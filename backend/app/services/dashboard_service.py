"""Dashboard + analytics. Rules (see plan A1):
  assets = savings+checking balances; liabilities = credit balances (owed); total_balance = assets - liabilities
  income = non-transfer credits on asset accounts; expenses = non-transfer debits on all accounts
  savings_rate = (income - expenses) / income * 100 (0 if no income)
"""
import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.money import ZERO, to_decimal
from app.models import Account, AccountType, Budget, BudgetAlert, Transaction
from app.services.budget_service import budget_status
from app.services.queries import (
    ASSET_TYPES, expenses_in_range, income_in_range, month_range, shift_month, spending_by_category,
)


def savings_rate(income, expenses) -> float:
    income = to_decimal(income)
    if income <= 0:
        return 0.0
    return float(((income - to_decimal(expenses)) / income * 100).quantize(Decimal("0.01")))


def dashboard(db: Session, user_id: int, today: datetime.date, month: int | None = None, year: int | None = None) -> dict:
    y = year or today.year
    m = month or today.month
    start, end = month_range(y, m)

    balances = dict(
        db.execute(select(Account.account_type, func.sum(Account.balance)).where(Account.user_id == user_id).group_by(Account.account_type)).all()
    )
    assets = sum((balances.get(t, ZERO) for t in ASSET_TYPES), ZERO)
    liabilities = balances.get(AccountType.credit, ZERO)

    income = income_in_range(db, user_id, start, end)
    expenses = expenses_in_range(db, user_id, start, end)
    cats = spending_by_category(db, user_id, start=start, end=end)
    top3 = [{"category": c, "amount": a} for c, a in list(cats.items())[:3]]

    budgets = db.scalars(select(Budget).where(Budget.user_id == user_id, Budget.month == m, Budget.year == y).order_by(Budget.category))
    utilization = []
    for b in budgets:
        s = budget_status(db, b)
        utilization.append({k: s[k] for k in ("monthly_limit", "spent", "utilization_percent", "has_alert")} | {"category": s["category"].value})
    alerts_count = db.scalar(
        select(func.count(BudgetAlert.id)).join(Budget, Budget.id == BudgetAlert.budget_id).where(Budget.user_id == user_id, Budget.month == m, Budget.year == y)
    ) or 0

    recent = list(
        db.scalars(
            select(Transaction).join(Account, Account.id == Transaction.account_id).where(Account.user_id == user_id)
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).limit(5)
        )
    )
    return {
        "month": m,
        "year": y,
        "total_balance": assets - liabilities,
        "total_assets": assets,
        "total_liabilities": liabilities,
        "monthly_income": income,
        "monthly_expenses": expenses,
        "net_cash_flow": income - expenses,
        "savings_rate": savings_rate(income, expenses),
        "top_3_categories": top3,
        "budget_alerts_count": alerts_count,
        "recent_transactions": recent,
        "budget_utilization": utilization,
    }


def spending_by_category_report(db: Session, user_id: int, *, start=None, end=None, account_id=None) -> list[dict]:
    return [{"category": c, "amount": a} for c, a in spending_by_category(db, user_id, start=start, end=end, account_id=account_id).items()]


def income_vs_expense(db: Session, user_id: int, today: datetime.date, months: int = 6) -> list[dict]:
    out = []
    for i in range(months - 1, -1, -1):
        y, m = shift_month(today.year, today.month, -i)
        start, end = month_range(y, m)
        out.append({
            "month": f"{y}-{m:02d}", "year": y, "month_number": m,
            "income": income_in_range(db, user_id, start, end),
            "expenses": expenses_in_range(db, user_id, start, end),
        })
    return out
