from datetime import date

from app.models import GIDER, Category, FixedExpense, ReminderLog, Transaction, User
from app.services import fixed, reminders


def _fixed(db, first_due, count=None, remind=3, amount=18_500_00):
    cat = db.query(Category).filter_by(kind=GIDER, name="Leasing").one()
    fx = FixedExpense(name="Kamyon leasing", amount=amount, due_day=first_due.day,
                      first_due=first_due, total_count=count, category_id=cat.id, remind_days=remind)
    db.add(fx)
    db.commit()
    return fx


def test_installments_open_two_months_ahead(db):
    fx = _fixed(db, date(2026, 10, 15))
    assert fixed.ensure_installments(db, date(2026, 10, 8)) == 3
    assert [i.due_date for i in fx.installments] == [
        date(2026, 10, 15), date(2026, 11, 15), date(2026, 12, 15)]
    assert fixed.ensure_installments(db, date(2026, 10, 9)) == 0          # tekrar çalışınca çoğalmaz
    assert fixed.ensure_installments(db, date(2026, 11, 1)) == 1          # ay dönünce bir sonraki açılır


def test_thirty_day_reminder_is_not_late(db):
    # 1 Mart vadeli, 30 gün önceden hatırlatmalı: 30 Ocak'ta taksit açık ve uyarıda olmalı
    _fixed(db, date(2027, 3, 1), remind=30)
    fixed.ensure_installments(db, date(2027, 1, 30))
    assert [a.days_left for a in fixed.alerts(db, date(2027, 1, 30))] == [30]


def test_short_months_use_last_day(db):
    fx = _fixed(db, date(2027, 1, 31))
    fixed.ensure_installments(db, date(2027, 2, 1))
    assert [i.due_date for i in fx.installments] == [
        date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]


def test_count_limits_installments(db):
    fx = _fixed(db, date(2026, 10, 5), count=2)
    fixed.ensure_installments(db, date(2027, 6, 1))
    assert len(fx.installments) == 2
    assert fixed.remaining(fx) == (2, 2 * 18_500_00)


def test_alerts_window(db):
    _fixed(db, date(2026, 10, 15), remind=3)
    fixed.ensure_installments(db, date(2026, 10, 8))
    assert fixed.alerts(db, date(2026, 10, 11)) == []
    (a,) = fixed.alerts(db, date(2026, 10, 12))
    assert a.days_left == 3 and a.state == "yaklasan"
    assert fixed.alerts(db, date(2026, 10, 15))[0].state == "bugun"
    late = fixed.alerts(db, date(2026, 10, 18))[0]
    assert late.state == "gecikti" and late.when_text == "3 gün gecikti"


def test_pay_creates_expense_and_delete_reopens(db):
    u = User(name="A", email="a@x.co", password_hash="x")
    db.add(u)
    db.commit()
    fx = _fixed(db, date(2026, 10, 15), count=12)
    fixed.ensure_installments(db, date(2026, 10, 8))
    inst = fx.installments[0]
    # Aynı taksiti ödeme öncesinde okumuş ikinci bir istek (ör. diğer ortağın açık sayfası)
    from app.db import SessionLocal
    from app.models import Installment
    other = SessionLocal()
    stale = other.get(Installment, inst.id)
    assert not stale.is_paid

    tx = fixed.pay_installment(db, inst, paid_on=date(2026, 10, 14), amount=18_650_00,
                               partner_id=u.id, created_by_id=u.id)
    assert inst.is_paid and tx.kind == GIDER and tx.amount == 18_650_00
    assert tx.category.name == "Leasing" and "1/12" in tx.description
    assert fixed.remaining(fx) == (11, 11 * 18_500_00)
    assert [i.installment.seq for i in fixed.unpaid_items(db, date(2026, 10, 14))] == [2, 3]

    # bayat kopyayla gelen ikinci ödeme reddedilir, ikinci gider kaydı oluşmaz
    import pytest
    with pytest.raises(ValueError):
        fixed.pay_installment(other, stale, paid_on=date(2026, 10, 14), amount=1,
                              partner_id=None, created_by_id=u.id)
    other.close()
    db.refresh(inst)
    assert inst.transaction_id == tx.id and db.query(Transaction).count() == 1

    inst.transaction_id = None
    db.delete(db.get(Transaction, tx.id))
    db.commit()
    assert not inst.is_paid


def test_reminders_send_once_per_stage(db, monkeypatch):
    db.add(User(name="A", email="a@x.co", password_hash="x"))
    db.add(User(name="B", email="b@x.co", password_hash="x", notify_email=False))
    db.commit()
    _fixed(db, date(2026, 10, 15), remind=3)
    sent = []
    monkeypatch.setattr(reminders, "send_mail", lambda to, subject, text, html=None: sent.append((to, subject, text)))

    assert reminders.run_once(db, date(2026, 10, 10)) == 0          # henüz erken
    assert reminders.run_once(db, date(2026, 10, 12)) == 1          # 3 gün kala
    assert reminders.run_once(db, date(2026, 10, 13)) == 0          # aynı aşama tekrar gitmez
    assert reminders.run_once(db, date(2026, 10, 15)) == 1          # vade günü
    assert reminders.run_once(db, date(2026, 10, 16)) == 1          # gecikti
    assert reminders.run_once(db, date(2026, 10, 20)) == 0          # haftada bir
    assert reminders.run_once(db, date(2026, 10, 23)) == 1
    assert len(sent) == 4
    assert sent[0][0] == ["a@x.co"]                                 # bildirimi kapalı ortağa gitmez
    assert "Kamyon leasing" in sent[0][1] and "18.500,00 ₺" in sent[0][2]
    assert db.query(ReminderLog).count() == 4


def test_overdue_installments_share_one_weekly_mail(db, monkeypatch):
    db.add(User(name="A", email="a@x.co", password_hash="x"))
    db.commit()
    _fixed(db, date(2026, 1, 10), remind=3, amount=1000_00)
    sent = []
    monkeypatch.setattr(reminders, "send_mail", lambda to, subject, text, html=None: sent.append(text))
    days = [date(2026, 1, 1) + __import__("datetime").timedelta(days=i) for i in range(150)]
    for d in days:
        reminders.run_once(db, d)
    # Mayıs sonunda 4-5 taksit gecikmiş durumda; yine de haftada birden fazla e-posta gitmemeli
    assert len(sent) <= 3 * 5 + 22
    last = sent[-1]
    assert last.count("gecikti") >= 4 and "Toplam: " in last
    sent_days = sorted({l.sent_on for l in db.query(ReminderLog).filter_by(kind="gecikti")})
    may = [d for d in sent_days if d.month == 5]
    assert len(may) <= 5, may
