import datetime
import enum
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.money import Money
from app.database import Base


class AccountType(str, enum.Enum):
    savings = "savings"
    checking = "checking"
    credit = "credit"


class Account(Base):
    """balance: savings/checking = funds held (>= 0); credit = outstanding amount owed."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType, native_enum=False, length=20), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC), server_default=func.now()
    )

    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
