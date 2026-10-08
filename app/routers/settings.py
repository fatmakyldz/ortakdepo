"""Ayarlar: profil, ortaklık payı, kategoriler, e-posta."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
import math

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import icons
from ..config import settings
from ..db import get_db
from ..models import GELIR, GIDER, Category, Transaction, User
from ..security import current_user, hash_password, start_session, verify_password
from ..services import reminders
from ..textutil import clean_text, name_key
from ..web import flash, redirect, render
from .auth import EMAIL_RE, MIN_PASSWORD
from .partners import share_text

router = APIRouter()


@router.get("/ayarlar")
def settings_page(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cats = db.scalars(select(Category).order_by(Category.kind.desc(), Category.sort, Category.name)).all()
    used = dict(
        db.execute(
            select(Transaction.category_id, func.count()).group_by(Transaction.category_id)
        ).all()
    )
    return render(request, "settings.html", {
        "users": list(db.scalars(select(User).order_by(User.id))),
        "share_text": share_text,
        "expense_cats": [c for c in cats if c.kind == GIDER],
        "income_cats": [c for c in cats if c.kind == GELIR],
        "used": used,
        "smtp_ok": settings.smtp_configured,
        "smtp_from": settings.smtp_from,
        "reminder_hour": settings.reminder_hour,
        "reminders_enabled": settings.reminders_enabled,
    })


@router.post("/ayarlar/profil")
def update_profile(
    request: Request,
    ad: str = Form(""), eposta: str = Form(""), bildirim: str = Form(""),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    name, email = clean_text(ad, 80), clean_text(eposta, 200).lower()
    if not name:
        flash(request, "Adınızı yazın.", "hata")
    elif not EMAIL_RE.match(email):
        flash(request, "E-posta adresi geçerli değil.", "hata")
    elif db.scalar(select(User.id).where(User.email == email, User.id != user.id)):
        flash(request, "Bu e-posta adresini diğer ortak kullanıyor.", "hata")
    else:
        user.name, user.email, user.notify_email = name, email, bildirim == "1"
        db.commit()
        flash(request, "Bilgileriniz güncellendi.")
    return redirect("/ayarlar")


@router.post("/ayarlar/sifre")
def change_password(
    request: Request,
    eski: str = Form(""), yeni: str = Form(""), tekrar: str = Form(""),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    if not verify_password(eski, user.password_hash):
        flash(request, "Mevcut şifre hatalı.", "hata")
    elif len(yeni) < MIN_PASSWORD:
        flash(request, f"Yeni şifre en az {MIN_PASSWORD} karakter olmalı.", "hata")
    elif yeni != tekrar:
        flash(request, "Yeni şifre ile tekrarı aynı değil.", "hata")
    else:
        user.password_hash = hash_password(yeni)
        db.commit()
        start_session(request, user)  # bu cihaz açık kalır, eski oturumlar düşer
        flash(request, "Şifreniz değişti. Diğer cihazlarda yeniden giriş yapmanız gerekecek.")
    return redirect("/ayarlar")


@router.post("/ayarlar/pay")
async def update_shares(
    request: Request, db: Session = Depends(get_db), user: User = Depends(current_user),
):
    form = await request.form()
    users = list(db.scalars(select(User).order_by(User.id)))
    shares: dict[int, int] = {}
    try:
        for u in users:
            raw = str(form.get(f"pay_{u.id}", "")).strip().replace(",", ".")
            number = float(raw)
            if not math.isfinite(number) or not (0 <= number <= 100):
                raise ValueError
            shares[u.id] = round(number * 100)
    except (ValueError, OverflowError):
        flash(request, "Payları yüzde olarak yazın. Örnek: 50", "hata")
        return redirect("/ayarlar")
    if sum(shares.values()) != 10000:
        flash(request, "Payların toplamı %100 olmalı.", "hata")
        return redirect("/ayarlar")
    for u in users:
        u.share_bp = shares[u.id]
    db.commit()
    flash(request, "Ortaklık payları güncellendi. Ortak bakiyesi yeni paylara göre hesaplanıyor.")
    return redirect("/ayarlar")


@router.post("/ayarlar/kategori")
def add_category(
    request: Request, ad: str = Form(""), tur: str = Form(GIDER),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    name = clean_text(ad, 60)
    kind = tur if tur in (GIDER, GELIR) else GIDER
    if not name:
        flash(request, "Kategori adını yazın.", "hata")
        return redirect("/ayarlar")
    existing = _same_name(db, kind, name)
    if existing:
        if existing.is_active:
            flash(request, f"“{existing.name}” zaten var.", "hata")
        else:
            existing.is_active = True
            db.commit()
            flash(request, f"“{existing.name}” yeniden kullanıma açıldı.")
        return redirect("/ayarlar")
    top = db.scalar(select(func.max(Category.sort)).where(Category.kind == kind)) or 0
    db.add(Category(name=name, kind=kind, sort=top + 1, icon=icons.guess_icon(name, kind)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        flash(request, f"“{name}” zaten var.", "hata")
        return redirect("/ayarlar")
    flash(request, f"“{name}” kategorisi eklendi.")
    return redirect("/ayarlar")


def _same_name(db: Session, kind: str, name: str, exclude_id: int | None = None) -> Category | None:
    """Aynı adlı kategori (büyük/küçük harf ve Türkçe harfler gözetilerek).

    SQLite'ın lower() işlevi Ş, İ, Ö gibi harfleri küçültmediği için karşılaştırma burada yapılır.
    """
    key = name_key(name)
    for cat in db.scalars(select(Category).where(Category.kind == kind)):
        if cat.id != exclude_id and name_key(cat.name) == key:
            return cat
    return None


def _get_category(db: Session, cat_id: int) -> Category:
    cat = db.get(Category, cat_id) if 0 < cat_id < 2**31 else None
    if cat is None:
        raise HTTPException(404, "Kategori bulunamadı.")
    return cat


@router.post("/ayarlar/kategori/{cat_id}/ad")
def rename_category(
    request: Request, cat_id: int, ad: str = Form(""), simge: str = Form(""),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    cat = _get_category(db, cat_id)
    name = clean_text(ad, 60)
    if simge in icons.CATEGORY_ICONS:
        cat.icon = simge
    if not name:
        flash(request, "Kategori adı boş olamaz.", "hata")
    elif _same_name(db, cat.kind, name, exclude_id=cat.id):
        flash(request, f"“{name}” adında başka bir kategori var.", "hata")
    else:
        cat.name = name
        try:
            db.commit()
            flash(request, "Kategori güncellendi.")
        except IntegrityError:
            db.rollback()
            flash(request, f"“{name}” adında başka bir kategori var.", "hata")
    return redirect("/ayarlar")


@router.post("/ayarlar/kategori/{cat_id}/durum")
def toggle_category(
    request: Request, cat_id: int,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    cat = _get_category(db, cat_id)
    in_use = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.category_id == cat.id))
    if cat.is_active and not in_use:
        from ..models import FixedExpense

        if not db.scalar(select(func.count()).select_from(FixedExpense).where(FixedExpense.category_id == cat.id)):
            db.delete(cat)
            db.commit()
            flash(request, f"“{cat.name}” silindi.")
            return redirect("/ayarlar")
    cat.is_active = not cat.is_active
    db.commit()
    flash(
        request,
        f"“{cat.name}” yeniden kullanıma açıldı." if cat.is_active
        else f"“{cat.name}” artık yeni kayıtlarda çıkmayacak. Eski kayıtlar duruyor.",
    )
    return redirect("/ayarlar")


@router.post("/ayarlar/test-eposta")
def test_email(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        reminders.send_mail(
            [user.email],
            f"{settings.app_name}: deneme e-postası",
            "Bu bir deneme e-postasıdır. Ödeme hatırlatmaları bu adrese gelecek.",
        )
        flash(request, f"Deneme e-postası {user.email} adresine gönderildi.")
    except reminders.MailError as exc:
        flash(request, str(exc), "hata")
    return redirect("/ayarlar")
