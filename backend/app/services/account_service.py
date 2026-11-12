import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.money import ZERO, to_decimal
from app.models import Account, AccountType, Transaction, TransactionType
from app.services.queries import get_owned_account, month_range, shift_month, spending_by_category

logger = get_logger("account_service")


def create_account(db: Session, user_id: int, *, account_name: str, account_type: AccountType, balance, currency: str = "INR") -> Account:
    account = Account(
        user_id=user_id, account_name=account_name, account_type=account_type,
        balance=to_decimal(balance), currency=currency.upper(),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    logger.info("account_created", account_id=account.id, account_type=account_type.value)
    return account


def list_accounts(db: Session, user_id: int) -> list[Account]:
    return list(db.scalars(select(Account).where(Account.user_id == user_id).order_by(Account.id)))


def rename_account(db: Session, user_id: int, account_id: int, account_name: str) -> Account:
    account = get_owned_account(db, account_id, user_id)
    name = account_name.strip()
    account.account_name = name
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, user_id: int, account_id: int) -> None:
    """Deletes the account and all its transactions atomically (manual §3). Budgets and alerts are untouched."""
    account = get_owned_account(db, account_id, user_id)
    try:
        db.delete(account)
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("account_deleted", account_id=account_id)


def account_summary(db: Session, user_id: int, account_id: int, today: datetime.date) -> dict:
    account = get_owned_account(db, account_id, user_id)
    rows = dict(
        db.execute(
            select(Transaction.type, func.sum(Transaction.amount)).where(Transaction.account_id == account.id).group_by(Transaction.type)
        ).all()
    )
    total_credit = rows.get(TransactionType.credit, ZERO)
    total_debit = rows.get(TransactionType.debit, ZERO)

    first_year, first_month = shift_month(today.year, today.month, -5)
    window_start = month_range(first_year, first_month)[0]
    window_end = month_range(today.year, today.month)[1]
    window = db.execute(
        select(Transaction.transaction_date, Transaction.type, Transaction.amount).where(
            Transaction.account_id == account.id,
            Transaction.is_transfer.is_(False),
            Transaction.transaction_date >= window_start,
            Transaction.transaction_date < window_end,
        )
    ).all()
    buckets: dict[tuple[int, int], dict[str, Decimal]] = {}
    for i in range(6):
        y, m = shift_month(first_year, first_month, i)
        buckets[(y, m)] = {"spending": ZERO, "income": ZERO}
    for d, t, amt in window:
        key = "spending" if t == TransactionType.debit else "income"
        buckets[(d.year, d.month)][key] += amt
    trend = [
        {"month": f"{y}-{m:02d}", "year": y, "month_number": m, **vals} for (y, m), vals in buckets.items()
    ]
    return {
        "account_id": account.id,
        "total_credit": total_credit,
        "total_debit": total_debit,
        "balance": to_decimal(account.balance),
        "spending_by_category": spending_by_category(db, user_id, account_id=account.id),
        "monthly_trend": trend,
    }
