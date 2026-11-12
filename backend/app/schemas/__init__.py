import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer, field_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.models import AccountType, AlertType, TransactionCategory, TransactionType

# JSON numbers out (tests/clients expect numbers); Decimal-safe in/out of the service layer
MoneyOut = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
MoneyIn = Annotated[Decimal, Field(max_digits=14, decimal_places=2)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- auth / users ----------------
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    phone: str | None = Field(default=None, max_length=30)
    monthly_income: MoneyIn = Field(default=Decimal("0"), ge=0)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("password")
    @classmethod
    def _bcrypt_limit(cls, v):
        if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
        return v

    @field_validator("email")
    @classmethod
    def _lower(cls, v):
        return v.lower()


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    monthly_income: MoneyIn | None = Field(default=None, ge=0)


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    phone: str | None
    monthly_income: MoneyOut
    created_at: datetime.datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------- accounts ----------------
class AccountCreate(BaseModel):
    account_name: str = Field(min_length=1, max_length=120)
    account_type: AccountType
    balance: MoneyIn = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)

    @field_validator("account_name")
    @classmethod
    def _strip(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("account_name must not be blank")
        return v


class AccountUpdate(BaseModel):
    account_name: str = Field(min_length=1, max_length=120)


class AccountOut(ORMModel):
    id: int
    user_id: int
    account_name: str
    account_type: AccountType
    balance: MoneyOut
    currency: str
    created_at: datetime.datetime


class MonthlyTrendItem(BaseModel):
    month: str
    year: int
    month_number: int
    spending: MoneyOut
    income: MoneyOut


class AccountSummary(BaseModel):
    account_id: int
    total_credit: MoneyOut
    total_debit: MoneyOut
    balance: MoneyOut
    spending_by_category: dict[str, MoneyOut]
    monthly_trend: list[MonthlyTrendItem]


# ---------------- transactions ----------------
class TransactionCreate(BaseModel):
    account_id: int
    amount: MoneyIn = Field(gt=0)
    type: TransactionType
    category: TransactionCategory
    description: str = Field(min_length=1, max_length=500)
    merchant: str | None = Field(default=None, max_length=200)
    transaction_date: datetime.date

    @field_validator("description")
    @classmethod
    def _desc(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("description must not be blank")
        return v

    @field_validator("merchant")
    @classmethod
    def _merchant(cls, v):
        return (v.strip() or None) if v else None


class TransactionOut(ORMModel):
    id: int
    account_id: int
    amount: MoneyOut
    type: TransactionType
    category: TransactionCategory
    description: str
    merchant: str | None
    transaction_date: datetime.date
    is_transfer: bool
    transfer_group: str | None
    created_at: datetime.datetime


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int
    pages: int


class TransferCreate(BaseModel):
    source_account_id: int
    destination_account_id: int
    amount: MoneyIn = Field(gt=0)
    transfer_date: datetime.date | None = None
    description: str = Field(default="Transfer", min_length=1, max_length=500)


class TransferOut(BaseModel):
    transfer_group: str
    debit: TransactionOut
    credit: TransactionOut
    source_balance: MoneyOut
    destination_balance: MoneyOut


# ---------------- budgets ----------------
class BudgetCreate(BaseModel):
    category: TransactionCategory
    monthly_limit: MoneyIn = Field(gt=0)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)

    @field_validator("category")
    @classmethod
    def _no_salary(cls, v):
        if v == TransactionCategory.salary:
            raise ValueError("Budgets cannot be set for the salary category (income only)")
        return v


class BudgetAlertOut(ORMModel):
    id: int
    budget_id: int
    alert_type: AlertType
    triggered_at: datetime.datetime


class BudgetOut(BaseModel):
    id: int
    category: TransactionCategory
    monthly_limit: MoneyOut
    month: int
    year: int
    created_at: datetime.datetime
    spent: MoneyOut
    remaining: MoneyOut
    utilization_percent: float
    has_alert: bool
    alerts: list[BudgetAlertOut]


class BudgetAlertDetail(BaseModel):
    id: int
    budget_id: int
    category: TransactionCategory
    month: int
    year: int
    alert_type: AlertType
    triggered_at: datetime.datetime


# ---------------- dashboard / analytics ----------------
class CategoryAmount(BaseModel):
    category: str
    amount: MoneyOut


class BudgetUtilizationItem(BaseModel):
    category: str
    monthly_limit: MoneyOut
    spent: MoneyOut
    utilization_percent: float
    has_alert: bool


class DashboardOut(BaseModel):
    month: int
    year: int
    total_balance: MoneyOut
    total_assets: MoneyOut
    total_liabilities: MoneyOut
    monthly_income: MoneyOut
    monthly_expenses: MoneyOut
    net_cash_flow: MoneyOut
    savings_rate: float
    top_3_categories: list[CategoryAmount]
    budget_alerts_count: int
    recent_transactions: list[TransactionOut]
    budget_utilization: list[BudgetUtilizationItem]


class IncomeExpensePoint(BaseModel):
    month: str
    year: int
    month_number: int
    income: MoneyOut
    expenses: MoneyOut
