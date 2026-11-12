"""Budget alerts: warning_80 at >=80% utilization, exceeded at >=100%; each type once per budget."""
import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.money import to_decimal
from app.models import AlertType, Budget, BudgetAlert, TransactionCategory
from app.services.queries import spent_in_month

logger = get_logger("budget_alert_service")

WARNING_RATIO = Decimal("0.8")


def utilization_percent(spent, limit) -> Decimal:
    limit = to_decimal(limit)
    if limit <= 0:
        return Decimal("0.00")
    return (to_decimal(spent) / limit * 100).quantize(Decimal("0.01"))


def check_and_create_alerts(db: Session, user_id: int, category, transaction_date: datetime.date) -> list[AlertType]:
    """Creates any newly crossed alerts for the budget of (user, category, month). Caller commits. Returns new alert types."""
    category = TransactionCategory(category)
    budget = db.scalar(
        select(Budget).where(
            Budget.user_id == user_id,
            Budget.category == category,
            Budget.month == transaction_date.month,
            Budget.year == transaction_date.year,
        )
    )
    if budget is None:
        return []

    limit = to_decimal(budget.monthly_limit)
    spent = spent_in_month(db, user_id, category, transaction_date.year, transaction_date.month)
    pct = utilization_percent(spent, limit)

    existing = set(db.scalars(select(BudgetAlert.alert_type).where(BudgetAlert.budget_id == budget.id)))
    wanted = []
    if spent >= limit * WARNING_RATIO:
        wanted.append(AlertType.warning_80)
    if spent >= limit:
        wanted.append(AlertType.exceeded)

    created = []
    for alert_type in wanted:
        if alert_type in existing:
            continue
        db.add(BudgetAlert(budget_id=budget.id, alert_type=alert_type))
        created.append(alert_type)
        logger.warning(
            "budget_alert_triggered",
            budget_id=budget.id,
            category=category.value,
            alert_type=alert_type.value,
            utilization_percent=float(pct),
        )
    if created:
        db.flush()
    return created
