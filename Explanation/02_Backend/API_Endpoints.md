# API Endpoints

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Source: `backend/app/routers/*.py` and `app/main.py`. All paths are prefixed with **`/api/v1`**. **23 endpoints** exist (22 under routers + `GET /health`).

Conventions used below:

* **Auth** = `Authorization: Bearer <JWT>` required (dependency `get_current_user`). Missing/invalid/expired token → **401** `{"detail": "Not authenticated"}` (no header) or `{"detail": "Could not validate credentials"}` (bad token / user deleted).
* Money in responses is a JSON **number** (`MoneyOut`), money in requests is accepted as number or string with ≤ 2 decimals and ≤ 14 digits (`MoneyIn`).
* `422` bodies have the shape `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` (custom handler). Domain errors are `{"detail": "<message>"}`.
* Schema field details are in [Models_and_Schemas](Models_and_Schemas.md); rule explanations in [Business_Logic](Business_Logic.md).

## Summary table

| # | Method | URL | Auth | Success | Purpose |
|---|---|---|---|---|---|
| 1 | POST | `/auth/register` | no | 201 | Create user |
| 2 | POST | `/auth/login` | no | 200 | Exchange credentials for JWT (form body) |
| 3 | GET | `/users/me` | yes | 200 | Current user |
| 4 | PATCH | `/users/me` | yes | 200 | Update name/phone/monthly income |
| 5 | POST | `/accounts` | yes | 201 | Create account |
| 6 | GET | `/accounts` | yes | 200 | List own accounts |
| 7 | GET | `/accounts/{account_id}` | yes | 200 | One account |
| 8 | PATCH | `/accounts/{account_id}` | yes | 200 | **Rename only** |
| 9 | DELETE | `/accounts/{account_id}` | yes | 204 | Delete account + its transactions |
| 10 | GET | `/accounts/{account_id}/summary` | yes | 200 | Totals, category spend, 6-month trend |
| 11 | POST | `/transactions` | yes | 201 | Record debit/credit |
| 12 | GET | `/transactions` | yes | 200 | Filtered, paginated list |
| 13 | GET | `/transactions/{transaction_id}` | yes | 200 | One transaction |
| 14 | POST | `/transfers` | yes | 201 | Atomic account-to-account transfer |
| 15 | POST | `/budgets` | yes | 201 | Create budget |
| 16 | GET | `/budgets` | yes | 200 | List budgets with live utilization |
| 17 | GET | `/budgets/{budget_id}` | yes | 200 | One budget |
| 18 | DELETE | `/budgets/{budget_id}` | yes | 204 | Delete budget (+ alerts) |
| 19 | GET | `/budget-alerts` | yes | 200 | List alerts |
| 20 | GET | `/dashboard` | yes | 200 | Month overview |
| 21 | GET | `/analytics/spending-by-category` | yes | 200 | Debit totals per category |
| 22 | GET | `/analytics/income-vs-expense` | yes | 200 | Monthly income/expense series |
| 23 | GET | `/health` | no | 200 | Liveness probe |

**Not implemented (verified — no such routes):** transaction update, transaction delete, budget update, account type/balance change, user delete, password change/reset, refresh tokens, logout endpoint.

---

## 1. `POST /auth/register`
* **Purpose:** create a user. **Auth:** none.
* **Body (JSON, `UserCreate`):** `name` (1–120, trimmed, not blank), `email` (valid email, lower-cased), `password` (≥ 8 chars and ≤ 72 UTF-8 bytes), `phone` (optional, ≤ 30), `monthly_income` (optional, default 0, ≥ 0, 2 dp).
* **Response 201 (`UserOut`):** `id, name, email, phone, monthly_income, created_at` (never the hash).
* **Validation:** Pydantic as above; duplicate email checked.
* **DB:** `SELECT users.id WHERE email=?`, `INSERT users` (bcrypt hash), commit.
* **Errors:** 409 `Email is already registered` (also on race via `IntegrityError`); 422.

## 2. `POST /auth/login`
* **Body:** `application/x-www-form-urlencoded` — `username` (the email) and `password` (`OAuth2PasswordRequestForm`).
* **Response 200 (`Token`):** `{"access_token": "<jwt>", "token_type": "bearer"}`.
* **Logic:** `auth_service.authenticate` lower-cases the email, loads the user, runs bcrypt verify (dummy hash for unknown users to keep timing similar), logs `login_success` or `auth_failure`.
* **Errors:** 401 `Incorrect email or password` with `WWW-Authenticate: Bearer` (same message for unknown user and wrong password); 422 if form fields missing.

## 3. `GET /users/me`
Auth. Returns `UserOut` for the token's user. No parameters. Errors: 401.

## 4. `PATCH /users/me`
* **Body (`UserUpdate`, all optional):** `name` (1–120), `phone` (≤ 30; `null` clears), `monthly_income` (≥ 0).
* **Logic (inline in router):** uses `model_dump(exclude_unset=True)`; sets name (`.strip()`), phone, monthly income; commit; refresh.
* **Errors:** 401, 422.
* **Observation:** unlike registration, a whitespace-only `name` of length ≥ 1 passes the schema and is stripped to an empty string (no blank-check validator on `UserUpdate`).

## 5. `POST /accounts`
* **Body (`AccountCreate`):** `account_name` (1–120, trimmed, not blank), `account_type` ∈ `savings|checking|credit`, `balance` (≥ 0, default 0), `currency` (exactly 3 chars, default `INR`, stored upper-cased).
* **Response 201 (`AccountOut`):** `id, user_id, account_name, account_type, balance, currency, created_at`.
* **DB:** `INSERT accounts` (`user_id` taken from the token), commit.
* **Errors:** 401, 422 (e.g. invalid `account_type`, negative balance).
* **Meaning of `balance`:** funds held for savings/checking; **amount owed** for credit.

## 6. `GET /accounts`
Auth. Returns `list[AccountOut]` of the caller's accounts ordered by `id`.

## 7. `GET /accounts/{account_id}`
Auth. `get_owned_account`. Errors: **404** `Account not found`; **403** `You do not have access to this account`.

## 8. `PATCH /accounts/{account_id}`
* **Body (`AccountUpdate`):** `account_name` (1–120).
* **Behaviour:** changes the **name only**. Type, balance and currency cannot be changed. Name is `.strip()`-ed in the service (a whitespace-only value of length ≥ 1 would become empty — same observation as §4).
* **Errors:** 401, 403, 404, 422.

## 9. `DELETE /accounts/{account_id}`
* **Response:** `204 No Content`.
* **Behaviour:** `db.delete(account)` — the ORM relationship `Account.transactions` has `cascade="all, delete-orphan"`, so **all its transactions are deleted in the same DB transaction**. Budgets and alerts are untouched. The **counterpart leg of a transfer on another account is not removed** (documented in `PROJECT_PROGRESS.md`). Rolls back on exception.
* **Errors:** 401, 403, 404.

## 10. `GET /accounts/{account_id}/summary`
* **Response (`AccountSummary`):**
  * `account_id`, `balance`;
  * `total_credit`, `total_debit` — `SUM(amount)` grouped by type over **all** the account's transactions (**transfer legs included**);
  * `spending_by_category` — dict category → debit total, **excluding transfer legs**, sorted descending;
  * `monthly_trend` — exactly 6 items (current month and the 5 before; zero-filled), each `{month:"YYYY-MM", year, month_number, spending, income}` where spending = non-transfer debits, income = non-transfer credits.
* **Dependencies:** `today` via `get_today`.
* **Errors:** 401, 403, 404.

## 11. `POST /transactions`
* **Body (`TransactionCreate`):** `account_id`, `amount` (> 0, ≤ 2 dp), `type` ∈ `credit|debit`, `category` ∈ `food|transport|utilities|entertainment|health|salary|other`, `description` (1–500, trimmed, not blank), `merchant` (optional ≤ 200, blank → `null`), `transaction_date` (ISO date; no range restriction).
* **Response 201 (`TransactionOut`):** includes `is_transfer` (false here) and `transfer_group` (null).
* **Business rules / DB (one DB transaction):** see [Business_Logic §2](Business_Logic.md): ownership check → salary-debit rejection → guarded balance `UPDATE` → `INSERT` → alert check for debits → commit.
* **Errors:** 401; **403/404** foreign/missing account; **400** `Insufficient balance` (savings/checking only); **422** invalid fields or `The salary category is income only (credit)`.

## 12. `GET /transactions`
* **Query:** `account_id`, `category`, `type`, `date_from`, `date_to` (inclusive both ends), `page` (≥ 1, default 1), `page_size` (1–100, default 20).
* **Response (`TransactionPage`):** `{items, total, page, page_size, pages}`; `pages = max(1, ceil(total/page_size))`. Ordering: `transaction_date DESC, id DESC`. Scope: only transactions of the caller's accounts (or one owned account).
* **Errors:** 401; 403/404 when `account_id` is foreign/missing; 422 for invalid enum/date/page values. Transfer legs **are included** in this list (flagged `is_transfer`).

## 13. `GET /transactions/{transaction_id}`
`get_owned_transaction` (ownership via `transaction.account.user_id`). Errors: 404 `Transaction not found`, 403 `You do not have access to this transaction`.

## 14. `POST /transfers`
* **Body (`TransferCreate`):** `source_account_id`, `destination_account_id`, `amount` (> 0), `transfer_date` (optional, default today), `description` (default `Transfer`, 1–500).
* **Response 201 (`TransferOut`):** `transfer_group` (UUID string), `debit`, `credit` (both `TransactionOut`), `source_balance`, `destination_balance`.
* **Behaviour:** one DB transaction: debit leg on source (guarded) and credit leg on destination, both `category=other`, `is_transfer=True`, shared `transfer_group`. Typical use: paying a credit-card bill (credit account balance is *reduced*).
* **Errors:** 422 `Source and destination accounts must be different`; 403/404 for foreign/missing accounts; 400 `Insufficient balance` when the source is a savings/checking account.

## 15. `POST /budgets`
* **Body (`BudgetCreate`):** `category` (any except `salary`), `monthly_limit` (> 0), `month` (1–12), `year` (2000–2100).
* **Response 201 (`BudgetOut`):** `id, category, monthly_limit, month, year, created_at, spent, remaining, utilization_percent, has_alert, alerts[]`.
* **Errors:** **409** `A budget for this category, month and year already exists`; 422 (including `Budgets cannot be set for the salary category (income only)`).
* **No alert is evaluated on creation.**

## 16. `GET /budgets`
Query `month` (1–12) and/or `year` (2000–2100) — both optional and independent. Ordered `year DESC, month DESC, category`. Each item has live `spent` (non-transfer debits in that category/month across **all** the user's accounts).

## 17. `GET /budgets/{budget_id}` · 18. `DELETE /budgets/{budget_id}`
Ownership via `get_owned_budget` (404/403). Delete returns 204 and removes the budget's alerts (ORM cascade).

## 19. `GET /budget-alerts`
Query `month`, `year` (optional). Returns `BudgetAlertDetail[]`: `id, budget_id, category, month, year, alert_type (warning_80|exceeded), triggered_at`, newest first, joined to the user's budgets.

## 20. `GET /dashboard`
* **Query:** `month`, `year` (optional, each defaults independently to today's month/year).
* **Response (`DashboardOut`):** `month, year, total_balance, total_assets, total_liabilities, monthly_income, monthly_expenses, net_cash_flow, savings_rate, top_3_categories[], budget_alerts_count, recent_transactions[5], budget_utilization[]`.
* Formulas: [Business_Logic §5](Business_Logic.md).

## 21. `GET /analytics/spending-by-category`
* **Query:** `month`+`year` (must be supplied together, else **422** `month and year must be provided together`), or `date_from`/`date_to` (inclusive; internally `end = date_to + 1 day`), plus optional `account_id` (ownership-checked → 403/404).
* If both `month`/`year` are given they override `date_from/date_to`. With no filters at all it aggregates all time.
* **Response:** `[{category, amount}]` sorted by amount descending; non-transfer debits only.

## 22. `GET /analytics/income-vs-expense`
* **Query:** `months` (1–24, default 6).
* **Response:** oldest → newest list of `{month:"YYYY-MM", year, month_number, income, expenses}` ending at the current month (zero-filled).

## 23. `GET /health`
No auth; `{"status": "ok"}`. Used by the live-backend test fixture to wait for startup.

---

## Example calls

```bash
# register + login
curl -X POST http://127.0.0.1:8000/api/v1/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Demo","email":"demo@example.com","password":"changeme123","monthly_income":80000}'
curl -X POST http://127.0.0.1:8000/api/v1/auth/login -d 'username=demo@example.com&password=changeme123'

# authorised call
curl http://127.0.0.1:8000/api/v1/accounts -H "Authorization: Bearer $TOKEN"
```
