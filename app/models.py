from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .db import Base
from .money import TRY

GIDER = "gider"
GELIR = "gelir"
SIRKET_ODEDI = "sirket_odedi"
ORTAK_YATIRDI = "ortak_yatirdi"
PAYMENT_LABELS = {SIRKET_ODEDI: "Şirket ortağa ödedi", ORTAK_YATIRDI: "Ortak şirkete yatırdı"}


class User(Base):
    """Ortak. `share_bp` eski sürümden kalma, hesapta kullanılmıyor."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    share_bp: Mapped[int] = mapped_column(Integer, default=5000)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(10), default=GIDER)  # gider | gelir
    sort: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("name", "kind", name="uq_category_name_kind"),)


class Transaction(Base):
    """Tek bir gelir ya da gider kaydı.

    `partner_id`: gider için parayı cebinden ödeyen, gelir için parayı teslim alan
    ortak. Boşsa işlem ortak hesaptan/kasadan yapılmıştır ve ortaklar arası
    borç-alacak hesabına girmez.
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[int] = mapped_column(Integer)  # kuruş, her zaman pozitif
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    partner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    category: Mapped[Category | None] = relationship(lazy="joined")
    partner: Mapped[User | None] = relationship(foreign_keys=[partner_id], lazy="joined")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    receipts: Mapped[list["Receipt"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan", lazy="selectin",
        order_by="Receipt.id",
    )
    installment: Mapped["Installment | None"] = relationship(
        back_populates="transaction", uselist=False, lazy="joined"
    )


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(300))  # yükleme klasörüne göre göreli yol
    thumb_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    original_name: Mapped[str] = mapped_column(String(300), default="")
    content_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transaction: Mapped[Transaction] = relationship(back_populates="receipts")

    @property
    def is_image(self) -> bool:
        return self.content_type.startswith("image/")


class FixedExpense(Base):
    """Her ay tekrarlayan sabit gider (leasing, kira, sigorta taksidi...)."""

    __tablename__ = "fixed_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Integer)  # aylık tutar, para biriminin en küçük birimiyle
    currency: Mapped[str] = mapped_column(String(3), default=TRY)
    due_day: Mapped[int] = mapped_column(Integer)  # 1-31; kısa aylarda ayın son günü
    first_due: Mapped[date] = mapped_column(Date)  # ilk taksitin vadesi
    total_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # boş = süresiz
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    remind_days: Mapped[int] = mapped_column(Integer, default=3)
    note: Mapped[str] = mapped_column(String(300), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    category: Mapped[Category | None] = relationship(lazy="joined")
    installments: Mapped[list["Installment"]] = relationship(
        back_populates="fixed", cascade="all, delete-orphan", order_by="Installment.due_date"
    )


class Installment(Base):
    """Sabit giderin bir aya düşen ödemesi."""

    __tablename__ = "installments"

    id: Mapped[int] = mapped_column(primary_key=True)
    fixed_id: Mapped[int] = mapped_column(ForeignKey("fixed_expenses.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)  # kaçıncı taksit (1'den başlar)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )

    fixed: Mapped[FixedExpense] = relationship(back_populates="installments", lazy="joined")
    transaction: Mapped[Transaction | None] = relationship(back_populates="installment")

    __table_args__ = (UniqueConstraint("fixed_id", "seq", name="uq_installment_seq"),)

    @property
    def is_paid(self) -> bool:
        return self.transaction_id is not None


class PartnerPayment(Base):
    """Şirket ile ortak arasındaki ödeme: şirket ortağa ödedi ya da ortak şirkete yatırdı."""

    __tablename__ = "partner_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    direction: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(lazy="joined")


class ExchangeRate(Base):
    """Günlük döviz kuru: value = 1 birim dövizin TL karşılığı × 10.000."""

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3))
    day: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(8))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("currency", "day", "source", name="uq_rate_day_source"),)


class ReminderLog(Base):
    """Aynı hatırlatmanın iki kez gitmemesi için gönderim kaydı."""

    __tablename__ = "reminder_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    installment_id: Mapped[int] = mapped_column(ForeignKey("installments.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # yaklasan | bugun | gecikti
    sent_on: Mapped[date] = mapped_column(Date)

    __table_args__ = (
        UniqueConstraint("installment_id", "kind", "sent_on", name="uq_reminder_once"),
    )


DEFAULT_CATEGORIES = {
    GIDER: ["Yakıt", "Yevmiye", "Yemek", "Bakım / Onarım", "Leasing", "Ek gider", "Diğer"],
    GELIR: ["İş geliri", "Diğer gelir"],
}


def seed_defaults(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(Category)):
        return
    for kind, names in DEFAULT_CATEGORIES.items():
        for i, name in enumerate(names):
            db.add(Category(name=name, kind=kind, sort=i))
    db.commit()
