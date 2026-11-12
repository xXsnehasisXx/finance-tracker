import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.money import Money
from app.database import Base
from app.models.transaction import TransactionCategory


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "category", "month", "year", name="uq_budget_user_category_month_year"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_budget_month"),
        CheckConstraint("monthly_limit > 0", name="ck_budget_limit_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[TransactionCategory] = mapped_column(Enum(TransactionCategory, native_enum=False, length=20), nullable=False)
    monthly_limit: Mapped[Decimal] = mapped_column(Money, nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC), server_default=func.now()
    )

    user = relationship("User", back_populates="budgets")
    alerts = relationship("BudgetAlert", back_populates="budget", cascade="all, delete-orphan")
