# Database and SQLAlchemy

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Sources: [`app/database/__init__.py`](../../backend/app/database/__init__.py), `app/models/*.py`, [`core/money.py`](../../backend/app/core/money.py), `app/services/*.py`. ER diagram: [Database_ER_Diagram](../09_Data_Flow_and_Reference/Database_ER_Diagram.md). Column-level model/schema tables: [Models_and_Schemas](Models_and_Schemas.md).

## 1. SQLite configuration

```python
_url = get_settings().database_url               # default sqlite:///./finance_tracker.db
engine = create_engine(_url, connect_args={"check_same_thread": False} if _is_sqlite else {})

@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _):
    cur.execute("PRAGMA foreign_keys=ON")        # SQLite ignores FKs unless enabled per connection
    if not _is_memory:
        cur.execute("PRAGMA journal_mode=WAL")    # readers don't block the writer
```

* `check_same_thread=False`: FastAPI runs sync handlers in a thread pool, so one connection may be used from different threads.
* The relative default URL resolves against the process **working directory** — start the backend from the same place each time or set an absolute `DATABASE_URL`. (Two `.db` files exist in the repo: root and `backend/`.)
* In tests `DATABASE_URL=sqlite://` (in-memory). The test engine in `tests/conftest.py` deliberately keeps foreign keys **off** because some POC unit tests insert rows with a `user_id` that has no user row.

## 2. Sessions

```python
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:   yield db
    finally: db.close()
```

* One session per request (FastAPI dependency).
* `autoflush=False`: pending objects are *not* auto-flushed before queries; services call `db.flush()` explicitly when they need generated ids or want queries to see pending rows (e.g. after inserting the `Transaction`, before `check_and_create_alerts` re-sums the month).
* `autocommit=False`: services decide when to `commit()`.

## 3. Declarative base and initialisation

`Base(DeclarativeBase)`; `init_db()` imports `app.models` (registering the 5 tables) and calls `Base.metadata.create_all(bind=engine)` during FastAPI startup. No Alembic. `create_all` never alters an existing table.

## 4. The `Money` type: Decimal in Python, integer paise in SQLite

```python
class Money(TypeDecorator):
    impl = BigInteger
    def process_bind_param(self, value, dialect):  return int(to_decimal(value).scaleb(2))        # 123.45 -> 12345
    def process_result_value(self, value, dialect): return Decimal(int(value)).scaleb(-2).quantize(CENT)  # 12345 -> 123.45
```

* `to_decimal` converts via `str()` (so `0.1 + 0.2`-style binary artefacts never enter), requires a finite value, and quantises to 2 dp with `ROUND_HALF_UP`.
* Storing integers means SQL `SUM` and `balance + delta` arithmetic is exact, and comparisons such as `balance + delta >= 0` are exact.
* Because `func.sum(Transaction.amount)` keeps the `Money` type, aggregate results come back as `Decimal`.
* Consequence: the `BIGINT` columns in the DDL hold **paise**, not rupees (e.g. ₹500.00 = `50000`). Anyone querying the DB by hand must divide by 100.

## 5. Tables (generated DDL, SQLite dialect)

```sql
CREATE TABLE users (
  id INTEGER NOT NULL PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(254) NOT NULL,
  phone VARCHAR(30), monthly_income BIGINT NOT NULL, password_hash VARCHAR(128) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL);
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE accounts (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users (id), account_name VARCHAR(120) NOT NULL,
  account_type VARCHAR(20) NOT NULL, balance BIGINT NOT NULL, currency VARCHAR(3) DEFAULT 'INR' NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL);

CREATE TABLE transactions (
  id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts (id), amount BIGINT NOT NULL,
  type VARCHAR(10) NOT NULL, category VARCHAR(20) NOT NULL, description VARCHAR(500) NOT NULL, merchant VARCHAR(200),
  transaction_date DATE NOT NULL, is_transfer BOOLEAN DEFAULT '0' NOT NULL, transfer_group VARCHAR(36),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
  CONSTRAINT ck_transactions_amount_positive CHECK (amount > 0));

CREATE TABLE budgets (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users (id), category VARCHAR(20) NOT NULL,
  monthly_limit BIGINT NOT NULL, month INTEGER NOT NULL, year INTEGER NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
  CONSTRAINT uq_budget_user_category_month_year UNIQUE (user_id, category, month, year),
  CONSTRAINT ck_budget_month CHECK (month >= 1 AND month <= 12),
  CONSTRAINT ck_budget_limit_positive CHECK (monthly_limit > 0));

CREATE TABLE budget_alerts (
  id INTEGER PRIMARY KEY, budget_id INTEGER NOT NULL REFERENCES budgets (id), alert_type VARCHAR(20) NOT NULL,
  triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
  CONSTRAINT uq_alert_budget_type UNIQUE (budget_id, alert_type));
```

(Abbreviated from `CreateTable(...)` compiled for SQLite from the models; only the PK/unique indexes shown for brevity.)

### Indexes

| Table | Index |
|---|---|
| users | `ix_users_id`, **unique** `ix_users_email` |
| accounts | `ix_accounts_id`, `ix_accounts_user_id` |
| transactions | `ix_transactions_id`, `ix_transactions_account_id`, `ix_transactions_transaction_date`, `ix_transactions_transfer_group`, composite `ix_transactions_account_date (account_id, transaction_date)`, composite `ix_transactions_category_type (category, type)` |
| budgets | `ix_budgets_id`, `ix_budgets_user_id` |
| budget_alerts | `ix_budget_alerts_id`, `ix_budget_alerts_budget_id` |

### Enums

`Enum(..., native_enum=False, length=…)` → stored as `VARCHAR`; SQLAlchemy 2.x does not create a CHECK constraint for them by default, so allowed values are enforced by Pydantic/Python enums, **not** by the database. Enums: `AccountType` (savings, checking, credit), `TransactionType` (credit, debit), `TransactionCategory` (food, transport, utilities, entertainment, health, salary, other), `AlertType` (warning_80, exceeded).

## 6. Relationships and cascades

| Relationship | Definition | Delete behaviour |
|---|---|---|
| `User.accounts` ↔ `Account.user` | `cascade="all, delete-orphan"` | deleting a user (no endpoint exists) would delete accounts |
| `User.budgets` ↔ `Budget.user` | `cascade="all, delete-orphan"` | same |
| `Account.transactions` ↔ `Transaction.account` | `cascade="all, delete-orphan"` | **deleting an account deletes its transactions** |
| `Budget.alerts` ↔ `BudgetAlert.budget` | `cascade="all, delete-orphan"` | **deleting a budget deletes its alerts** |

Cascades are **ORM-level** (SQLAlchemy loads children and deletes them). The foreign keys themselves have **no `ON DELETE`** clause, so deleting a parent row by raw SQL while `foreign_keys=ON` would be rejected.

There is intentionally **no** `Transaction → User` link (transactions belong to accounts) and **no** `Budget ↔ Transaction` foreign key: budget "spent" is computed by query (user + category + month, non-transfer debits across all the user's accounts).

## 7. CRUD patterns

| Operation | Pattern (file) |
|---|---|
| Create | `db.add(obj); db.commit(); db.refresh(obj)` (`account_service.create_account`) |
| Read one | `db.get(Model, id)` then ownership check (`queries.get_owned_*`) |
| Read many | `db.scalars(select(...).where(...).order_by(...))` |
| Update | mutate ORM attribute, `commit`, `refresh` (`rename_account`, `update_me`) — **only** accounts' name and user profile can be updated |
| Delete | `db.delete(obj); db.commit()` (account, budget) |
| Aggregate | `select(func.sum(...)).group_by(...)` (`queries.py`, `dashboard_service.py`, `account_service.account_summary`) |
| Pagination | `.order_by(date.desc(), id.desc()).offset((page-1)*size).limit(size)` plus a separate `count(*)` |

## 8. Transaction handling (atomicity)

* `create_transaction` and `create_transfer` wrap the whole unit of work in `try: … db.commit() except Exception: db.rollback(); raise`. Balance update(s), the row insert(s) and alert rows succeed or fail together.
* The balance change is a **single guarded SQL UPDATE**, not read-modify-write in Python:

```python
condition = Account.id == account.id
if account_type != credit and delta < 0:
    condition = and_(condition, Account.balance + delta >= 0)
result = db.execute(update(Account).where(condition).values(balance=Account.balance + delta)
                    .execution_options(synchronize_session=False))
if result.rowcount != 1: raise InsufficientBalanceError("Insufficient balance")
db.refresh(account)
```

  If the guard fails no row is updated (`rowcount == 0`) → HTTP 400 and the surrounding rollback leaves everything unchanged. This also protects against two concurrent debits racing past a Python-side balance check.
* `delete_account` is atomic (transactions + account in one commit, rollback on error).
* IntegrityError fallbacks: `register_user` and `create_budget` pre-check for duplicates and also catch `IntegrityError` on commit (race) and convert it to HTTP 409.

## 9. Lifecycle: create → read → aggregate

1. **Create:** `POST /accounts` inserts an account with initial `balance` (paise in DB).
2. **Record:** `POST /transactions` runs the atomic flow of §8; the `Transaction` row stores `amount > 0` (CHECK) and the direction in `type`.
3. **Read:** `GET /transactions` filters on `account_id IN (user's accounts)`, uses `ix_transactions_account_date`, paginates.
4. **Aggregate:** dashboard/analytics join `transactions → accounts`, filter `Account.user_id`, `is_transfer = 0`, and a half-open date range `[first_of_month, first_of_next_month)`, then `SUM(amount) GROUP BY category` (or no grouping). Results are `Decimal`s thanks to `Money`.

## 10. Limitations

* No migrations; schema drift on an existing DB file is not handled.
* No DB-level enum CHECKs.
* Money columns store paise (a reader of raw rows must know this).
* SQLite single-writer: concurrent writes are serialised; fine for a POC, not for multi-node production.
* `finance_tracker.db` is listed in `.gitignore` but the root-level file is currently **tracked by git** (see [Security_and_Configuration](../08_Deployment_and_DevOps/Security_and_Configuration.md)); there is no seed in the schema (use `scripts/seed_demo.py` against a running backend).
