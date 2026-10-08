from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import SessionLocal, init_db
from .models import User
from .routers import auth, dashboard, fixed, partners, reports, settings as settings_router, transactions
from .security import LoginRequired, SameOriginMiddleware, SecurityHeadersMiddleware
from .services import reminders
from .web import APP_DIR, render

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    task = asyncio.create_task(reminders.loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

# Sıra önemli: en son eklenen en dışta çalışır.
app.add_middleware(SameOriginMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="defter_oturum",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.https_only,
)
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

for module in (auth, dashboard, transactions, fixed, partners, reports, settings_router):
    app.include_router(module.router)


@app.exception_handler(LoginRequired)
async def _login_required(request: Request, _exc: LoginRequired):
    with SessionLocal() as db:
        has_users = bool(db.scalar(select(func.count()).select_from(User)))
    return RedirectResponse("/giris" if has_users else "/kurulum", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        title, text = "Sayfa bulunamadı", "Aradığınız kayıt silinmiş ya da adres yanlış olabilir."
    else:
        title, text = "İşlem tamamlanamadı", str(exc.detail)
    if isinstance(exc.detail, str) and exc.status_code == 404 and exc.detail != "Not Found":
        text = exc.detail
    return render(request, "error.html", {"title": title, "text": text}, status_code=exc.status_code)


@app.get("/saglik", include_in_schema=False)
def health():
    return {"durum": "ok"}


# ---- Telefona "uygulama gibi" eklenebilme (PWA)

@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return JSONResponse(
        {
            "name": settings.app_name,
            "short_name": settings.app_name.split()[0][:12] if settings.app_name else "Defter",
            "description": "Günlük gelir, gider ve fiş takibi",
            "lang": "tr",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#ffffff",
            "icons": [
                {"src": "/static/brand/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/brand/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {"src": "/static/brand/icon-maskable-512.png", "sizes": "512x512", "type": "image/png",
                 "purpose": "maskable"},
            ],
            "shortcuts": [
                {"name": "Gider ekle", "url": "/kayitlar/yeni?tur=gider"},
                {"name": "Gelir ekle", "url": "/kayitlar/yeni?tur=gelir"},
            ],
        },
        media_type="application/manifest+json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # Kök dizinden sunulur ki kapsamı tüm site olsun; tarayıcı her seferinde yenisini sorsun
    return FileResponse(
        APP_DIR / "static" / "js" / "sw.js", media_type="text/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Tarayıcıların kendiliğinden istediği adres; sezkar.com'daki dosyanın aynısı
    return FileResponse(
        APP_DIR / "static" / "brand" / "favicon.ico", media_type="image/x-icon",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/cevrimdisi", include_in_schema=False)
def offline(request: Request):
    return render(request, "offline.html")
