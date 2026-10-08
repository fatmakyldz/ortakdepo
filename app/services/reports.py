"""Dönem özetleri: aylık kâr/zarar, kategori dağılımı, günlük döküm, 12 aylık seyir."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import GELIR, GIDER, Category, FixedExpense, Installment, Transaction, User
from ..timeutil import AYLAR_KISA, add_months, month_bounds


@dataclass
class CategoryRow:
    name: str
    amount: int
    count: int
    pct: float  # toplam içindeki pay, 0-100


@dataclass
class PartnerRow:
    name: str
    paid: int = 0
    collected: int = 0


@dataclass
class DayRow:
    day: date
    income: int = 0
    expense: int = 0
    count: int = 0

    @property
    def net(self) -> int:
        return self.income - self.expense


@dataclass
class PeriodReport:
    start: date
    end: date
    income: int = 0
    expense: int = 0
    expense_categories: list[CategoryRow] = field(default_factory=list)
    income_categories: list[CategoryRow] = field(default_factory=list)
    partners: list[PartnerRow] = field(default_factory=list)
    days: list[DayRow] = field(default_factory=list)
    unpaid_fixed: int = 0
    unpaid_fixed_count: int = 0
    count: int = 0

    @property
    def net(self) -> int:
        return self.income - self.expense

    @property
    def net_after_fixed(self) -> int:
        return self.net - self.unpaid_fixed


def totals(db: Session, start: date, end: date) -> tuple[int, int]:
    """(gelir, gider) toplamları."""
    rows = dict(
        db.execute(
            select(Transaction.kind, func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.day.between(start, end))
            .group_by(Transaction.kind)
        ).all()
    )
    return rows.get(GELIR, 0), rows.get(GIDER, 0)


def _categories(db: Session, kind: str, start: date, end: date, total: int) -> list[CategoryRow]:
    rows = db.execute(
        select(
            func.coalesce(Category.name, "Kategorisiz"),
            func.sum(Transaction.amount),
            func.count(Transaction.id),
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.kind == kind, Transaction.day.between(start, end))
        .group_by(Category.id)
        .order_by(func.sum(Transaction.amount).desc())
    ).all()
    return [
        CategoryRow(name, amount, count, (amount / total * 100) if total else 0.0)
        for name, amount, count in rows
    ]


def period_report(db: Session, start: date, end: date) -> PeriodReport:
    income, expense = totals(db, start, end)
    rep = PeriodReport(start=start, end=end, income=income, expense=expense)
    rep.expense_categories = _categories(db, GIDER, start, end, expense)
    rep.income_categories = _categories(db, GELIR, start, end, income)

    users = {u.id: u.name for u in db.scalars(select(User).order_by(User.id))}
    prow = {uid: PartnerRow(name) for uid, name in users.items()}
    prow[None] = PartnerRow("Ortak hesap")
    for pid, kind, total in db.execute(
        select(Transaction.partner_id, Transaction.kind, func.sum(Transaction.amount))
        .where(Transaction.day.between(start, end))
        .group_by(Transaction.partner_id, Transaction.kind)
    ):
        row = prow.get(pid) or prow[None]
        if kind == GIDER:
            row.paid += total
        else:
            row.collected += total
    rep.partners = [prow[uid] for uid in users] + (
        [prow[None]] if prow[None].paid or prow[None].collected else []
    )

    days: dict[date, DayRow] = {}
    for day, kind, total, cnt in db.execute(
        select(Transaction.day, Transaction.kind, func.sum(Transaction.amount), func.count())
        .where(Transaction.day.between(start, end))
        .group_by(Transaction.day, Transaction.kind)
    ):
        row = days.setdefault(day, DayRow(day))
        row.count += cnt
        if kind == GELIR:
            row.income += total
        else:
            row.expense += total
    rep.days = [days[d] for d in sorted(days, reverse=True)]
    rep.count = sum(d.count for d in rep.days)

    unpaid = db.execute(
        select(func.coalesce(func.sum(Installment.amount), 0), func.count(Installment.id))
        .join(FixedExpense)
        .where(
            Installment.transaction_id.is_(None),
            FixedExpense.is_active,
            Installment.due_date.between(start, end),
        )
    ).one()
    rep.unpaid_fixed, rep.unpaid_fixed_count = unpaid
    return rep


def month_report(db: Session, year: int, month: int) -> PeriodReport:
    return period_report(db, *month_bounds(year, month))


@dataclass
class TrendPoint:
    year: int
    month: int
    income: int
    expense: int

    @property
    def net(self) -> int:
        return self.income - self.expense

    @property
    def label(self) -> str:
        return AYLAR_KISA[self.month]

    @property
    def key(self) -> str:
        return f"{self.year}-{self.month:02d}"


def trend(db: Session, end_year: int, end_month: int, months: int = 12) -> list[TrendPoint]:
    sy, sm = add_months(end_year, end_month, -(months - 1))
    start = date(sy, sm, 1)
    end = month_bounds(end_year, end_month)[1]
    ym = func.strftime("%Y-%m", Transaction.day)
    sums: dict[tuple[str, str], int] = {
        (k, kind): total
        for k, kind, total in db.execute(
            select(ym, Transaction.kind, func.sum(Transaction.amount))
            .where(Transaction.day.between(start, end))
            .group_by(ym, Transaction.kind)
        )
    }
    out = []
    for i in range(months):
        y, m = add_months(sy, sm, i)
        key = f"{y}-{m:02d}"
        out.append(TrendPoint(y, m, sums.get((key, GELIR), 0), sums.get((key, GIDER), 0)))
    return out


def nice_ceiling(value: int) -> int:
    """Grafik ekseninin üst sınırı için değeri 'temiz' bir sayıya yuvarlar (kuruş)."""
    if value <= 0:
        return 100_00
    lira = value / 100
    mag = 10 ** (len(str(int(lira))) - 1)
    for step in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if lira <= step * mag:
            return int(step * mag * 100)
    return int(10 * mag * 100)
