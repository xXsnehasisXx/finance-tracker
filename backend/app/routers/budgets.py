from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import BudgetAlertDetail, BudgetCreate, BudgetOut
from app.services import budget_service

router = APIRouter(tags=["budgets"])


@router.post("/budgets", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
def create_budget(payload: BudgetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budget = budget_service.create_budget(
        db, user.id, category=payload.category, monthly_limit=payload.monthly_limit, month=payload.month, year=payload.year
    )
    return budget_service.budget_status(db, budget)


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return budget_service.list_budgets(db, user.id, month, year)


@router.get("/budgets/{budget_id}", response_model=BudgetOut)
def get_budget(budget_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return budget_service.get_budget(db, user.id, budget_id)


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budget_service.delete_budget(db, user.id, budget_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/budget-alerts", response_model=list[BudgetAlertDetail])
def list_budget_alerts(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return budget_service.list_alerts(db, user.id, month, year)
