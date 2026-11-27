# Models and Schemas

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Models = how data is stored (SQLAlchemy, `backend/app/models/`). Schemas = how data enters/leaves the API (Pydantic, [`backend/app/schemas/__init__.py`](../../backend/app/schemas/__init__.py)). Keeping them separate means the API contract can differ from storage (e.g. `password_hash` is never in a response schema; money is `Decimal` internally but a number in JSON).

## 1. ORM models

### `User` (`users`)
| Column | Type | Constraints / default |
|---|---|---|
| `id` | int | PK, indexed |
| `name` | String(120) | not null |
| `email` | String(254) | **unique**, indexed, not null |
| `phone` | String(30) | nullable |
| `monthly_income` | `Money` | not null, default 0.00 |
| `password_hash` | String(128) | not null |
| `created_at` | DateTime(tz) | default `now(UTC)` / `CURRENT_TIMESTAMP` |

Relationships: `accounts` (1-N, cascade all/delete-orphan), `budgets` (1-N, cascade all/delete-orphan).

### `Account` (`accounts`)
| Column | Type | Constraints / default |
|---|---|---|
| `id` | int | PK |
| `user_id` | FK `users.id` | not null, indexed |
| `account_name` | String(120) | not null |
| `account_type` | Enum `AccountType` (VARCHAR 20) | not null |
| `balance` | `Money` | not null, default 0.00. **Savings/checking: funds held (≥ 0). Credit: outstanding amount owed** |
| `currency` | String(3) | default `INR` |
| `created_at` | DateTime(tz) | default now |

Relationships: `user`, `transactions` (cascade all/delete-orphan).

### `Transaction` (`transactions`)
| Column | Type | Constraints / default |
|---|---|---|
| `id` | int | PK |
| `account_id` | FK `accounts.id` | not null, indexed — **transactions belong to accounts, never directly to users** |
| `amount` | `Money` | not null, `CHECK amount > 0` |
| `type` | Enum `TransactionType` | credit / debit |
| `category` | Enum `TransactionCategory` | food, transport, utilities, entertainment, health, salary, other |
| `description` | String(500) | not null |
| `merchant` | String(200) | nullable |
| `transaction_date` | Date | not null, indexed |
| `is_transfer` | Boolean | not null, default false (server default `0`) |
| `transfer_group` | String(36) | nullable, indexed; UUID shared by the two legs of a transfer |
| `created_at` | DateTime(tz) | default now |

Indexes: `(account_id, transaction_date)`, `(category, type)`. `is_transfer`/`transfer_group` are *supporting columns* beyond the POC ER model, set only by the transfer service so repayments are not counted as income/expense.

### `Budget` (`budgets`)
| Column | Type | Constraints |
|---|---|---|
| `id` | int | PK |
| `user_id` | FK `users.id` | not null, indexed |
| `category` | Enum `TransactionCategory` | not null |
| `monthly_limit` | `Money` | `CHECK monthly_limit > 0` |
| `month` | int | `CHECK month BETWEEN 1 AND 12` |
| `year` | int | not null |
| `created_at` | DateTime(tz) | default now |

`UNIQUE (user_id, category, month, year)` → *one budget per user, category and month*. Relationship `alerts` (cascade all/delete-orphan).

### `BudgetAlert` (`budget_alerts`)
| Column | Type | Constraints |
|---|---|---|
| `id` | int | PK |
| `budget_id` | FK `budgets.id` | not null, indexed |
| `alert_type` | Enum `AlertType` | `warning_80` / `exceeded` |
| `triggered_at` | DateTime(tz) | default now |

`UNIQUE (budget_id, alert_type)` → each alert type at most once per budget.

> The `salary`-category-budget restriction is **not** a DB constraint; it is a Pydantic validator (`BudgetCreate._no_salary`).

## 2. Pydantic schema conventions

```python
MoneyOut = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
MoneyIn  = Annotated[Decimal, Field(max_digits=14, decimal_places=2)]
class ORMModel(BaseModel): model_config = ConfigDict(from_attributes=True)
```

* **Input** money uses `Decimal` (so `0.1` JSON numbers are parsed exactly by Pydantic) and rejects more than 2 decimals / 14 digits.
* **Output** money is serialised as a JSON number (`float`) because clients and tests expect numbers. Arithmetic stays `Decimal` inside the service layer.
* `ORMModel` (`from_attributes=True`) lets `response_model` read straight from ORM objects (e.g. `UserOut`, `AccountOut`, `TransactionOut`).

## 3. Schemas by area

### Auth / users
| Schema | Fields |
|---|---|
| `UserCreate` | `name` (1–120, stripped, non-blank), `email` (`EmailStr`, lower-cased), `password` (min 8, ≤ 72 bytes), `phone?` (≤ 30), `monthly_income` (≥ 0, default 0) |
| `UserUpdate` | `name?` (1–120), `phone?` (≤ 30), `monthly_income?` (≥ 0) |
| `UserOut` | `id, name, email, phone, monthly_income, created_at` |
| `Token` | `access_token`, `token_type="bearer"` |

### Accounts
| Schema | Fields |
|---|---|
| `AccountCreate` | `account_name` (1–120, stripped non-blank), `account_type`, `balance` (≥ 0, default 0), `currency` (exactly 3 chars, default INR) |
| `AccountUpdate` | `account_name` (1–120) |
| `AccountOut` | `id, user_id, account_name, account_type, balance, currency, created_at` |
| `AccountSummary` | `account_id, total_credit, total_debit, balance, spending_by_category{str:money}, monthly_trend[MonthlyTrendItem]` |
| `MonthlyTrendItem` | `month "YYYY-MM", year, month_number, spending, income` |

### Transactions
| Schema | Fields |
|---|---|
| `TransactionCreate` | `account_id, amount (>0), type, category, description (1–500 stripped non-blank), merchant? (≤200, blank→null), transaction_date` |
| `TransactionOut` | `id, account_id, amount, type, category, description, merchant, transaction_date, is_transfer, transfer_group, created_at` |
| `TransactionPage` | `items, total, page, page_size, pages` |
| `TransferCreate` | `source_account_id, destination_account_id, amount (>0), transfer_date?, description="Transfer"` |
| `TransferOut` | `transfer_group, debit, credit, source_balance, destination_balance` |

### Budgets
| Schema | Fields |
|---|---|
| `BudgetCreate` | `category` (not salary), `monthly_limit (>0)`, `month (1–12)`, `year (2000–2100)` |
| `BudgetOut` | `id, category, monthly_limit, month, year, created_at, spent, remaining, utilization_percent (float), has_alert, alerts[BudgetAlertOut]` |
| `BudgetAlertOut` | `id, budget_id, alert_type, triggered_at` |
| `BudgetAlertDetail` | `id, budget_id, category, month, year, alert_type, triggered_at` |

`spent`, `remaining`, `utilization_percent`, `has_alert`, `alerts` are **not columns**: `budget_service.budget_status()` computes them on every read, so they are always current.

### Dashboard / analytics
| Schema | Fields |
|---|---|
| `DashboardOut` | `month, year, total_balance, total_assets, total_liabilities, monthly_income, monthly_expenses, net_cash_flow, savings_rate (float), top_3_categories[CategoryAmount], budget_alerts_count, recent_transactions[TransactionOut], budget_utilization[BudgetUtilizationItem]` |
| `CategoryAmount` | `category, amount` |
| `BudgetUtilizationItem` | `category, monthly_limit, spent, utilization_percent, has_alert` |
| `IncomeExpensePoint` | `month, year, month_number, income, expenses` |

## 4. Validation placement summary

| Rule | Pydantic | Service | DB |
|---|---|---|---|
| Email format, lower-case | ✅ | — | unique index |
| Password length | ✅ | — | — |
| `amount > 0` | ✅ (`gt=0`) | ✅ (re-checked) | ✅ CHECK |
| Salary must be credit | — | ✅ | — |
| Salary has no budget | ✅ | — | — |
| One budget per user/category/month | — | ✅ pre-check | ✅ UNIQUE |
| Month 1–12 | ✅ | — | ✅ CHECK |
| Non-negative asset balance | — | ✅ guarded UPDATE | — |
| Alert once per type | — | ✅ | ✅ UNIQUE |
