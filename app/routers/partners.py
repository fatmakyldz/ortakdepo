"""Ortak bakiyesi ve hesaplaşma ödemeleri."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Settlement, User
from ..money import AmountError, parse_amount
from ..security import current_user
from ..services import balance
from ..textutil import clean_text, entry_date, to_id
from ..web import flash, redirect, render

router = APIRouter()


def share_text(bp: int) -> str:
    """5000 -> '50', 3333 -> '33,33'."""
    return f"{bp / 100:.2f}".rstrip("0").rstrip(".").replace(".", ",")


@router.get("/ortaklar")
def partners_page(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    sheet = balance.compute(db)
    settlements = db.scalars(
        select(Settlement).order_by(Settlement.day.desc(), Settlement.id.desc()).limit(50)
    ).all()
    return render(request, "partners.html", {
        "sheet": sheet,
        "settlements": settlements,
        "users": [l.user for l in sheet.lines],
        "share_label": " / ".join("%" + share_text(l.user.share_bp) for l in sheet.lines),
    })


@router.post("/ortaklar/hesaplasma")
def add_settlement(
    request: Request,
    gun: str = Form(""), kimden: str = Form(""), kime: str = Form(""),
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
    src = db.get(User, to_id(kimden)) if to_id(kimden) else None
    dst = db.get(User, to_id(kime)) if to_id(kime) else None
    if not src or not dst:
        errors.append("Ödeyen ve alan ortağı seçin.")
    elif src.id == dst.id:
        errors.append("Ödeyen ve alan aynı kişi olamaz.")
    if errors:
        for e in errors:
            flash(request, e, "hata")
        return redirect("/ortaklar")
    db.add(Settlement(day=day, from_user_id=src.id, to_user_id=dst.id, amount=amount,
                      note=clean_text(aciklama, 300)))
    db.commit()
    flash(request, f"{src.name}, {dst.name} ortağına yaptığı ödeme kaydedildi.")
    return redirect("/ortaklar")


@router.post("/ortaklar/hesaplasma/{sid}/sil")
def delete_settlement(
    request: Request, sid: int,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    s = db.get(Settlement, sid) if 0 < sid < 2**31 else None
    if s is None:
        raise HTTPException(404, "Kayıt bulunamadı.")
    db.delete(s)
    db.commit()
    flash(request, "Hesaplaşma kaydı silindi.")
    return redirect("/ortaklar")
