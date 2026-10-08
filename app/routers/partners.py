"""Ortakların şirketle cari hesabı ve şirket-ortak ödemeleri."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PAYMENT_LABELS, PartnerPayment, User
from ..money import AmountError, parse_amount
from ..security import current_user
from ..services import balance
from ..textutil import clean_text, entry_date, to_id
from ..web import flash, redirect, render

router = APIRouter()


@router.get("/ortaklar")
def partners_page(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    sheet = balance.compute(db)
    payments = db.scalars(
        select(PartnerPayment).order_by(PartnerPayment.day.desc(), PartnerPayment.id.desc()).limit(50)
    ).all()
    return render(request, "partners.html", {
        "sheet": sheet,
        "payments": payments,
        "users": [l.user for l in sheet.lines],
        "labels": PAYMENT_LABELS,
    })


@router.post("/ortaklar/odeme")
def add_payment(
    request: Request,
    gun: str = Form(""), ortak: str = Form(""), yon: str = Form(""),
    tutar: str = Form(""), aciklama: str = Form(""),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    errors: list[str] = []
    day, date_error = entry_date(gun)
    if date_error:
        errors.append(date_error)
    amount = 0
    try:
        amount = parse_amount(tutar)
    except AmountError as exc:
        errors.append(str(exc))
    who = db.get(User, to_id(ortak)) if to_id(ortak) else None
    if not who:
        errors.append("Ortağı seçin.")
    if yon not in PAYMENT_LABELS:
        errors.append("Ödemenin yönünü seçin.")
    if errors:
        for e in errors:
            flash(request, e, "hata")
        return redirect("/ortaklar")
    db.add(PartnerPayment(day=day, user_id=who.id, direction=yon, amount=amount,
                          note=clean_text(aciklama, 300)))
    db.commit()
    flash(request, f"{who.name}: {PAYMENT_LABELS[yon].lower()}, kaydedildi.")
    return redirect("/ortaklar")


@router.post("/ortaklar/odeme/{pid}/sil")
def delete_payment(
    request: Request, pid: int,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    p = db.get(PartnerPayment, pid) if 0 < pid < 2**31 else None
    if p is None:
        raise HTTPException(404, "Kayıt bulunamadı.")
    db.delete(p)
    db.commit()
    flash(request, "Ödeme kaydı silindi.")
    return redirect("/ortaklar")
