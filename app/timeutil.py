from __future__ import annotations

import calendar
from datetime import date, datetime

from .config import settings

AYLAR = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]
AYLAR_KISA = ["", "Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def now() -> datetime:
    return datetime.now(settings.timezone)


def today() -> date:
    return now().date()


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def clamp_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def parse_month(text: str | None, fallback: date | None = None) -> tuple[int, int]:
    """'2026-10' -> (2026, 10). Geçersizse içinde bulunulan ay."""
    fb = fallback or today()
    try:
        y, m = (text or "").split("-")
        y, m = int(y), int(m)
        if 2000 <= y <= 2100 and 1 <= m <= 12:
            return y, m
    except ValueError:
        pass
    return fb.year, fb.month


def parse_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


def fmt_date(d: date | None) -> str:
    return f"{d.day} {AYLAR[d.month]} {d.year}" if d else ""


def fmt_date_short(d: date | None) -> str:
    return f"{d.day} {AYLAR_KISA[d.month]}" if d else ""


def fmt_day_name(d: date | None) -> str:
    return GUNLER[d.weekday()] if d else ""


def fmt_month(year: int, month: int) -> str:
    return f"{AYLAR[month]} {year}"
