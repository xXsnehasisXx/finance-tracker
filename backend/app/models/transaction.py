import datetime
import enum
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.money import Money
from app.database import Base


class TransactionType(str, enum.Enum):
    credit = "credit"
    debit = "debit"


class TransactionCategory(str, enum.Enum):
    food = "food"
    transport = "transport"
    utilities = "utilities"
    entertainment = "entertainment"
    health = "health"
    salary = "salary"
    other = "other"


class Transaction(Base):
    """Belongs to an account (never directly to a user).

    is_transfer / transfer_group are supporting columns set only by the transfer service
    (account-to-account moves such as credit-card repayments) so they are never counted as income/expense.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        Index("ix_transactions_account_date", "account_id", "transaction_date"),
        Index("ix_transactions_category_type", "category", "type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, native_enum=False, length=10), nullable=False)
    category: Mapped[TransactionCategory] = mapped_column(Enum(TransactionCategory, native_enum=False, length=20), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(200), nullable=True)
    transaction_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    is_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    transfer_group: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC), server_default=func.now()
    )

    account = relationship("Account", back_populates="transactions")
