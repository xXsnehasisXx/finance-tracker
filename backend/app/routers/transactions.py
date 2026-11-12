import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.clock import get_today
from app.core.deps import get_current_user
from app.database import get_db
from app.models import TransactionCategory, TransactionType, User
from app.schemas import TransactionCreate, TransactionOut, TransactionPage, TransferCreate, TransferOut
from app.services import transaction_service
from app.services.queries import get_owned_transaction

router = APIRouter(tags=["transactions"])


@router.post("/transactions", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return transaction_service.create_transaction(db, payload, user.id)


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    account_id: int | None = None,
    category: TransactionCategory | None = None,
    type: TransactionType | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = transaction_service.list_transactions(
        db, user.id, account_id=account_id, category=category, tx_type=type,
        date_from=date_from, date_to=date_to, page=page, page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.get("/transactions/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_owned_transaction(db, transaction_id, user.id)


@router.post("/transfers", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def create_transfer(
    payload: TransferCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    today: datetime.date = Depends(get_today),
):
    group, debit, credit, source, destination = transaction_service.create_transfer(
        db, user.id, payload.source_account_id, payload.destination_account_id, payload.amount,
        payload.transfer_date or today, payload.description,
    )
    return {"transfer_group": group, "debit": debit, "credit": credit,
            "source_balance": source.balance, "destination_balance": destination.balance}
