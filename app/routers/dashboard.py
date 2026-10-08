from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import GELIR, GIDER, Transaction, User
from ..security import current_user
from ..services import balance, charts, fixed, reports
from ..timeutil import AYLAR, add_months, fmt_date, fmt_month, month_bounds, today
from ..web import render
from .transactions import group_by_day, partners

router = APIRouter()

DAYS = 14


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    on = today()
    fixed.ensure_installments(db, on)

    todays = db.scalars(
        select(Transaction).where(Transaction.day == on).order_by(Transaction.id.desc())
    ).unique().all()
    recent = db.scalars(
        select(Transaction).where(Transaction.day < on)
        .order_by(Transaction.day.desc(), Transaction.id.desc()).limit(6)
    ).unique().all()

    month = reports.month_report(db, on.year, on.month)
    py, pm = add_months(on.year, on.month, -1)
    prev_income, prev_expense = reports.totals(db, *month_bounds(py, pm))

    series = reports.daily_series(db, on, DAYS)
    columns = [
        charts.Column(
            # ay değişen günde ve ilk sütunda ay adı da yazılır: "28", "29", "1 Eki"
            f"{p.day.day} {AYLAR[p.day.month][:3]}" if (i == 0 or p.day.day == 1) else str(p.day.day),
            fmt_date(p.day), p.income, p.expense, p.day == on,
        )
        for i, p in enumerate(series)
    ]

    return render(request, "dashboard.html", {
        "todays": todays,
        "today_income": sum(t.amount for t in todays if t.kind == GELIR),
        "today_expense": sum(t.amount for t in todays if t.kind == GIDER),
        "recent_groups": group_by_day(recent),
        "alerts": fixed.alerts(db, on),
        "month": month,
        "month_label": fmt_month(on.year, on.month),
        "prev_label": AYLAR[pm],
        "prev_income": prev_income,
        "prev_expense": prev_expense,
        "top_cats": reports.top_categories(month.expense_categories, 5),
        "max_cat": max([c.amount for c in month.expense_categories] + [1]),
        "chart": charts.column_chart(columns, width=560, height=230, bar=11),
        "series": series,
        "days": DAYS,
        "sheet": balance.compute(db),
        "partners": partners(db),
    })
