import datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.clock import get_today
from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import AccountCreate, AccountOut, AccountSummary, AccountUpdate
from app.services import account_service
from app.services.queries import get_owned_account

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return account_service.create_account(
        db, user.id, account_name=payload.account_name, account_type=payload.account_type, balance=payload.balance, currency=payload.currency
    )


@router.get("", response_model=list[AccountOut])
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return account_service.list_accounts(db, user.id)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_owned_account(db, account_id, user.id)


@router.patch("/{account_id}", response_model=AccountOut)
def rename_account(account_id: int, payload: AccountUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return account_service.rename_account(db, user.id, account_id, payload.account_name)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_service.delete_account(db, user.id, account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{account_id}/summary", response_model=AccountSummary)
def account_summary(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    today: datetime.date = Depends(get_today),
):
    return account_service.account_summary(db, user.id, account_id, today)
