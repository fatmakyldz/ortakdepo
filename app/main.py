from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
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
