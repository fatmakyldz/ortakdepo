"""Sabit giderler ve aylık taksitleri."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import GIDER, FixedExpense, Installment, Transaction
from ..timeutil import AYLAR, add_months, clamp_day, month_bounds, today

# Taksitler bu kadar ay ilerisine kadar önceden açılır (içinde bulunulan ay dahil değil).
# 30 güne kadar "önceden hatırlat" süresinin her ayda yetişmesi için iki ay.
HORIZON_MONTHS = 2


def due_date_for(fixed: FixedExpense, seq: int) -> date:
    y, m = add_months(fixed.first_due.year, fixed.first_due.month, seq - 1)
    return clamp_day(y, m, fixed.due_day)


def ensure_installments(db: Session, on: date | None = None) -> int:
    """Aktif sabit giderler için eksik taksitleri açar. Açılan taksit sayısını döner."""
    on = on or today()
    hy, hm = add_months(on.year, on.month, HORIZON_MONTHS)
    horizon = month_bounds(hy, hm)[1]
    created = 0
    fixed_list = db.scalars(select(FixedExpense).where(FixedExpense.is_active)).all()
    for fx in fixed_list:
        existing = {
            i.seq for i in db.scalars(select(Installment).where(Installment.fixed_id == fx.id))
        }
        seq = 1
        while fx.total_count is None or seq <= fx.total_count:
            due = due_date_for(fx, seq)
            if due > horizon:
                break
            if seq not in existing:
                db.add(Installment(fixed_id=fx.id, seq=seq, due_date=due, amount=fx.amount))
                created += 1
            seq += 1
            if seq > 1200:  # emniyet: 100 yıl
                break
    if created:
        try:
            db.commit()
        except IntegrityError:
            # Aynı anda başka bir istek (ya da arka plan döngüsü) aynı taksitleri açtı
            db.rollback()
            return 0
    return created


@dataclass
class DueItem:
    installment: Installment
    days_left: int  # negatifse gecikmiş

    @property
    def state(self) -> str:
        if self.days_left < 0:
            return "gecikti"
        if self.days_left == 0:
            return "bugun"
        return "yaklasan"

    @property
    def when_text(self) -> str:
        d = self.days_left
        if d < 0:
            return f"{-d} gün gecikti"
        if d == 0:
            return "Bugün son gün"
        if d == 1:
            return "Yarın"
        return f"{d} gün kaldı"


def unpaid_items(db: Session, on: date | None = None, until: date | None = None) -> list[DueItem]:
    """Ödenmemiş taksitler, vadesi en yakın olandan başlayarak."""
    on = on or today()
    q = (
        select(Installment)
        .join(FixedExpense)
        .where(Installment.transaction_id.is_(None), FixedExpense.is_active)
        .order_by(Installment.due_date, Installment.id)
    )
    if until:
        q = q.where(Installment.due_date <= until)
    return [DueItem(i, (i.due_date - on).days) for i in db.scalars(q)]


def alerts(db: Session, on: date | None = None) -> list[DueItem]:
    """Uyarı gösterilecek taksitler: gecikenler ve hatırlatma süresine girenler."""
    on = on or today()
    return [
        it for it in unpaid_items(db, on) if it.days_left <= it.installment.fixed.remind_days
    ]


def installment_label(inst: Installment) -> str:
    fx = inst.fixed
    ay = f"{AYLAR[inst.due_date.month]} {inst.due_date.year}"
    if fx.total_count:
        return f"{fx.name}, {ay} ({inst.seq}/{fx.total_count})"
    return f"{fx.name}, {ay}"


def pay_installment(
    db: Session,
    inst: Installment,
    *,
    paid_on: date,
    amount: int,
    partner_id: int | None,
    created_by_id: int | None,
) -> Transaction:
    if inst.is_paid:
        raise ValueError("Bu taksit zaten ödendi olarak işaretli.")
    tx = Transaction(
        kind=GIDER,
        day=paid_on,
        amount=amount,
        category_id=inst.fixed.category_id,
        partner_id=partner_id,
        description=installment_label(inst),
        created_by_id=created_by_id,
    )
    db.add(tx)
    db.flush()
    # Koşullu güncelleme: iki istek aynı anda gelirse yalnızca biri taksiti kapatabilir
    claimed = db.execute(
        update(Installment)
        .where(Installment.id == inst.id, Installment.transaction_id.is_(None))
        .values(transaction_id=tx.id)
    ).rowcount
    if not claimed:
        db.rollback()
        raise ValueError("Bu taksit zaten ödendi olarak işaretli.")
    db.commit()
    db.refresh(inst)
    return tx


def end_fixed(db: Session, fx: FixedExpense) -> None:
    """Sabit gideri sonlandırır: ödenmemiş taksitler kalkar, ödenenler kayıtlarda durur."""
    fx.is_active = False
    for inst in list(fx.installments):
        if not inst.is_paid:
            db.delete(inst)
    db.commit()


def remaining(fx: FixedExpense, on: date | None = None) -> tuple[int | None, int | None]:
    """(kalan taksit sayısı, kalan toplam tutar). Süresiz giderlerde (None, None)."""
    if fx.total_count is None:
        return None, None
    paid = sum(1 for i in fx.installments if i.is_paid)
    left = max(fx.total_count - paid, 0)
    return left, left * fx.amount
