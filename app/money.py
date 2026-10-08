"""Para tutarları: veritabanında kuruş (tam sayı) olarak tutulur, kayan nokta yok."""
from __future__ import annotations

import re


class AmountError(ValueError):
    pass


_UNIT = re.compile(r"^₺|(₺|tl|try)$", re.IGNORECASE)
_GROUPED = re.compile(r"[1-9][0-9]{0,2}(\.[0-9]{3})+")
_EXAMPLE = "Tutar anlaşılamadı. Örnek: 1.250,50"


def parse_amount(text: str | None) -> int:
    """Kullanıcının yazdığı tutarı kuruşa çevirir.

    Türkçe yazım esas alınır: virgül ondalık, nokta binliktir.
      "1.250,50" -> 125050     "1250,5" -> 125050     "1250" -> 125000
    Telefon klavyesinden gelen noktalı ondalık da kabul edilir:
      "12.5" -> 1250           "1.250" -> 125000 (binlik)
    Belirsiz ya da bozuk yazımlar ("1,5.", "1.2.3,5", "0.500") tahmin edilmez, reddedilir.
    """
    if text is None:
        raise AmountError("Tutar girin.")
    s = "".join(str(text).split())[:40]
    s = _UNIT.sub("", _UNIT.sub("", s))
    if not s:
        raise AmountError("Tutar girin.")
    if not re.fullmatch(r"[0-9.,]+", s) or not s.isascii():
        raise AmountError("Tutar yalnızca rakam, nokta ve virgül içerebilir.")

    if "," in s:
        if s.count(",") > 1:
            raise AmountError("Tutarda birden fazla virgül var.")
        whole, frac = s.split(",")
        if "." in frac:
            raise AmountError(_EXAMPLE)
        if "." in whole:
            if not _GROUPED.fullmatch(whole):
                raise AmountError(_EXAMPLE)
            whole = whole.replace(".", "")
    elif "." in s:
        if _GROUPED.fullmatch(s):
            whole, frac = s.replace(".", ""), ""
        elif s.count(".") == 1:
            whole, frac = s.split(".")
        else:
            raise AmountError(_EXAMPLE)
    else:
        whole, frac = s, ""

    if len(frac) > 2:
        raise AmountError("Kuruş hanesi en fazla iki basamak olabilir.")
    if not whole and not frac:
        raise AmountError("Tutar girin.")
    if len(whole) > 12:
        raise AmountError("Tutar çok büyük görünüyor, kontrol edin.")
    kurus = int(whole or "0") * 100 + int((frac + "00")[:2])
    if kurus <= 0:
        raise AmountError("Tutar sıfırdan büyük olmalı.")
    if kurus > 100_000_000_000:  # 1 milyar TL üstü muhtemelen yazım hatası
        raise AmountError("Tutar çok büyük görünüyor, kontrol edin.")
    return kurus


def format_number(kurus: int | None) -> str:
    """125050 -> '1.250,50' (işaretsiz biçim; eksi için gerçek eksi işareti)."""
    kurus = int(kurus or 0)
    sign = "−" if kurus < 0 else ""
    lira, k = divmod(abs(kurus), 100)
    grouped = f"{lira:,}".replace(",", ".")
    return f"{sign}{grouped},{k:02d}"


def format_try(kurus: int | None) -> str:
    return f"{format_number(kurus)} ₺"


def format_input(kurus: int | None) -> str:
    """Form alanına geri yazmak için: binlik ayraçsız, virgüllü."""
    if not kurus:
        return ""
    lira, k = divmod(abs(int(kurus)), 100)
    return f"{lira},{k:02d}"


def format_compact(kurus: int | None) -> str:
    """Grafik eksenleri için kısa yazım: 12.500 ₺ -> '12,5 bin', 1.200.000 ₺ -> '1,2 mn'."""
    lira = abs(int(kurus or 0)) / 100
    sign = "−" if (kurus or 0) < 0 else ""
    if lira >= 1_000_000:
        txt = f"{lira / 1_000_000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " mn"
    elif lira >= 1_000:
        txt = f"{lira / 1_000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " bin"
    else:
        txt = f"{lira:.0f}"
    return sign + txt


TRY = "TRY"
EUR = "EUR"
CURRENCIES = {TRY: "₺", EUR: "€"}
RATE_SCALE = 10_000


def format_money(kurus: int | None, currency: str = TRY) -> str:
    return f"{format_number(kurus)} {CURRENCIES.get(currency, currency)}"


def parse_rate(text: str | None) -> int:
    s = "".join(str(text or "").split())[:20].replace(",", ".")
    if not re.fullmatch(r"[0-9]+(\.[0-9]{1,4})?", s):
        raise ValueError("Kuru 57,2034 gibi yazın.")
    whole, _, frac = s.partition(".")
    value = int(whole) * RATE_SCALE + int((frac + "0000")[:4])
    if not (RATE_SCALE // 100 <= value <= 10_000 * RATE_SCALE):
        raise ValueError("Kur gerçekçi görünmüyor, kontrol edin.")
    return value


def format_rate(value: int | None) -> str:
    return f"{(value or 0) / RATE_SCALE:.4f}".replace(".", ",")
