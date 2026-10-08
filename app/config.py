"""Ortam değişkenlerinden okunan ayarlar. Hepsinin makul bir varsayılanı var."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "evet", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    app_name: str
    data_dir: Path
    secret_key: str
    base_url: str
    https_only: bool
    timezone: ZoneInfo
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_tls: str  # "starttls" | "ssl" | "none"
    reminder_hour: int
    reminders_enabled: bool
    max_upload_mb: int
    setup_key: str

    @property
    def db_path(self) -> Path:
        return self.data_dir / "defter.db"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "fisler"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)


def _secret_key(data_dir: Path) -> str:
    """SECRET_KEY verilmediyse bir kez üretip veri klasöründe saklar.

    Böylece uygulama yeniden başladığında oturumlar düşmez.
    """
    env = os.environ.get("SECRET_KEY", "").strip()
    if env:
        return env
    key_file = data_dir / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key)
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return key


def _base_url() -> str:
    """Sitenin dış adresi. Verilmediyse bulut servisinin kendi bildirdiği adres kullanılır."""
    explicit = os.environ.get("BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    render = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    if render:
        return render.rstrip("/")
    railway = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if railway:
        return f"https://{railway}".rstrip("/")
    fly = os.environ.get("FLY_APP_NAME", "").strip()
    if fly:
        return f"https://{fly}.fly.dev"
    return "http://localhost:8000"


def load_settings() -> Settings:
    data_dir = Path(os.environ.get("DATA_DIR", BASE_DIR / "data")).resolve()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "fisler").mkdir(exist_ok=True)
    except PermissionError:
        raise SystemExit(
            f"Veri klasörüne yazılamıyor: {data_dir}\n"
            "Klasörün sahibi uygulamayı çalıştıran kullanıcı olmalı."
        ) from None
    return Settings(
        app_name=os.environ.get("APP_NAME", "Sezkar Muhasebe"),
        data_dir=data_dir,
        secret_key=_secret_key(data_dir),
        base_url=_base_url(),
        https_only=_bool("HTTPS_ONLY", False),
        timezone=ZoneInfo(os.environ.get("TZ_NAME", "Europe/Istanbul")),
        smtp_host=os.environ.get("SMTP_HOST", "").strip(),
        smtp_port=_int("SMTP_PORT", 587),
        smtp_user=os.environ.get("SMTP_USER", "").strip(),
        smtp_password=os.environ.get("SMTP_PASSWORD", ""),
        smtp_from=os.environ.get("SMTP_FROM", "").strip(),
        smtp_tls=os.environ.get("SMTP_TLS", "starttls").strip().lower(),
        reminder_hour=_int("REMINDER_HOUR", 9),
        reminders_enabled=_bool("REMINDERS_ENABLED", True),
        max_upload_mb=_int("MAX_UPLOAD_MB", 15),
        setup_key=os.environ.get("KURULUM_ANAHTARI", "").strip(),
    )


settings = load_settings()
