import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AlertType(str, enum.Enum):
    warning_80 = "warning_80"
    exceeded = "exceeded"


class BudgetAlert(Base):
    __tablename__ = "budget_alerts"
    __table_args__ = (UniqueConstraint("budget_id", "alert_type", name="uq_alert_budget_type"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"), nullable=False, index=True)
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType, native_enum=False, length=20), nullable=False)
    triggered_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC), server_default=func.now()
    )

    budget = relationship("Budget", back_populates="alerts")
