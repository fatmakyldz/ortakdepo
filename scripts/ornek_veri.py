"""Deneme amaçlı örnek veri üretir. GERÇEK DEFTERDE ÇALIŞTIRMAYIN.

Kullanım (boş bir veri klasörüyle):
    DATA_DIR=./deneme-veri python scripts/ornek_veri.py
    DATA_DIR=./deneme-veri uvicorn app.main:app
Giriş: fatma@example.com / deneme-1234   (diğer ortak: kerem@example.com / deneme-1234)
"""
from __future__ import annotations

import random
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import GELIR, GIDER, SIRKET_ODEDI, Category, ExchangeRate, FixedExpense, PartnerPayment, Receipt, Transaction, User  # noqa: E402
from app.money import EUR  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services import fixed  # noqa: E402
from app.timeutil import add_months, clamp_day, today  # noqa: E402


def fake_receipt(title: str, amount: int, key: str) -> tuple[str, str]:
    """Fiş görünümlü basit bir görsel üretir."""
    rel_dir = "ornek"
    folder = settings.upload_dir / rel_dir
    folder.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (600, 820), (250, 250, 247))
    d = ImageDraw.Draw(img)
    d.text((40, 40), title.upper(), fill=(30, 30, 30))
    for i in range(9):
        d.line((40, 120 + i * 52, 560, 120 + i * 52), fill=(205, 205, 200), width=2)
        d.rectangle((40, 138 + i * 52, 40 + random.randint(140, 360), 150 + i * 52), fill=(120, 120, 120))
    d.text((40, 640), f"TOPLAM  {amount / 100:,.2f} TL", fill=(20, 20, 20))
    img.save(folder / f"{key}.jpg", "JPEG", quality=80)
    thumb = img.copy()
    thumb.thumbnail((480, 480))
    thumb.save(folder / f"{key}_k.jpg", "JPEG", quality=76)
    return f"{rel_dir}/{key}.jpg", f"{rel_dir}/{key}_k.jpg"


def main() -> None:
    init_db()
    random.seed(7)
    with SessionLocal() as db:
        if db.query(User).count():
            sys.exit("Bu veri klasöründe zaten kullanıcı var; örnek veri yalnızca boş deftere yazılır.")
        fatma = User(name="Fatma", email="fatma@example.com", password_hash=hash_password("deneme-1234"))
        kerem = User(name="Kerem", email="kerem@example.com", password_hash=hash_password("deneme-1234"))
        db.add_all([fatma, kerem])
        db.commit()
        cat = {c.name: c.id for c in db.query(Category)}
        t = today()

        plan = [  # (kategori, alt, üst, olasılık, açıklamalar)
            ("Yakıt", 2800, 6400, 0.75, ["34 ABC 123 depo", "34 DEF 456 depo", "Mazot, şantiye"]),
            ("Yevmiye", 1800, 3600, 0.6, ["2 işçi", "Operatör", "3 işçi"]),
            ("Yemek", 350, 1100, 0.85, ["Öğle", "Şantiye yemeği", "Akşam"]),
            ("Bakım / Onarım", 1500, 14000, 0.07, ["Lastik", "Yağ bakımı", "Hidrolik hortum"]),
            ("Ek gider", 150, 1900, 0.2, ["Otopark", "Köprü geçişi", "Kırtasiye", "Halat"]),
        ]
        n = 0
        for back in range(330, -1, -1):
            day = t - timedelta(days=back)
            if day.weekday() == 6:
                continue
            season = 1.0 + 0.25 * ((day.month % 12) in (4, 5, 6, 7, 8, 9))
            for name, lo, hi, p, notes in plan:
                if random.random() > p:
                    continue
                amount = int(random.randint(lo, hi) * season) * 100 + random.choice([0, 0, 50, 90])
                payer = random.choices([fatma.id, kerem.id, None], [5, 4, 2])[0]
                tx = Transaction(kind=GIDER, day=day, amount=amount, category_id=cat[name],
                                 partner_id=payer, description=random.choice(notes),
                                 created_by_id=payer or fatma.id)
                if back < 12 and random.random() < 0.8:
                    n += 1
                    path, thumb = fake_receipt(name, amount, f"fis{n}")
                    tx.receipts.append(Receipt(path=path, thumb_path=thumb, original_name="fis.jpg",
                                               content_type="image/jpeg", size=0))
                db.add(tx)
            if random.random() < 0.62:
                amount = int(random.randint(9000, 24000) * season) * 100
                taker = random.choices([fatma.id, kerem.id, None], [2, 2, 6])[0]
                db.add(Transaction(kind=GELIR, day=day, amount=amount, category_id=cat["İş geliri"],
                                   partner_id=taker, description=random.choice(
                                       ["Hafriyat, Yılmaz İnşaat", "Nakliye", "Günlük kiralama", "Hakediş"]),
                                   created_by_id=taker or kerem.id))
        db.commit()

        # Leasing: geçmiş aylar ödenmiş, bu ayınki birkaç gün içinde
        due = t + timedelta(days=2)
        for back in range(10, 0, -1):
            y, m = add_months(due.year, due.month, -back)
            d = clamp_day(y, m, due.day)
            db.add(Transaction(kind=GIDER, day=d, amount=42_750_00, category_id=cat["Leasing"],
                               partner_id=None, description="Ekskavatör leasing (geçmiş taksit)",
                               created_by_id=fatma.id))
        db.add(FixedExpense(name="Ekskavatör leasing", amount=950_00, currency=EUR, due_day=due.day, first_due=due,
                            total_count=26, category_id=cat["Leasing"], remind_days=5,
                            note="Sözleşme 2025/1184, aylık 950 €"))
        db.add(ExchangeRate(currency=EUR, day=t, value=572034, source="tcmb"))
        late = t - timedelta(days=3)
        db.add(FixedExpense(name="Depo kirası", amount=15_000_00, due_day=late.day, first_due=late,
                            total_count=None, category_id=cat["Ek gider"], remind_days=3))
        db.add(PartnerPayment(day=t - timedelta(days=40), user_id=fatma.id, direction=SIRKET_ODEDI,
                              amount=60_000_00, note="Havale"))
        db.commit()
        fixed.ensure_installments(db)
    print("Örnek veri yazıldı:", settings.data_dir)


if __name__ == "__main__":
    main()
