"""Şablonlar, ortak bağlam, flash mesajları ve yönlendirme yardımcıları."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import money, timeutil
from .config import settings

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

templates.env.filters.update(
    tl=money.format_try,
    sayi=money.format_number,
    tl_input=money.format_input,
    kisa=money.format_compact,
    tarih=timeutil.fmt_date,
    tarih_kisa=timeutil.fmt_date_short,
    gun_adi=timeutil.fmt_day_name,
)
templates.env.globals.update(app_name=settings.app_name, AYLAR=timeutil.AYLAR)


def _asset_version() -> str:
    try:
        newest = max(p.stat().st_mtime for p in (APP_DIR / "static").rglob("*") if p.is_file())
        return str(int(newest))
    except ValueError:
        return "1"


templates.env.globals["asset_v"] = _asset_version()


def flash(request: Request, text: str, kind: str = "ok") -> None:
    # Mesajlar oturum çerezinde taşınır; çerez şişmesin diye sayı ve uzunluk sınırlı
    items = request.session.setdefault("flash", [])
    if len(items) < 6:
        items.append({"kind": kind, "text": text[:240]})


def render(request: Request, name: str, ctx: dict | None = None, status_code: int = 200):
    context = {
        "user": getattr(request.state, "user", None),
        "alert_count": getattr(request.state, "alert_count", 0),
        "flashes": request.session.pop("flash", []),
        "today": timeutil.today(),
        "path": request.url.path,
    }
    context.update(ctx or {})
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def redirect(url: str, **params) -> RedirectResponse:
    """POST sonrası yönlendirme (303): sayfa yenilenince form tekrar gönderilmez."""
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    if clean:
        url = f"{url}?{urlencode(clean)}"
    return RedirectResponse(url, status_code=303)
