from datetime import date

from app.models import GELIR, GIDER, Category, Settlement, Transaction, User
from app.services import balance
from app.services.balance import split_by_share


def _users(db, share_a=5000, share_b=5000):
    a = User(name="A", email="a@x.co", password_hash="x", share_bp=share_a)
    b = User(name="B", email="b@x.co", password_hash="x", share_bp=share_b)
    db.add_all([a, b])
    db.commit()
    return a, b


def _tx(db, kind, amount, partner=None):
    cat = db.query(Category).filter_by(kind=kind).first()
    db.add(Transaction(kind=kind, day=date(2026, 10, 1), amount=amount,
                       category_id=cat.id, partner_id=partner.id if partner else None))
    db.commit()


def test_split_keeps_every_kurus():
    assert split_by_share(100, [5000, 5000]) == [50, 50]
    assert split_by_share(101, [5000, 5000]) == [51, 50]
    assert split_by_share(100, [3333, 6667]) == [33, 67]
    assert sum(split_by_share(999_999, [3333, 6667])) == 999_999
    assert split_by_share(-101, [5000, 5000]) == [-51, -50]
    assert split_by_share(0, [5000, 5000]) == [0, 0]


def test_expense_paid_by_one_partner(db):
    a, b = _users(db)
    _tx(db, GIDER, 100_00, a)
    sheet = balance.compute(db)
    assert [l.balance for l in sheet.lines] == [50_00, -50_00]
    (t,) = sheet.transfers
    assert (t.from_user.id, t.to_user.id, t.amount) == (b.id, a.id, 50_00)


def test_income_collected_by_one_partner(db):
    a, b = _users(db)
    _tx(db, GELIR, 1000_00, a)
    sheet = balance.compute(db)
    # A parayı aldı; yarısı B'nin hakkı
    assert [l.balance for l in sheet.lines] == [-500_00, 500_00]


def test_shared_account_does_not_affect_balance(db):
    _users(db)
    _tx(db, GIDER, 750_00, None)
    _tx(db, GELIR, 2000_00, None)
    sheet = balance.compute(db)
    assert sheet.settled and all(l.balance == 0 for l in sheet.lines)


def test_settlement_closes_the_balance(db):
    a, b = _users(db)
    _tx(db, GIDER, 300_00, a)
    _tx(db, GIDER, 100_00, b)
    _tx(db, GELIR, 1000_00, b)
    # A: +300; B: 100 - 1000 = -900; havuz -600; pay -300'er
    sheet = balance.compute(db)
    assert [l.balance for l in sheet.lines] == [600_00, -600_00]
    db.add(Settlement(day=date(2026, 10, 2), from_user_id=b.id, to_user_id=a.id, amount=600_00))
    db.commit()
    sheet = balance.compute(db)
    assert sheet.settled and [l.balance for l in sheet.lines] == [0, 0]


def test_uneven_shares_and_zero_sum(db):
    a, b = _users(db, 6000, 4000)
    _tx(db, GIDER, 1000_01, a)
    sheet = balance.compute(db)
    assert sum(l.balance for l in sheet.lines) == 0
    assert sheet.lines[0].fair_share + sheet.lines[1].fair_share == 1000_01
    assert sheet.lines[0].balance == 1000_01 - 600_01  # A payının (%60) üstünü alacaklı
