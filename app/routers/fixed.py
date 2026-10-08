"""Sabit giderler (leasing vb.) ve taksit ödemeleri."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import GIDER, Category, FixedExpense, Installment, User
from ..money import AmountError, parse_amount
from ..security import current_user
from ..services import fixed as fixed_service
from ..textutil import clean_text, entry_date, to_id, to_int
from ..timeutil import add_months, month_bounds, parse_date, today
from ..web import flash, redirect, render
from .transactions import attach_receipts, categories_for, clean_uploads, parse_partner, partners

router = APIRouter()


def _page(request: Request, db: Session, form: dict | None = None, errors: list[str] | None = None, status: int = 200):
    fixed_service.ensure_installments(db)
    on = today()
    active = db.scalars(
        select(FixedExpense).where(FixedExpense.is_active).order_by(FixedExpense.name)
    ).all()
    ended = db.scalars(
        select(FixedExpense).where(FixedExpense.is_active.is_(False)).order_by(FixedExpense.id.desc())
    ).all()
    # Liste kalabalık olmasın: gecikenler + gelecek ayın sonuna kadar olanlar
    unpaid = fixed_service.unpaid_items(db, on, until=month_bounds(*add_months(on.year, on.month, 1))[1])
    paid = db.scalars(
        select(Installment)
        .where(Installment.transaction_id.is_not(None))
        .order_by(Installment.due_date.desc())
        .limit(12)
    ).all()
    cards = []
    for fx in active:
        left, left_total = fixed_service.remaining(fx)
        cards.append({"fx": fx, "left": left, "left_total": left_total})
    leasing = db.scalar(select(Category).where(Category.kind == GIDER, Category.name == "Leasing"))
    default_form = {
        "ad": "", "tutar": "", "ilk_vade": "", "taksit": "", "hatirlat": "3",
        "kategori_id": str(leasing.id) if leasing else "", "not": "",
    }
    return render(request, "fixed.html", {
        "cards": cards,
        "ended": ended,
        "unpaid": unpaid,
        "unpaid_total": sum(i.installment.amount for i in unpaid),
        "paid": paid,
        "partners": partners(db),
        "categories": categories_for(db, GIDER),
        "form": form or default_form,
        "errors": errors or [],
        "open_form": bool(errors) or not active,
    }, status_code=status)


@router.get("/sabit")
def fixed_page(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _page(request, db)


@router.post("/sabit")
def create_fixed(
    request: Request,
    ad: str = Form(""),
    tutar: str = Form(""),
    ilk_vade: str = Form(""),
    taksit: str = Form(""),
    hatirlat: str = Form("3"),
    kategori_id: str = Form(""),
    aciklama: str = Form("", alias="not"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    form = {"ad": ad, "tutar": tutar, "ilk_vade": ilk_vade, "taksit": taksit,
            "hatirlat": hatirlat, "kategori_id": kategori_id, "not": aciklama}
    errors: list[str] = []
    name = clean_text(ad, 120)
    if not name:
        errors.append("Giderin adını yazın. Örnek: Kamyon leasing")
    amount = 0
    try:
        amount = parse_amount(tutar)
    except AmountError as exc:
        errors.append(str(exc))
    first_due = parse_date(ilk_vade)
    if first_due is None:
        errors.append("Sıradaki ödeme tarihini seçin.")
    elif first_due < today() - timedelta(days=366):
        errors.append("Sıradaki ödeme tarihi bir yıldan eski olamaz.")
    elif first_due > today() + timedelta(days=366 * 2):
        errors.append("Sıradaki ödeme tarihi iki yıldan ileri olamaz; yılı kontrol edin.")
    total_count = None
    if taksit.strip():
        total_count = to_id(taksit)
        if total_count is None or not (1 <= total_count <= 600):
            total_count = None
            errors.append("Kalan taksit sayısı 1 ile 600 arasında olmalı ya da boş bırakılmalı.")
    remind = to_int(hatirlat, 3, 0, 30)
    category = db.get(Category, to_id(kategori_id)) if to_id(kategori_id) else None
    if category is None or category.kind != GIDER:
        errors.append("Kategori seçin.")
    if errors:
        return _page(request, db, form, errors, status=422)

    fx = FixedExpense(
        name=name, amount=amount, due_day=first_due.day, first_due=first_due,
        total_count=total_count, category_id=category.id, remind_days=remind,
        note=clean_text(aciklama, 300),
    )
    db.add(fx)
    db.commit()
    fixed_service.ensure_installments(db)
    flash(request, f"“{name}” eklendi. Ödeme günü yaklaşınca uyarı göreceksiniz.")
    return redirect("/sabit")


def _get_fixed(db: Session, fixed_id: int) -> FixedExpense:
    fx = db.get(FixedExpense, fixed_id) if 0 < fixed_id < 2**31 else None
    if fx is None:
        raise HTTPException(404, "Sabit gider bulunamadı.")
    return fx


@router.post("/sabit/{fixed_id}/guncelle")
def update_fixed(
    request: Request, fixed_id: int,
    ad: str = Form(""), tutar: str = Form(""), hatirlat: str = Form("3"),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    fx = _get_fixed(db, fixed_id)
    try:
        amount = parse_amount(tutar)
    except AmountError as exc:
        flash(request, str(exc), "hata")
        return redirect("/sabit")
    if clean_text(ad):
        fx.name = clean_text(ad, 120)
    fx.remind_days = to_int(hatirlat, fx.remind_days, 0, 30)
    if amount != fx.amount:
        fx.amount = amount
        for inst in fx.installments:
            if not inst.is_paid:
                inst.amount = amount
    db.commit()
    flash(request, f"“{fx.name}” güncellendi. Ödenmemiş taksitler yeni tutarla görünüyor.")
    return redirect("/sabit")


@router.post("/sabit/{fixed_id}/sonlandir")
def end_fixed(
    request: Request, fixed_id: int,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    fx = _get_fixed(db, fixed_id)
    has_paid = any(i.is_paid for i in fx.installments)
    name = fx.name
    if has_paid:
        fixed_service.end_fixed(db, fx)
        flash(request, f"“{name}” sonlandırıldı. Ödenmiş taksitler kayıtlarda duruyor.")
    else:
        db.delete(fx)
        db.commit()
        flash(request, f"“{name}” silindi.")
    return redirect("/sabit")


@router.post("/taksit/{inst_id}/ode")
def pay_installment(
    request: Request, inst_id: int,
    gun: str = Form(""), tutar: str = Form(""), kim: str = Form(""),
    donus: str = Form("/sabit"),
    fisler: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    inst = db.get(Installment, inst_id) if 0 < inst_id < 2**31 else None
    if inst is None:
        raise HTTPException(404, "Taksit bulunamadı.")
    back = "/" if donus == "/" else "/sabit"
    errors: list[str] = []
    paid_on, date_error = entry_date(gun)
    if date_error:
        errors.append("Ödeme tarihi: " + date_error)
    amount = 0
    try:
        amount = parse_amount(tutar)
    except AmountError as exc:
        errors.append(str(exc))
    partner_id, ok = parse_partner(db, kim)
    if not ok:
        errors.append("Kimin ödediğini seçin.")
    if inst.is_paid:
        errors.append("Bu taksit zaten ödendi olarak işaretli.")
    if errors:
        for e in errors:
            flash(request, e, "hata")
        return redirect(back)

    try:
        tx = fixed_service.pay_installment(
            db, inst, paid_on=paid_on, amount=amount, partner_id=partner_id, created_by_id=user.id
        )
    except ValueError as exc:
        flash(request, str(exc), "hata")
        return redirect(back)
    for p in attach_receipts(db, tx, clean_uploads(fisler)):
        flash(request, p, "hata")
    flash(request, f"{fixed_service.installment_label(inst)} ödendi olarak kaydedildi.")
    return redirect(back)
