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
from ..services import exports, reports
from ..timeutil import add_months, fmt_month, month_bounds, parse_date, parse_month, today
from ..web import flash, redirect, render

router = APIRouter()

# Grafik ölçüleri (SVG kullanıcı birimi)
W, H = 720, 250
PAD_L, PAD_R, PAD_T, PAD_B = 58, 8, 14, 30
BAR_W, GAP = 15, 2


def _bar_path(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Üstü yuvarlak, tabanı düz sütun."""
    if h <= 0:
        return ""
    r = min(r, h, w / 2)
    return (
        f"M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z"
    )


def trend_chart(points: list[reports.TrendPoint]) -> dict:
    top = reports.nice_ceiling(max([p.income for p in points] + [p.expense for p in points] + [0]))
    plot_w, plot_h = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    band = plot_w / len(points)
    base = PAD_T + plot_h

    def y_of(v: int) -> float:
        return base - (v / top) * plot_h

    groups = []
    for i, p in enumerate(points):
        cx = PAD_L + band * i + band / 2
        x_inc = cx - GAP / 2 - BAR_W
        x_exp = cx + GAP / 2
        groups.append({
            "point": p,
            "cx": round(cx, 1),
            "band_x": round(PAD_L + band * i, 1),
            "band_w": round(band, 1),
            "income_path": _bar_path(x_inc, y_of(p.income), BAR_W, base - y_of(p.income)),
            "expense_path": _bar_path(x_exp, y_of(p.expense), BAR_W, base - y_of(p.expense)),
            "month_label": fmt_month(p.year, p.month),
        })
    ticks = [{"y": round(y_of(top * k // 4), 1), "value": top * k // 4} for k in range(5)]
    return {
        "w": W, "h": H, "base": base, "pad_l": PAD_L, "pad_r": PAD_R, "pad_t": PAD_T,
        "plot_h": plot_h, "groups": groups, "ticks": ticks,
        "empty": all(p.income == 0 and p.expense == 0 for p in points),
    }


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
        "chart": trend_chart(points),
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


@router.get("/rapor/pdf")
def export_pdf(
    request: Request, bas: str = "", bit: str = "",
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    rng = _range(request, bas, bit)
    if rng is None:
        return redirect("/rapor")
    start, end = rng
    return _download(
        exports.build_pdf(db, start, end),
        f"defter_{start.isoformat()}_{end.isoformat()}.pdf",
        "application/pdf",
    )
