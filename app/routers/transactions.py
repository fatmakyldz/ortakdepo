"""Gelir ve gider kayıtları, fiş dosyaları."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import GELIR, GIDER, Category, Receipt, Transaction, User
from ..money import AmountError, parse_amount
from ..security import current_user
from ..services import receipts as receipt_service
from ..textutil import MIN_DATE, clean_text, entry_date, to_id
from ..timeutil import add_months, fmt_month, month_bounds, parse_date, parse_month, today  # noqa: F401
from ..web import flash, redirect, render

router = APIRouter()

MAX_FILES = 8
KIND_LABEL = {GIDER: "Gider", GELIR: "Gelir"}


def categories_for(db: Session, kind: str, include_id: int | None = None) -> list[Category]:
    cats = db.scalars(
        select(Category).where(Category.kind == kind).order_by(Category.sort, Category.name)
    ).all()
    return [c for c in cats if c.is_active or c.id == include_id]


def partners(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def parse_partner(db: Session, raw: str) -> tuple[int | None, bool]:
    """'ortak' -> (None, True); kullanıcı no -> (id, True); geçersiz -> (None, False)."""
    if raw == "ortak":
        return None, True
    uid = to_id(raw)
    if uid is None:
        return None, False
    return (uid, True) if db.get(User, uid) else (None, False)


def clean_uploads(files: list[UploadFile] | None) -> list[UploadFile]:
    return [f for f in (files or []) if f is not None and getattr(f, "filename", "")]


def attach_receipts(db: Session, tx: Transaction, files: list[UploadFile]) -> list[str]:
    """Dosyaları kayda ekler. Yüklenemeyenlerin hata metinlerini döner."""
    problems: list[str] = []
    room = MAX_FILES - len(tx.receipts)
    for upload in files:
        if room <= 0:
            problems.append(f"Bir kayda en fazla {MAX_FILES} dosya eklenebilir; fazlası alınmadı.")
            break
        try:
            saved = receipt_service.save_upload(upload)
        except receipt_service.ReceiptError as exc:
            problems.append(str(exc))
            continue
        tx.receipts.append(
            Receipt(
                path=saved.path, thumb_path=saved.thumb_path, original_name=saved.original_name,
                content_type=saved.content_type, size=saved.size,
            )
        )
        room -= 1
    db.commit()
    return problems


def get_tx(db: Session, tx_id: int) -> Transaction:
    tx = db.get(Transaction, tx_id) if 0 < tx_id < 2**31 else None
    if tx is None:
        raise HTTPException(404, "Kayıt bulunamadı.")
    return tx


# ---------------------------------------------------------------- liste

@dataclass
class DayGroup:
    day: date
    items: list[Transaction] = field(default_factory=list)
    income: int = 0
    expense: int = 0


def group_by_day(rows: list[Transaction]) -> list[DayGroup]:
    groups: dict[date, DayGroup] = {}
    for tx in rows:
        g = groups.setdefault(tx.day, DayGroup(tx.day))
        g.items.append(tx)
        if tx.kind == GELIR:
            g.income += tx.amount
        else:
            g.expense += tx.amount
    return list(groups.values())


@router.get("/kayitlar")
def list_transactions(
    request: Request,
    ay: str = "",
    tur: str = "",
    kategori: str = "",
    kim: str = "",
    q: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    year, month = parse_month(ay)
    start, end = month_bounds(year, month)
    query = select(Transaction).where(Transaction.day.between(start, end))
    if tur in (GIDER, GELIR):
        query = query.where(Transaction.kind == tur)
    if to_id(kategori):
        query = query.where(Transaction.category_id == to_id(kategori))
    if kim == "ortak":
        query = query.where(Transaction.partner_id.is_(None))
    elif to_id(kim):
        query = query.where(Transaction.partner_id == to_id(kim))
    q = clean_text(q, 100)
    if q:
        query = query.where(Transaction.description.ilike(f"%{q}%"))
    rows = db.scalars(query.order_by(Transaction.day.desc(), Transaction.id.desc())).unique().all()

    py, pm = add_months(year, month, -1)
    ny, nm = add_months(year, month, 1)
    all_cats = db.scalars(select(Category).order_by(Category.kind, Category.sort)).all()
    return render(request, "transactions.html", {
        "groups": group_by_day(rows),
        "total_income": sum(t.amount for t in rows if t.kind == GELIR),
        "total_expense": sum(t.amount for t in rows if t.kind == GIDER),
        "count": len(rows),
        "month_label": fmt_month(year, month),
        "ay": f"{year}-{month:02d}",
        "prev_ay": f"{py}-{pm:02d}",
        "next_ay": f"{ny}-{nm:02d}",
        "is_current_month": (year, month) == (today().year, today().month),
        "filters": {"tur": tur, "kategori": kategori, "kim": kim, "q": q},
        "has_filters": bool(tur or kategori or kim or q),
        "categories": all_cats,
        "partners": partners(db),
    })


# ---------------------------------------------------------------- yeni / düzenle

def _form_context(db: Session, kind: str, form: dict, errors: list[str], tx: Transaction | None = None):
    return {
        "kind": kind,
        "kind_label": KIND_LABEL[kind],
        "form": form,
        "errors": errors,
        "tx": tx,
        "categories": categories_for(db, kind, tx.category_id if tx else None),
        "partners": partners(db),
        "yesterday": today() - timedelta(days=1),
        "min_date": MIN_DATE,
    }


@router.get("/kayitlar/yeni")
def new_form(
    request: Request,
    tur: str = GIDER,
    gun: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    kind = tur if tur in (GIDER, GELIR) else GIDER
    form = {
        "gun": (parse_date(gun) or today()).isoformat(),
        "tutar": "", "kategori_id": "", "kim": str(user.id), "aciklama": "",
    }
    return render(request, "transaction_form.html", _form_context(db, kind, form, []))


def _validate(db: Session, kind: str, gun: str, tutar: str, kategori_id: str, kim: str, aciklama: str):
    errors: list[str] = []
    day, date_error = entry_date(gun)
    if date_error:
        errors.append(date_error)
    amount = 0
    try:
        amount = parse_amount(tutar)
    except AmountError as exc:
        errors.append(str(exc))
    category = db.get(Category, to_id(kategori_id)) if to_id(kategori_id) else None
    if category is None or category.kind != kind:
        errors.append("Kategori seçin.")
    partner_id, ok = parse_partner(db, kim)
    if not ok:
        errors.append("Kimin ödediğini seçin." if kind == GIDER else "Parayı kimin aldığını seçin.")
    description = clean_text(aciklama, 300)
    return errors, day, amount, category, partner_id, description


@router.post("/kayitlar/yeni")
def create_transaction(
    request: Request,
    tur: str = Form(GIDER),
    gun: str = Form(""),
    tutar: str = Form(""),
    kategori_id: str = Form(""),
    kim: str = Form(""),
    aciklama: str = Form(""),
    sonra: str = Form(""),
    fisler: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    kind = tur if tur in (GIDER, GELIR) else GIDER
    errors, day, amount, category, partner_id, description = _validate(
        db, kind, gun, tutar, kategori_id, kim, aciklama
    )
    files = clean_uploads(fisler)
    if errors:
        if files:
            errors.append("Seçtiğiniz fişleri yeniden eklemeniz gerekiyor.")
        form = {"gun": gun, "tutar": tutar, "kategori_id": kategori_id, "kim": kim, "aciklama": aciklama}
        return render(request, "transaction_form.html", _form_context(db, kind, form, errors), status_code=422)

    tx = Transaction(
        kind=kind, day=day, amount=amount, category_id=category.id,
        partner_id=partner_id, description=description, created_by_id=user.id,
    )
    db.add(tx)
    db.commit()
    problems = attach_receipts(db, tx, files)
    flash(request, f"{KIND_LABEL[kind]} kaydedildi.")
    for p in problems:
        flash(request, p, "hata")
    if problems:
        return redirect(f"/kayitlar/{tx.id}")
    if sonra == "yeni":
        return redirect("/kayitlar/yeni", tur=kind, gun=day.isoformat())
    return redirect("/")


@router.get("/kayitlar/{tx_id}")
def detail(
    request: Request, tx_id: int,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    tx = get_tx(db, tx_id)
    return render(request, "transaction_detail.html", {
        "tx": tx, "kind_label": KIND_LABEL[tx.kind], "max_files": MAX_FILES,
    })


@router.get("/kayitlar/{tx_id}/duzenle")
def edit_form(
    request: Request, tx_id: int,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    tx = get_tx(db, tx_id)
    from ..money import format_input

    form = {
        "gun": tx.day.isoformat(),
        "tutar": format_input(tx.amount),
        "kategori_id": str(tx.category_id or ""),
        "kim": str(tx.partner_id) if tx.partner_id else "ortak",
        "aciklama": tx.description,
    }
    return render(request, "transaction_form.html", _form_context(db, tx.kind, form, [], tx))


@router.post("/kayitlar/{tx_id}/duzenle")
def update_transaction(
    request: Request,
    tx_id: int,
    gun: str = Form(""),
    tutar: str = Form(""),
    kategori_id: str = Form(""),
    kim: str = Form(""),
    aciklama: str = Form(""),
    fisler: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    tx = get_tx(db, tx_id)
    errors, day, amount, category, partner_id, description = _validate(
        db, tx.kind, gun, tutar, kategori_id, kim, aciklama
    )
    files = clean_uploads(fisler)
    if errors:
        if files:
            errors.append("Seçtiğiniz fişleri yeniden eklemeniz gerekiyor.")
        form = {"gun": gun, "tutar": tutar, "kategori_id": kategori_id, "kim": kim, "aciklama": aciklama}
        return render(request, "transaction_form.html", _form_context(db, tx.kind, form, errors, tx), status_code=422)

    tx.day, tx.amount, tx.category_id = day, amount, category.id
    tx.partner_id, tx.description = partner_id, description
    db.commit()
    for p in attach_receipts(db, tx, files):
        flash(request, p, "hata")
    flash(request, "Kayıt güncellendi.")
    return redirect(f"/kayitlar/{tx.id}")


@router.post("/kayitlar/{tx_id}/sil")
def delete_transaction(
    request: Request, tx_id: int,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    tx = get_tx(db, tx_id)
    paths = [p for r in tx.receipts for p in (r.path, r.thumb_path)]
    inst = tx.installment
    message = "Kayıt silindi."
    if inst is not None:
        if inst.fixed.is_active:
            inst.transaction_id = None
            message = "Kayıt silindi. Bağlı olduğu taksit yeniden ödenecekler listesinde."
        else:
            # Sonlandırılmış sabit giderin taksiti yeniden açılmaz; görünmeyen borç kalmasın
            db.delete(inst)
            message = "Kayıt silindi. Bağlı olduğu sabit gider sonlandırıldığı için taksit yeniden açılmadı."
    db.delete(tx)
    db.commit()
    receipt_service.delete_files(*paths)
    flash(request, message)
    return redirect("/kayitlar", ay=f"{tx.day.year}-{tx.day.month:02d}")


# ---------------------------------------------------------------- fişler

@router.post("/kayitlar/{tx_id}/fis")
def add_receipts(
    request: Request, tx_id: int,
    fisler: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    tx = get_tx(db, tx_id)
    files = clean_uploads(fisler)
    if not files:
        flash(request, "Eklenecek dosya seçin.", "hata")
        return redirect(f"/kayitlar/{tx.id}")
    before = len(tx.receipts)
    problems = attach_receipts(db, tx, files)
    added = len(tx.receipts) - before
    if added:
        flash(request, f"{added} dosya eklendi.")
    for p in problems:
        flash(request, p, "hata")
    return redirect(f"/kayitlar/{tx.id}")


def _get_receipt(db: Session, receipt_id: int) -> Receipt:
    rec = db.get(Receipt, receipt_id) if 0 < receipt_id < 2**31 else None
    if rec is None:
        raise HTTPException(404, "Dosya bulunamadı.")
    return rec


@router.post("/fisler/{receipt_id}/sil")
def delete_receipt(
    request: Request, receipt_id: int,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    rec = _get_receipt(db, receipt_id)
    tx_id = rec.transaction_id
    paths = (rec.path, rec.thumb_path)
    db.delete(rec)
    db.commit()
    receipt_service.delete_files(*paths)
    flash(request, "Dosya silindi.")
    return redirect(f"/kayitlar/{tx_id}")


def _serve(rec: Receipt, rel: str, content_type: str) -> FileResponse:
    full = receipt_service.resolve(rel)
    if full is None:
        raise HTTPException(404, "Dosya diskte bulunamadı.")
    return FileResponse(
        full, media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "Content-Disposition": "inline",
            # Dosya yanıtı hiçbir şey çalıştıramaz; tarayıcının PDF görüntüleyicisi için
            # yalnızca aynı kaynaktan gömme serbest (sayfalardaki genel politika bunu kapatır).
            "Content-Security-Policy": "default-src 'none'; img-src 'self'; object-src 'self'; "
                                       "style-src 'unsafe-inline'; frame-ancestors 'none'",
        },
    )


@router.get("/fisler/{receipt_id}/dosya")
def receipt_file(
    receipt_id: int, db: Session = Depends(get_db), user: User = Depends(current_user),
):
    rec = _get_receipt(db, receipt_id)
    return _serve(rec, rec.path, rec.content_type)


@router.get("/fisler/{receipt_id}/kucuk")
def receipt_thumb(
    receipt_id: int, db: Session = Depends(get_db), user: User = Depends(current_user),
):
    rec = _get_receipt(db, receipt_id)
    if not rec.thumb_path:
        raise HTTPException(404, "Önizleme yok.")
    return _serve(rec, rec.thumb_path, "image/jpeg")
