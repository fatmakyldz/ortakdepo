import pytest

from app.money import AmountError, format_compact, format_input, format_number, format_try, parse_amount


@pytest.mark.parametrize("text,kurus", [
    ("1250", 125000),
    ("1250,5", 125050),
    ("1250,50", 125050),
    ("1.250,50", 125050),
    ("1.250", 125000),          # nokta + 3 hane: binlik
    ("12.5", 1250),             # telefon klavyesi: ondalık
    ("12.50", 1250),
    ("1.234.567", 123456700),
    ("1.234.567,89", 123456789),
    ("0,75", 75),
    (",5", 50),
    (" 2.000 ₺ ", 200000),
    ("350 TL", 35000),
])
def test_parse_amount(text, kurus):
    assert parse_amount(text) == kurus


@pytest.mark.parametrize("text", [
    "", None, "abc", "0", "0,00", "1,2,3", "1,234", "1.25.0", "-50", "12,345",
    "1,5.", "12,.", "1.2.3,5", "0.500", "0.001", "12tl50", "1" * 5000, "²", "1.2345,00", "01.250",
])
def test_parse_amount_rejects(text):
    with pytest.raises(AmountError):
        parse_amount(text)


def test_format():
    assert format_number(125050) == "1.250,50"
    assert format_try(5) == "0,05 ₺"
    assert format_try(-123456789) == "−1.234.567,89 ₺"
    assert format_input(125050) == "1250,50"
    assert parse_amount(format_input(987654321)) == 987654321
    assert format_compact(1250000) == "12,5 bin"
    assert format_compact(120000000) == "1,2 mn"
