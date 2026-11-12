import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.clock import get_today
from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import CategoryAmount, DashboardOut, IncomeExpensePoint
from app.services import dashboard_service
from app.services.queries import get_owned_account, month_range

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    today: datetime.date = Depends(get_today),
):
    return dashboard_service.dashboard(db, user.id, today, month, year)


@router.get("/analytics/spending-by-category", response_model=list[CategoryAmount])
def spending_by_category(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    account_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = date_from, (date_to + datetime.timedelta(days=1) if date_to else None)
    if month is not None and year is not None:
        start, end = month_range(year, month)
    elif (month is None) != (year is None):
        raise HTTPException(status_code=422, detail="month and year must be provided together")
    if account_id is not None:
        get_owned_account(db, account_id, user.id)
    return dashboard_service.spending_by_category_report(db, user.id, start=start, end=end, account_id=account_id)


@router.get("/analytics/income-vs-expense", response_model=list[IncomeExpensePoint])
def income_vs_expense(
    months: int = Query(6, ge=1, le=24),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    today: datetime.date = Depends(get_today),
):
    return dashboard_service.income_vs_expense(db, user.id, today, months)
