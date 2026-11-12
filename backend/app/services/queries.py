"""Shared query helpers. Spending/income figures exclude transfer legs (is_transfer) to avoid double counting."""
import datetime
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.money import ZERO
from app.models import Account, AccountType, Budget, Transaction, TransactionCategory, TransactionType

ASSET_TYPES = (AccountType.savings, AccountType.checking)


def month_range(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    """[first day, first day of next month)"""
    start = datetime.date(year, month, 1)
    end = datetime.date(year + 1, 1, 1) if month == 12 else datetime.date(year, month + 1, 1)
    return start, end


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def get_owned_account(db: Session, account_id: int, user_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found")
    if account.user_id != user_id:
        raise ForbiddenError("You do not have access to this account")
    return account


def get_owned_budget(db: Session, budget_id: int, user_id: int) -> Budget:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise NotFoundError("Budget not found")
    if budget.user_id != user_id:
        raise ForbiddenError("You do not have access to this budget")
    return budget


def get_owned_transaction(db: Session, transaction_id: int, user_id: int) -> Transaction:
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise NotFoundError("Transaction not found")
    if txn.account.user_id != user_id:
        raise ForbiddenError("You do not have access to this transaction")
    return txn


def user_account_ids(db: Session, user_id: int) -> list[int]:
    return list(db.scalars(select(Account.id).where(Account.user_id == user_id)))


def _sum(db: Session, *conditions) -> Decimal:
    value = db.scalar(select(func.sum(Transaction.amount)).join(Account, Account.id == Transaction.account_id).where(*conditions))
    return value if value is not None else ZERO


def spent_in_month(db: Session, user_id: int, category, year: int, month: int) -> Decimal:
    """Budget 'spent': non-transfer debits of a category across the user's accounts in that calendar month."""
    start, end = month_range(year, month)
    return _sum(
        db,
        Account.user_id == user_id,
        Transaction.type == TransactionType.debit,
        Transaction.category == TransactionCategory(category),
        Transaction.is_transfer.is_(False),
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    )


def income_in_range(db: Session, user_id: int, start: datetime.date, end: datetime.date) -> Decimal:
    """Income = credits on asset accounts (savings/checking), excluding transfer legs. Credit-card repayments are never income."""
    return _sum(
        db,
        Account.user_id == user_id,
        Account.account_type.in_(ASSET_TYPES),
        Transaction.type == TransactionType.credit,
        Transaction.is_transfer.is_(False),
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    )


def expenses_in_range(db: Session, user_id: int, start: datetime.date, end: datetime.date) -> Decimal:
    """Expenses (accrual) = non-transfer debits on all accounts; a card purchase counts when incurred."""
    return _sum(
        db,
        Account.user_id == user_id,
        Transaction.type == TransactionType.debit,
        Transaction.is_transfer.is_(False),
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    )


def spending_by_category(db: Session, user_id: int, *, start=None, end=None, account_id=None) -> dict[str, Decimal]:
    conds = [Account.user_id == user_id, Transaction.type == TransactionType.debit, Transaction.is_transfer.is_(False)]
    if start is not None:
        conds.append(Transaction.transaction_date >= start)
    if end is not None:
        conds.append(Transaction.transaction_date < end)
    if account_id is not None:
        conds.append(Transaction.account_id == account_id)
    rows = db.execute(
        select(Transaction.category, func.sum(Transaction.amount))
        .join(Account, Account.id == Transaction.account_id)
        .where(and_(*conds))
        .group_by(Transaction.category)
    ).all()
    out = {(c.value if hasattr(c, "value") else str(c)): v for c, v in rows}
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))
