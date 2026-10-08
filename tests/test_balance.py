from datetime import date

from app.models import GELIR, GIDER, ORTAK_YATIRDI, SIRKET_ODEDI, Category, PartnerPayment, Transaction, User
from app.services import balance


def _users(db):
    a = User(name="A", email="a@x.co", password_hash="x")
    b = User(name="B", email="b@x.co", password_hash="x")
    db.add_all([a, b])
    db.commit()
    return a, b


def _tx(db, kind, amount, partner=None):
    cat = db.query(Category).filter_by(kind=kind).first()
    db.add(Transaction(kind=kind, day=date(2026, 10, 1), amount=amount,
                       category_id=cat.id, partner_id=partner.id if partner else None))
    db.commit()


def test_expense_paid_by_one_partner_is_owed_by_company(db):
    a, b = _users(db)
    _tx(db, GIDER, 100_00, a)
    sheet = balance.compute(db)
    assert [l.balance for l in sheet.lines] == [100_00, 0]
    assert [l.user.id for l in sheet.open] == [a.id]


def test_income_collected_by_one_partner_is_owed_to_company(db):
    a, b = _users(db)
    _tx(db, GELIR, 1000_00, a)
    sheet = balance.compute(db)
    assert [l.balance for l in sheet.lines] == [-1000_00, 0]


def test_partners_never_owe_each_other(db):
    a, b = _users(db)
    _tx(db, GIDER, 300_00, a)
    _tx(db, GIDER, 100_00, b)
    _tx(db, GELIR, 1000_00, b)
    sheet = balance.compute(db)
    assert [l.balance for l in sheet.lines] == [300_00, -900_00]


def test_shared_account_does_not_affect_balance(db):
    _users(db)
    _tx(db, GIDER, 750_00, None)
    _tx(db, GELIR, 2000_00, None)
    sheet = balance.compute(db)
    assert sheet.settled and all(l.balance == 0 for l in sheet.lines)


def test_company_payment_closes_the_receivable(db):
    a, b = _users(db)
    _tx(db, GIDER, 600_00, a)
    db.add(PartnerPayment(day=date(2026, 10, 2), user_id=a.id, direction=SIRKET_ODEDI, amount=600_00))
    db.commit()
    sheet = balance.compute(db)
    assert sheet.settled and [l.balance for l in sheet.lines] == [0, 0]


def test_deposit_to_company_closes_the_debt(db):
    a, b = _users(db)
    _tx(db, GELIR, 400_00, b)
    db.add(PartnerPayment(day=date(2026, 10, 2), user_id=b.id, direction=ORTAK_YATIRDI, amount=400_00))
    db.commit()
    sheet = balance.compute(db)
    assert sheet.settled
    assert sheet.lines[1].received == 0 and sheet.lines[1].deposited == 400_00
