from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import GELIR, GIDER, Transaction, User
from ..security import current_user
from ..services import balance, fixed, reports
from ..timeutil import fmt_month, today
from ..web import render
from .transactions import group_by_day, partners

router = APIRouter()


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    on = today()
    fixed.ensure_installments(db, on)

    todays = db.scalars(
        select(Transaction).where(Transaction.day == on).order_by(Transaction.id)
    ).unique().all()
    recent = db.scalars(
        select(Transaction).where(Transaction.day < on)
        .order_by(Transaction.day.desc(), Transaction.id.desc()).limit(8)
    ).unique().all()

    return render(request, "dashboard.html", {
        "todays": todays,
        "today_income": sum(t.amount for t in todays if t.kind == GELIR),
        "today_expense": sum(t.amount for t in todays if t.kind == GIDER),
        "recent_groups": group_by_day(recent),
        "alerts": fixed.alerts(db, on),
        "month": reports.month_report(db, on.year, on.month),
        "month_label": fmt_month(on.year, on.month),
        "sheet": balance.compute(db),
        "partners": partners(db),
    })
