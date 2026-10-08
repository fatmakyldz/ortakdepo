"""Döviz kuru: TCMB günlük bülteninden döviz satış kuru, elle giriş ile ezilebilir."""
from __future__ import annotations

import logging
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ExchangeRate
from ..money import EUR, RATE_SCALE
from ..timeutil import now, today

log = logging.getLogger("ortakdefter.kur")

TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
TCMB = "tcmb"
ELLE = "elle"
RETRY_SECONDS = 3600


class RateError(RuntimeError):
    pass


@dataclass
class Quote:
    currency: str
    day: date
    value: int


def parse_tcmb(xml_text: str, currency: str = EUR) -> Quote:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RateError("TCMB kur dosyası okunamadı.") from exc
    try:
        day = datetime.strptime(root.get("Tarih", ""), "%d.%m.%Y").date()
    except ValueError as exc:
        raise RateError("TCMB kur dosyasında bülten tarihi yok.") from exc
    for cur in root.findall("Currency"):
        if cur.get("CurrencyCode") != currency:
            continue
        raw = (cur.findtext("ForexSelling") or "").strip()
        unit_raw = (cur.findtext("Unit") or "1").strip()
        try:
            unit = int(unit_raw or 1)
            value = round(float(raw) * RATE_SCALE / unit)
        except ValueError:
            break
        if value > 0:
            return Quote(currency, day, value)
        break
    raise RateError(f"TCMB kur dosyasında {currency} satış kuru yok.")


def fetch_tcmb(currency: str = EUR) -> Quote:
    req = urllib.request.Request(TCMB_URL, headers={"User-Agent": "OrtakDefter/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read(512_000).decode("utf-8", "replace")
    except (OSError, ValueError) as exc:
        raise RateError(f"TCMB'ye ulaşılamadı: {exc}") from exc
    return parse_tcmb(body, currency)


def latest(db: Session, currency: str = EUR) -> ExchangeRate | None:
    return db.scalar(
        select(ExchangeRate)
        .where(ExchangeRate.currency == currency)
        .order_by(ExchangeRate.day.desc(), (ExchangeRate.source == ELLE).desc(), ExchangeRate.id.desc())
        .limit(1)
    )


def save(db: Session, quote: Quote, source: str) -> ExchangeRate:
    row = db.scalar(
        select(ExchangeRate).where(
            ExchangeRate.currency == quote.currency,
            ExchangeRate.day == quote.day,
            ExchangeRate.source == source,
        )
    )
    if row is None:
        row = ExchangeRate(currency=quote.currency, day=quote.day, source=source)
        db.add(row)
    row.value = quote.value
    row.fetched_at = now().replace(tzinfo=None)
    db.commit()
    return row


_last_try: datetime | None = None


def refresh(db: Session, currency: str = EUR, *, force: bool = False) -> ExchangeRate | None:
    global _last_try
    current = latest(db, currency)
    if not force:
        if not settings.rates_enabled:
            return current
        if current is not None and current.day >= today():
            return current
        moment = now()
        if _last_try is not None and (moment - _last_try).total_seconds() < RETRY_SECONDS:
            return current
        _last_try = moment
    try:
        quote = fetch_tcmb(currency)
    except RateError as exc:
        log.warning("%s", exc)
        if force:
            raise
        return current
    save(db, quote, TCMB)
    return latest(db, currency)


def convert(amount: int, value: int) -> int:
    return (amount * value + RATE_SCALE // 2) // RATE_SCALE
