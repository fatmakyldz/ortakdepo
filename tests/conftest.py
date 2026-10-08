import os
import sys
import tempfile
from pathlib import Path

# Uygulama içe aktarılmadan önce: testler kendi boş veri klasöründe çalışsın
_tmp = tempfile.mkdtemp(prefix="defter-test-")
os.environ["DATA_DIR"] = _tmp
os.environ["SECRET_KEY"] = "test-anahtari"
os.environ["SMTP_HOST"] = ""
os.environ["REMINDERS_ENABLED"] = "0"
os.environ["REMINDER_TO"] = ""
os.environ["RATES_ENABLED"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import login_throttle  # noqa: E402


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    from app.services import rates

    def offline(currency="EUR"):
        raise rates.RateError("test ortamında ağ yok")

    monkeypatch.setattr(rates, "fetch_tcmb", offline)


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    init_db()
    login_throttle._hits.clear()
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def client(db):
    with TestClient(app, base_url="http://testserver") as c:
        yield c


@pytest.fixture()
def logged_in(client):
    r = client.post("/kurulum", data={
        "ad1": "Fatma", "eposta1": "fatma@example.com", "sifre1": "gizli-sifre-1",
        "ad2": "Kerem", "eposta2": "kerem@example.com", "sifre2": "gizli-sifre-2",
    }, follow_redirects=False)
    assert r.status_code == 303
    return client
