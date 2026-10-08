"""Aylık rapor ve dışa aktarma."""
from __future__ import annotations

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import current_user
from ..services import charts, exports, reports
from ..timeutil import add_months, fmt_month, month_bounds, parse_date, parse_month, today
from ..web import flash, redirect, render

router = APIRouter()

def trend_chart(points: list[reports.TrendPoint], current_key: str) -> dict:
    return charts.column_chart([
        charts.Column(p.label, fmt_month(p.year, p.month), p.income, p.expense, p.key == current_key)
        for p in points
    ])


@router.get("/rapor")
def report_page(
    request: Request, ay: str = "",
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    year, month = parse_month(ay)
    rep = reports.month_report(db, year, month)
    py, pm = add_months(year, month, -1)
    ny, nm = add_months(year, month, 1)
    prev_income, prev_expense = reports.totals(db, *month_bounds(py, pm))
    points = reports.trend(db, year, month, 12)
    t = today()
    return render(request, "report.html", {
        "rep": rep,
        "month_label": fmt_month(year, month),
        "prev_label": fmt_month(py, pm),
        "prev_net": prev_income - prev_expense,
        "has_prev": bool(prev_income or prev_expense),
        "ay": f"{year}-{month:02d}",
        "prev_ay": f"{py}-{pm:02d}",
        "next_ay": f"{ny}-{nm:02d}",
        "is_current_month": (year, month) == (t.year, t.month),
        "chart": trend_chart(points, f"{year}-{month:02d}"),
        "points": points,
        "max_cat": max([c.amount for c in rep.expense_categories] + [1]),
        "year_start": date(year, 1, 1),
    })


def _range(request: Request, bas: str, bit: str) -> tuple[date, date] | None:
    start, end = parse_date(bas), parse_date(bit)
    if not start or not end:
        flash(request, "Döküm için başlangıç ve bitiş tarihini seçin.", "hata")
        return None
    if start > end:
        start, end = end, start
    return start, end


def _download(content: bytes, filename: str, media_type: str) -> Response:
    return Response(
        content, media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-store",
        },
    )


@router.get("/rapor/excel")
def export_xlsx(
    request: Request, bas: str = "", bit: str = "",
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    rng = _range(request, bas, bit)
    if rng is None:
        return redirect("/rapor")
    start, end = rng
    return _download(
        exports.build_xlsx(db, start, end),
        f"defter_{start.isoformat()}_{end.isoformat()}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/rapor/csv")
def export_csv(
    request: Request, bas: str = "", bit: str = "",
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    rng = _range(request, bas, bit)
    if rng is None:
        return redirect("/rapor")
    start, end = rng
    return _download(
        exports.build_csv(db, start, end),
        f"defter_{start.isoformat()}_{end.isoformat()}.csv",
        "text/csv; charset=utf-8",
    )
