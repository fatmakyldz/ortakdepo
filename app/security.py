from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import Depends, Request
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse, RedirectResponse

from .db import get_db
from .models import User

_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iters, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


class LoginRequired(Exception):
    pass


# Var olmayan e-postada da aynı süre harcansın diye doğrulanacak sahte özet
DUMMY_HASH = hash_password("yok-boyle-bir-sifre")


def session_stamp(user: User) -> str:
    """Oturumu şifreye bağlar: şifre değişince eski oturum çerezleri geçersiz kalır."""
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def start_session(request: Request, user: User) -> None:
    request.session.clear()
    request.session["uid"] = user.id
    request.session["damga"] = session_stamp(user)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("uid")
    user = db.get(User, uid) if isinstance(uid, int) else None
    if user is None or not hmac.compare_digest(
        str(request.session.get("damga", "")), session_stamp(user)
    ):
        request.session.clear()
        raise LoginRequired()
    request.state.user = user
    from .services import fixed  # döngüsel içe aktarmayı önlemek için burada

    request.state.alert_count = len(fixed.alerts(db))
    return user


class LoginThrottle:
    """Aynı adresten art arda hatalı girişleri sınırlar (bellekte, tek süreç)."""

    def __init__(self, limit: int = 8, window: int = 15 * 60):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        q = self._hits[key]
        cutoff = time.monotonic() - self.window
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        return len(self._prune(key)) >= self.limit

    def fail(self, key: str) -> None:
        if len(self._hits) > 5000:  # bellek sınırı: süresi dolmuş adresleri at
            for k in [k for k in self._hits if not self._prune(k)]:
                self._hits.pop(k, None)
        self._prune(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


login_throttle = LoginThrottle()


def client_ip(request: Request) -> str:
    # Ters vekil arkasında gerçek adresi uvicorn'un --proxy-headers seçeneği doldurur;
    # başlığı burada elle okumuyoruz ki dışarıdan sahte adresle sınır aşılamasın.
    return request.client.host if request.client else "?"


OPEN_POST_PATHS = {"/giris", "/kurulum", "/cikis"}


class SameOriginMiddleware(BaseHTTPMiddleware):
    """Başka siteden gelen form gönderimlerini reddeder (CSRF koruması).

    Oturum çerezi SameSite=Lax olduğu için tarayıcı zaten çapraz site POST'larda
    çerezi göndermez; bu katman Origin başlığını da doğrulayan ikinci kilittir.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin != "null":
                host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
                if urlsplit(origin).netloc.lower() != host.split(",")[0].strip().lower():
                    return PlainTextResponse("İstek başka bir siteden geldi.", status_code=403)
            elif origin == "null":
                return PlainTextResponse("İstek başka bir siteden geldi.", status_code=403)
            # Giriş yapmamış birinin gönderdiği form gövdesi (ör. büyük dosyalar) hiç okunmasın
            if request.url.path not in OPEN_POST_PATHS and not request.session.get("uid"):
                return RedirectResponse("/giris", status_code=303)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'",
        )
        return response
