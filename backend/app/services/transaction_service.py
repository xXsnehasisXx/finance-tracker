"""Transaction + transfer business logic. All balance changes happen in one DB transaction with the row insert.

Balance rules (account-type specific; documented exception to the POC overview's simplified rule):
  savings/checking : debit decreases, credit increases; balance may not go below zero ("Insufficient balance")
  credit           : balance is the amount OWED; debit increases it, credit (payment) decreases it; no negative check
"""
import datetime
import uuid
from decimal import Decimal

from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import DomainValidationError, InsufficientBalanceError
from app.core.logging import get_logger
from app.core.money import to_decimal
from app.core.telemetry import span
from app.models import Account, AccountType, Transaction, TransactionCategory, TransactionType
from app.services.budget_alert_service import check_and_create_alerts
from app.services.queries import get_owned_account, user_account_ids

logger = get_logger("transaction_service")


def signed_delta(account_type: AccountType, tx_type: TransactionType, amount: Decimal) -> Decimal:
    is_debit = tx_type == TransactionType.debit
    if account_type == AccountType.credit:
        return amount if is_debit else -amount
    return -amount if is_debit else amount


def apply_balance_delta(db: Session, account: Account, tx_type: TransactionType, amount: Decimal) -> None:
    """Atomic guarded UPDATE (concurrency-safe); raises InsufficientBalanceError for asset accounts."""
    account_type = AccountType(account.account_type)
    delta = signed_delta(account_type, tx_type, amount)
    old_balance = to_decimal(account.balance)
    condition = Account.id == account.id
    if account_type != AccountType.credit and delta < 0:
        condition = and_(condition, Account.balance + delta >= 0)
    with span("db.query", **{"db.operation": "UPDATE", "db.table": "accounts"}):
        result = db.execute(
            update(Account).where(condition).values(balance=Account.balance + delta).execution_options(synchronize_session=False)
        )
    if result.rowcount != 1:
        raise InsufficientBalanceError("Insufficient balance")
    db.refresh(account)
    logger.info(
        "balance_updated",
        account_id=account.id,
        old_balance=float(old_balance),
        new_balance=float(to_decimal(account.balance)),
    )


def create_transaction(db: Session, transaction_data, user_id: int) -> Transaction:
    data = transaction_data.model_dump()
    try:
        account = get_owned_account(db, data["account_id"], user_id)
        tx_type = TransactionType(data["type"])
        category = TransactionCategory(data["category"])
        amount = to_decimal(data["amount"])
        if amount <= 0:
            raise DomainValidationError("amount must be greater than 0")
        if category == TransactionCategory.salary and tx_type == TransactionType.debit:
            raise DomainValidationError("The salary category is income only (credit)")

        apply_balance_delta(db, account, tx_type, amount)
        transaction = Transaction(
            account_id=account.id,
            amount=amount,
            type=tx_type,
            category=category,
            description=data["description"],
            merchant=data.get("merchant"),
            transaction_date=data["transaction_date"],
            is_transfer=False,
        )
        with span("db.query", **{"db.operation": "INSERT", "db.table": "transactions"}):
            db.add(transaction)
            db.flush()
        if tx_type == TransactionType.debit:
            check_and_create_alerts(db, user_id, category, data["transaction_date"])
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(transaction)
    logger.info(
        "transaction_created",
        transaction_id=transaction.id,
        type=tx_type.value,
        amount=float(amount),
        category=category.value,
    )
    return transaction


def create_transfer(
    db: Session,
    user_id: int,
    source_account_id: int,
    destination_account_id: int,
    amount,
    transfer_date: datetime.date,
    description: str = "Transfer",
) -> tuple[str, Transaction, Transaction, Account, Account]:
    """Atomic two-leg move between two of the user's accounts (e.g. paying a credit card). Legs are is_transfer=True."""
    if source_account_id == destination_account_id:
        raise DomainValidationError("Source and destination accounts must be different")
    amount = to_decimal(amount)
    if amount <= 0:
        raise DomainValidationError("amount must be greater than 0")
    try:
        source = get_owned_account(db, source_account_id, user_id)
        destination = get_owned_account(db, destination_account_id, user_id)
        group = str(uuid.uuid4())
        apply_balance_delta(db, source, TransactionType.debit, amount)
        apply_balance_delta(db, destination, TransactionType.credit, amount)
        debit = Transaction(
            account_id=source.id, amount=amount, type=TransactionType.debit, category=TransactionCategory.other,
            description=description, transaction_date=transfer_date, is_transfer=True, transfer_group=group,
        )
        credit = Transaction(
            account_id=destination.id, amount=amount, type=TransactionType.credit, category=TransactionCategory.other,
            description=description, transaction_date=transfer_date, is_transfer=True, transfer_group=group,
        )
        db.add_all([debit, credit])
        db.commit()
    except Exception:
        db.rollback()
        raise
    for obj in (debit, credit, source, destination):
        db.refresh(obj)
    logger.info("transfer_created", transfer_group=group, source_account_id=source.id,
                destination_account_id=destination.id, amount=float(amount))
    return group, debit, credit, source, destination


def list_transactions(
    db: Session,
    user_id: int,
    *,
    account_id: int | None = None,
    category: TransactionCategory | None = None,
    tx_type: TransactionType | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Transaction], int]:
    if account_id is not None:
        get_owned_account(db, account_id, user_id)
        ids = [account_id]
    else:
        ids = user_account_ids(db, user_id)
    if not ids:
        return [], 0
    conds = [Transaction.account_id.in_(ids)]
    if category is not None:
        conds.append(Transaction.category == category)
    if tx_type is not None:
        conds.append(Transaction.type == tx_type)
    if date_from is not None:
        conds.append(Transaction.transaction_date >= date_from)
    if date_to is not None:
        conds.append(Transaction.transaction_date <= date_to)
    total = db.scalar(select(func.count()).select_from(Transaction).where(*conds)) or 0
    items = list(
        db.scalars(
            select(Transaction).where(*conds)
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
    )
    return items, total
