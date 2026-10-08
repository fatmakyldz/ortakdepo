"""Şifresini unutan ortağa yeni şifre verir. Sunucuda çalıştırılır.

Kullanım:
    python scripts/sifre_sifirla.py ortak@ornek.com
    docker compose exec defter python scripts/sifre_sifirla.py ortak@ornek.com
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Kullanım: python scripts/sifre_sifirla.py ortak@ornek.com")
    email = sys.argv[1].strip().lower()
    init_db()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            known = ", ".join(u.email for u in db.scalars(select(User)))
            sys.exit(f"{email} bulunamadı. Kayıtlı adresler: {known or 'yok'}")
        new = getpass.getpass("Yeni şifre (en az 8 karakter): ")
        if len(new) < 8:
            sys.exit("Şifre en az 8 karakter olmalı.")
        if new != getpass.getpass("Yeni şifre, tekrar: "):
            sys.exit("Şifreler aynı değil.")
        user.password_hash = hash_password(new)
        db.commit()
        print(f"{user.name} için şifre değişti.")


if __name__ == "__main__":
    main()
