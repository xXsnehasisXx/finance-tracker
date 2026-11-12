from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.logging import get_logger
from app.core.money import to_decimal
from app.models import AlertType, Budget, BudgetAlert, TransactionCategory
from app.services.budget_alert_service import utilization_percent
from app.services.queries import get_owned_budget, spent_in_month

logger = get_logger("budget_service")


def create_budget(db: Session, user_id: int, *, category: TransactionCategory, monthly_limit, month: int, year: int) -> Budget:
    exists = db.scalar(
        select(Budget.id).where(Budget.user_id == user_id, Budget.category == category, Budget.month == month, Budget.year == year)
    )
    if exists:
        raise ConflictError("A budget for this category, month and year already exists")
    budget = Budget(user_id=user_id, category=category, monthly_limit=to_decimal(monthly_limit), month=month, year=year)
    db.add(budget)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("A budget for this category, month and year already exists")
    db.refresh(budget)
    logger.info("budget_created", budget_id=budget.id, category=category.value, month=month, year=year)
    return budget


def budget_status(db: Session, budget: Budget) -> dict:
    spent = spent_in_month(db, budget.user_id, budget.category, budget.year, budget.month)
    limit = to_decimal(budget.monthly_limit)
    alerts = list(db.scalars(select(BudgetAlert).where(BudgetAlert.budget_id == budget.id).order_by(BudgetAlert.id)))
    return {
        "id": budget.id,
        "category": budget.category,
        "monthly_limit": limit,
        "month": budget.month,
        "year": budget.year,
        "created_at": budget.created_at,
        "spent": spent,
        "remaining": limit - spent,
        "utilization_percent": float(utilization_percent(spent, limit)),
        "has_alert": len(alerts) > 0,
        "alerts": alerts,
    }


def list_budgets(db: Session, user_id: int, month: int | None = None, year: int | None = None) -> list[dict]:
    conds = [Budget.user_id == user_id]
    if month is not None:
        conds.append(Budget.month == month)
    if year is not None:
        conds.append(Budget.year == year)
    budgets = db.scalars(select(Budget).where(*conds).order_by(Budget.year.desc(), Budget.month.desc(), Budget.category))
    return [budget_status(db, b) for b in budgets]


def get_budget(db: Session, user_id: int, budget_id: int) -> dict:
    return budget_status(db, get_owned_budget(db, budget_id, user_id))


def delete_budget(db: Session, user_id: int, budget_id: int) -> None:
    budget = get_owned_budget(db, budget_id, user_id)
    db.delete(budget)
    db.commit()
    logger.info("budget_deleted", budget_id=budget_id)


def list_alerts(db: Session, user_id: int, month: int | None = None, year: int | None = None) -> list[dict]:
    conds = [Budget.user_id == user_id]
    if month is not None:
        conds.append(Budget.month == month)
    if year is not None:
        conds.append(Budget.year == year)
    rows = db.execute(
        select(BudgetAlert, Budget).join(Budget, Budget.id == BudgetAlert.budget_id).where(*conds).order_by(BudgetAlert.triggered_at.desc(), BudgetAlert.id.desc())
    ).all()
    return [
        {"id": a.id, "budget_id": b.id, "category": b.category, "month": b.month, "year": b.year,
         "alert_type": a.alert_type, "triggered_at": a.triggered_at}
        for a, b in rows
    ]
