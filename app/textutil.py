"""Kullanıcı metni ve form değerleri için küçük yardımcılar."""
from __future__ import annotations

import re
from datetime import date, timedelta

from .timeutil import parse_date, today

_CONTROL = re.compile(r"[\x00-\x08\x0e-\x1b\x7f]")  # satır sonu, sekme vb. boşluk sayılır
_TR_LOWER = str.maketrans({"I": "ı", "İ": "i"})

MIN_DATE = date(2000, 1, 1)


def clean_text(text: str | None, limit: int = 300) -> str:
    """Denetim karakterlerini atar, satır sonlarını ve art arda boşlukları tek boşluğa indirir.

    Böylece ad ve açıklamalar e-posta başlığını ya da Excel dökümünü bozamaz.
    """
    return " ".join(_CONTROL.sub("", text or "").split())[:limit]


def name_key(text: str) -> str:
    """Büyük/küçük harf duyarsız karşılaştırma anahtarı (Türkçe I/İ dahil)."""
    return clean_text(text).translate(_TR_LOWER).casefold()


def to_id(raw: object) -> int | None:
    """Formdan gelen kimlik: yalnızca 1-9 haneli düz rakam, aksi halde None."""
    s = str(raw or "").strip()
    if 1 <= len(s) <= 9 and s.isascii() and s.isdigit():
        return int(s)
    return None


def to_int(raw: object, default: int, low: int, high: int) -> int:
    value = to_id(raw) if str(raw or "").strip() != "0" else 0
    if value is None:
        value = default
    return max(low, min(value, high))


def entry_date(raw: str | None) -> tuple[date | None, str | None]:
    """Kayıt tarihi: (tarih, hata). Gelecek günler ve 2000 öncesi kabul edilmez.

    Alt sınır, yıl alanına "26" yazınca tarayıcının gönderdiği 0026 gibi değerleri yakalar.
    """
    day = parse_date(raw)
    if day is None:
        return None, "Tarih seçin."
    if day > today() + timedelta(days=1):
        return None, "Tarih ileri bir gün olamaz."
    if day < MIN_DATE:
        return None, "Tarihin yılını kontrol edin; 2000 öncesi kabul edilmiyor."
    return day, None
