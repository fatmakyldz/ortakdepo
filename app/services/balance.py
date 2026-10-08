"""Ortaklar arası borç-alacak hesabı.

Mantık: her ortağın "cebinden çıkan net para"sı = ödediği giderler − teslim aldığı
gelirler. İşletmenin bu yolla dönen toplam net gideri, ortaklık payına göre
bölüşülür. Cebinden payına düşenden fazla çıkan ortak alacaklı olur. Ortakların
birbirine yaptığı hesaplaşma ödemeleri bakiyeyi kapatır.

Ortak hesaptan/kasadan yapılan işlemler (partner_id boş) kimsenin cebinden
çıkmadığı için bu hesaba girmez.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import GELIR, GIDER, Settlement, Transaction, User


@dataclass
class PartnerLine:
    user: User
    paid: int = 0          # cebinden ödediği giderler
    collected: int = 0     # teslim aldığı gelirler
    fair_share: int = 0    # net giderden payına düşen
    sent: int = 0          # diğer ortağa yaptığı hesaplaşma ödemeleri
    received: int = 0      # diğer ortaktan aldığı hesaplaşma ödemeleri
    balance: int = 0       # > 0 alacaklı, < 0 borçlu

    @property
    def out_of_pocket(self) -> int:
        return self.paid - self.collected


@dataclass
class Transfer:
    from_user: User
    to_user: User
    amount: int


@dataclass
class BalanceSheet:
    lines: list[PartnerLine] = field(default_factory=list)
    transfers: list[Transfer] = field(default_factory=list)
    pool: int = 0  # ortakların cebinden dönen toplam net gider

    @property
    def settled(self) -> bool:
        return not self.transfers


def split_by_share(total: int, shares_bp: list[int]) -> list[int]:
    """Tutarı paylara göre kuruş kaybetmeden böler (en büyük kalan yöntemi)."""
    denom = sum(shares_bp)
    if denom <= 0 or not shares_bp:
        return [0 for _ in shares_bp]
    sign = -1 if total < 0 else 1
    total_abs = abs(total)
    raw = [total_abs * s for s in shares_bp]
    parts = [r // denom for r in raw]
    leftover = total_abs - sum(parts)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] % denom), i))
    for i in order[:leftover]:
        parts[i] += 1
    return [sign * p for p in parts]


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

    for s in db.scalars(select(Settlement)):
        if s.from_user_id in lines:
            lines[s.from_user_id].sent += s.amount
        if s.to_user_id in lines:
            lines[s.to_user_id].received += s.amount

    ordered = [lines[u.id] for u in users]
    pool = sum(l.out_of_pocket for l in ordered)
    shares = split_by_share(pool, [l.user.share_bp for l in ordered])
    for line, share in zip(ordered, shares):
        line.fair_share = share
        line.balance = line.out_of_pocket - share + line.sent - line.received

    return BalanceSheet(lines=ordered, transfers=_transfers(ordered), pool=pool)


def _transfers(lines: list[PartnerLine]) -> list[Transfer]:
    """Bakiyeyi sıfırlayacak ödemeler: borçlulardan alacaklılara."""
    debtors = sorted(([l.user, -l.balance] for l in lines if l.balance < 0), key=lambda x: -x[1])
    creditors = sorted(([l.user, l.balance] for l in lines if l.balance > 0), key=lambda x: -x[1])
    out: list[Transfer] = []
    di = ci = 0
    while di < len(debtors) and ci < len(creditors):
        amount = min(debtors[di][1], creditors[ci][1])
        if amount > 0:
            out.append(Transfer(debtors[di][0], creditors[ci][0], amount))
        debtors[di][1] -= amount
        creditors[ci][1] -= amount
        if debtors[di][1] == 0:
            di += 1
        if creditors[ci][1] == 0:
            ci += 1
    return out
