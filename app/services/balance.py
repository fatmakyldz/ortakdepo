"""Ortakların şirketle cari hesabı.

Bir ortağın cebinden çıkan net para (ödediği giderler − teslim aldığı gelirler)
şirketten alacağıdır. Şirketin ortağa yaptığı ödemeler bu alacağı düşürür,
ortağın şirkete yatırdığı para artırır. Ortaklar birbirine borçlanmaz.

Ortak hesaptan/kasadan yapılan işlemler (partner_id boş) kimsenin cebinden
çıkmadığı için bu hesaba girmez.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import GELIR, GIDER, ORTAK_YATIRDI, SIRKET_ODEDI, PartnerPayment, Transaction, User


@dataclass
class PartnerLine:
    user: User
    paid: int = 0
    collected: int = 0
    received: int = 0
    deposited: int = 0

    @property
    def out_of_pocket(self) -> int:
        return self.paid - self.collected

    @property
    def balance(self) -> int:
        return self.out_of_pocket - self.received + self.deposited


@dataclass
class BalanceSheet:
    lines: list[PartnerLine] = field(default_factory=list)

    @property
    def open(self) -> list[PartnerLine]:
        return [l for l in self.lines if l.balance != 0]

    @property
    def settled(self) -> bool:
        return not self.open


def compute(db: Session) -> BalanceSheet:
    users = list(db.scalars(select(User).order_by(User.id)))
    lines = {u.id: PartnerLine(user=u) for u in users}

    rows = db.execute(
        select(Transaction.partner_id, Transaction.kind, func.sum(Transaction.amount))
        .where(Transaction.partner_id.is_not(None))
        .group_by(Transaction.partner_id, Transaction.kind)
    ).all()
    for pid, kind, total in rows:
        if pid not in lines:
            continue
        if kind == GIDER:
            lines[pid].paid = total or 0
        elif kind == GELIR:
            lines[pid].collected = total or 0

    pays = db.execute(
        select(PartnerPayment.user_id, PartnerPayment.direction, func.sum(PartnerPayment.amount))
        .group_by(PartnerPayment.user_id, PartnerPayment.direction)
    ).all()
    for uid, direction, total in pays:
        if uid not in lines:
            continue
        if direction == SIRKET_ODEDI:
            lines[uid].received = total or 0
        elif direction == ORTAK_YATIRDI:
            lines[uid].deposited = total or 0

    return BalanceSheet(lines=[lines[u.id] for u in users])
