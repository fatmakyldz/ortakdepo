from datetime import date

import pytest

from app.models import ExchangeRate
from app.money import EUR, RATE_SCALE, format_money, format_rate, parse_rate
from app.services import rates

SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date Tarih="07.10.2026" Date="10/07/2026" Bulten_No="2026/189">
  <Currency CrossOrder="0" Kod="USD" CurrencyCode="USD"><Unit>1</Unit><ForexSelling>49.1976</ForexSelling></Currency>
  <Currency CrossOrder="9" Kod="EUR" CurrencyCode="EUR"><Unit>1</Unit><ForexBuying>57.1</ForexBuying><ForexSelling>57.2034</ForexSelling></Currency>
  <Currency CrossOrder="10" Kod="JPY" CurrencyCode="JPY"><Unit>100</Unit><ForexSelling>32.5</ForexSelling></Currency>
</Tarih_Date>"""


def test_parse_tcmb_reads_forex_selling():
    q = rates.parse_tcmb(SAMPLE)
    assert (q.currency, q.day, q.value) == (EUR, date(2026, 10, 7), 572034)
    jpy = rates.parse_tcmb(SAMPLE, "JPY")
    assert jpy.value == 3250


def test_parse_tcmb_rejects_bad_input():
    with pytest.raises(rates.RateError):
        rates.parse_tcmb("<bozuk")
    with pytest.raises(rates.RateError):
        rates.parse_tcmb(SAMPLE, "GBP")


def test_convert_rounds_to_kurus():
    assert rates.convert(1250_00, 572034) == 71504_25
    assert rates.convert(1, 572034) == 57
    assert rates.convert(0, 572034) == 0


def test_rate_text_round_trip():
    assert parse_rate("57,2034") == 572034
    assert parse_rate("57.2") == 572000
    assert parse_rate("57") == 57 * RATE_SCALE
    assert format_rate(572034) == "57,2034"
    assert format_money(1250_00, EUR) == "1.250,00 €"
    for bad in ["", "abc", "0", "-5", "1.2.3", "100000"]:
        with pytest.raises(ValueError):
            parse_rate(bad)


def test_refresh_saves_and_manual_wins(db, monkeypatch):
    monkeypatch.setattr(rates, "fetch_tcmb", lambda currency=EUR: rates.Quote(EUR, date(2026, 10, 8), 572034))
    row = rates.refresh(db, force=True)
    assert row.value == 572034 and row.source == rates.TCMB
    assert db.query(ExchangeRate).count() == 1

    rates.save(db, rates.Quote(EUR, date(2026, 10, 8), 580000), rates.ELLE)
    assert rates.latest(db).value == 580000

    rates.refresh(db, force=True)
    assert rates.latest(db).value == 580000 and db.query(ExchangeRate).count() == 2


def test_refresh_keeps_last_known_rate_when_tcmb_is_down(db, monkeypatch):
    rates.save(db, rates.Quote(EUR, date(2026, 10, 1), 560000), rates.TCMB)

    def boom(currency=EUR):
        raise rates.RateError("kapalı")

    monkeypatch.setattr(rates, "fetch_tcmb", boom)
    assert rates.refresh(db).value == 560000
    with pytest.raises(rates.RateError):
        rates.refresh(db, force=True)
