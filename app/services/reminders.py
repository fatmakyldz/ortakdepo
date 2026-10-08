"""Ödeme günü hatırlatmaları (e-posta).

Kural:
  - vadeye `remind_days` gün ya da daha az kaldığında bir kez  -> "yaklasan"
  - vade günü bir kez                                          -> "bugun"
  - vade geçtiyse, ödenene kadar haftada bir                    -> "gecikti"
Gönderilenler `ReminderLog`a yazılır; aynı hatırlatma ikinci kez gitmez.
"""
from __future__ import annotations

import asyncio
import html
import logging
import smtplib
import ssl
from datetime import date, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import ReminderLog, User
from ..money import format_try
from ..timeutil import fmt_date, now, today
from . import fixed

log = logging.getLogger("ortakdefter.hatirlatma")


class MailError(RuntimeError):
    pass


def send_mail(to: list[str], subject: str, text: str, html_body: str | None = None) -> None:
    if not settings.smtp_configured:
        raise MailError("E-posta ayarları yapılmamış (SMTP_HOST ve SMTP_FROM gerekli).")
    if not to:
        raise MailError("Gönderilecek adres yok.")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(to)
    msg.set_content(text)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    try:
        if settings.smtp_tls == "ssl":
            server = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=20,
                context=ssl.create_default_context(),
            )
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        with server:
            if settings.smtp_tls == "starttls":
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(f"E-posta gönderilemedi: {exc}") from exc


def _pending(db: Session, on: date) -> list[tuple[fixed.DueItem, str]]:
    out: list[tuple[fixed.DueItem, str]] = []
    overdue: list[fixed.DueItem] = []
    overdue_due = False
    for item in fixed.unpaid_items(db, on):
        inst = item.installment
        if item.days_left > inst.fixed.remind_days:
            continue
        kind = item.state
        q = select(ReminderLog.id).where(
            ReminderLog.installment_id == inst.id, ReminderLog.kind == kind
        )
        if kind == "gecikti":
            overdue.append(item)
            q = q.where(ReminderLog.sent_on > on - timedelta(days=7))
            overdue_due = overdue_due or db.scalar(q.limit(1)) is None
        elif db.scalar(q.limit(1)) is None:
            out.append((item, kind))
    # Gecikenlerden birinin haftası dolduysa hepsi aynı e-postada gider ve birlikte kaydedilir;
    # böylece her taksit kendi takvimiyle ayrı ayrı e-posta üretmez, toplam borç eksik görünmez.
    if overdue_due:
        out = [(item, "gecikti") for item in overdue] + out
    return out


def build_message(items: list[fixed.DueItem]) -> tuple[str, str, str]:
    overdue = [i for i in items if i.days_left < 0]
    total = sum(i.installment.amount for i in items)
    if len(items) == 1:
        it = items[0]
        subject = f"{it.installment.fixed.name}: {it.when_text.lower()} ({format_try(it.installment.amount)})"
    elif overdue:
        subject = f"{len(items)} ödeme bekliyor, {len(overdue)} tanesi gecikti"
    else:
        subject = f"Yaklaşan {len(items)} ödeme, toplam {format_try(total)}"

    lines = [
        f"- {fixed.installment_label(i.installment)}: {format_try(i.installment.amount)}, "
        f"vade {fmt_date(i.installment.due_date)} ({i.when_text.lower()})"
        for i in items
    ]
    link = f"{settings.base_url}/sabit"
    text = "\n".join(
        ["Ödeme hatırlatması", "", *lines, "", f"Toplam: {format_try(total)}",
         "", f"Ödendi olarak işaretlemek için: {link}"]
    )
    rows = "".join(
        "<tr>"
        f"<td style='padding:8px 12px 8px 0;border-bottom:1px solid #d9dee3'>{html.escape(fixed.installment_label(i.installment))}"
        f"<br><span style='color:{'#C4432B' if i.days_left < 0 else '#4A5670'};font-size:13px'>"
        f"Vade {html.escape(fmt_date(i.installment.due_date))}, {html.escape(i.when_text.lower())}</span></td>"
        f"<td style='padding:8px 0;border-bottom:1px solid #d9dee3;text-align:right;white-space:nowrap'>"
        f"<b>{html.escape(format_try(i.installment.amount))}</b></td>"
        "</tr>"
        for i in items
    )
    html_body = (
        "<div style='font-family:system-ui,Segoe UI,Arial,sans-serif;color:#16233B;max-width:520px'>"
        f"<h2 style='margin:0 0 12px;font-size:18px'>Ödeme hatırlatması</h2>"
        f"<table style='border-collapse:collapse;width:100%;font-size:15px'>{rows}"
        f"<tr><td style='padding:10px 12px 0 0'>Toplam</td>"
        f"<td style='padding:10px 0 0;text-align:right'><b>{html.escape(format_try(total))}</b></td></tr></table>"
        f"<p style='margin:20px 0 0'><a href='{html.escape(link)}' style='color:#2743C9'>"
        "Ödendi olarak işaretle</a></p>"
        f"<p style='color:#7C869A;font-size:12px;margin-top:24px'>{html.escape(settings.app_name)}</p></div>"
    )
    return subject, text, html_body


def run_once(db: Session, on: date | None = None) -> int:
    """Bekleyen hatırlatmaları tek e-postada gönderir. Gönderilen taksit sayısını döner."""
    on = on or today()
    fixed.ensure_installments(db, on)
    pending = _pending(db, on)
    if not pending:
        return 0
    recipients = [
        u.email for u in db.scalars(select(User).where(User.notify_email)) if u.email
    ]
    if not recipients:
        return 0
    subject, text, html_body = build_message([item for item, _ in pending])
    send_mail(recipients, subject, text, html_body)
    for item, kind in pending:
        already = db.scalar(
            select(ReminderLog.id).where(
                ReminderLog.installment_id == item.installment.id,
                ReminderLog.kind == kind, ReminderLog.sent_on == on,
            )
        )
        if already is None:
            db.add(ReminderLog(installment_id=item.installment.id, kind=kind, sent_on=on))
    db.commit()
    return len(pending)


def _tick() -> None:
    with SessionLocal() as db:
        fixed.ensure_installments(db)
        if not (settings.reminders_enabled and settings.smtp_configured):
            return
        if now().hour < settings.reminder_hour:
            return
        try:
            sent = run_once(db)
            if sent:
                log.info("%s taksit için hatırlatma gönderildi", sent)
        except MailError as exc:
            log.warning("%s", exc)


async def loop() -> None:
    """Uygulama açıkken arka planda döner; 20 dakikada bir kontrol eder."""
    await asyncio.sleep(5)
    while True:
        try:
            await asyncio.to_thread(_tick)
        except Exception:  # döngü hiçbir hatada durmamalı
            log.exception("Hatırlatma döngüsünde beklenmeyen hata")
        await asyncio.sleep(20 * 60)
