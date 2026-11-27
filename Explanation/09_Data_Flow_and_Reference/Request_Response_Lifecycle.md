# Request / Response Lifecycle

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). This traces **one HTTP request** through the real code path, using `POST /api/v1/transactions` (a debit) as the example, and then notes where other endpoints differ. Overview of layers: [Backend_Architecture](../02_Backend/Backend_Architecture.md).

## 1. Sequence

```mermaid
sequenceDiagram
    participant C as Client (React api.js)
    participant U as uvicorn
    participant CORS as CORSMiddleware
    participant MW as request_context middleware
    participant R as FastAPI router + validation
    participant D as Dependencies
    participant RT as routers/transactions.py
    participant S as transaction_service
    participant Q as queries.py
    participant AL as budget_alert_service
    participant DB as SQLite
    C->>U: POST /api/v1/transactions JSON + Authorization Bearer
    U->>MW: ASGI request (request_context is added last, so it is the outermost middleware)
    MW->>MW: request_id = header or req_xxx, bind contextvars, start span http.request
    MW->>CORS: call_next
    CORS->>R: pass through (CORS headers added on the way back, preflight answered here)
    R->>D: resolve get_current_user(token, db)
    D->>D: OAuth2PasswordBearer extracts token, then decode_access_token (HS256, exp, sub)
    D->>DB: SELECT users WHERE id = sub
    D-->>R: User (or 401)
    R->>R: parse + validate body -> TransactionCreate (422 on failure)
    R->>RT: create_transaction(payload, user, db)
    RT->>S: create_transaction(db, payload, user.id)
    S->>Q: get_owned_account(db, account_id, user.id)
    Q->>DB: SELECT accounts WHERE id
    Q-->>S: Account (404 or 403 otherwise)
    S->>DB: UPDATE accounts SET balance = balance + delta WHERE id AND balance + delta >= 0
    S->>DB: INSERT transactions + flush
    S->>AL: check_and_create_alerts (debits only)
    AL->>DB: SELECT budget, SUM spent, existing alerts, then INSERT alert rows
    S->>DB: COMMIT
    S-->>RT: Transaction
    RT-->>R: ORM object
    R->>R: serialise with response_model TransactionOut (Decimal to number)
    R-->>MW: 201 JSON
    MW->>MW: log http_request (status, duration_ms) and add x-request-id header
    MW-->>C: 201 + x-request-id
```

## 2. Stage by stage

| # | Stage | Code | Outcome on failure |
|---|---|---|---|
| 1 | **Request context** | `@app.middleware("http") request_context` (registered after CORS, hence outermost in Starlette's stack) | exceptions logged as `unhandled_exception` and re-raised |
| 2 | **CORS** | `CORSMiddleware(allow_origins=settings.cors_origins, …)` | cross-origin preflight answered; disallowed origins get no CORS headers (browser blocks). Same-origin dev traffic (Vite proxy) is unaffected |
| 3 | **Authentication** | `get_current_user` (`core/deps.py`) | 401 `Not authenticated` / `Could not validate credentials` |
| 4 | **DB session** | `get_db` yields a `SessionLocal()`; closed in `finally` | — |
| 5 | **Body validation** | Pydantic `TransactionCreate` (types, `gt=0`, lengths, enums, validators) | 422 `{"detail":[{loc,msg,type}]}` via custom handler |
| 6 | **Authorization** | `get_owned_account` | 404 / 403 |
| 7 | **Business rules** | salary-credit-only, guarded balance update | 422 / 400 `Insufficient balance` |
| 8 | **Persistence** | `INSERT`, `flush`, alert rows, `commit` | any exception → `rollback()` and re-raise → 500 unless it is an `AppError` |
| 9 | **Serialisation** | `response_model=TransactionOut` (`from_attributes`, `MoneyOut`) | — |
| 10 | **Logging** | `http_request` line with `request_id`, `status_code`, `duration_ms`, `status` | — |

Domain exceptions (`AppError` subclasses) raised in stages 6–8 are converted to `{"detail": "<message>"}` with the exception's `status_code` by the registered handler.

## 3. Response shapes

* **201 Created** `TransactionOut`: `{id, account_id, amount, type, category, description, merchant, transaction_date, is_transfer, transfer_group, created_at}`.
* **Errors:** see [Validation_and_Error_Handling §4](../02_Backend/Validation_and_Error_Handling.md).
* Every response carries `x-request-id`; the same id appears in all log lines for that request (contextvars).

## 4. Variations

| Endpoint kind | Difference |
|---|---|
| `POST /auth/login` | no `get_current_user`; body is a form; returns `Token` |
| `GET` list/dashboard endpoints | no commit; aggregations via `queries.py`; `Depends(get_today)` provides the date |
| `DELETE` endpoints | `204` with empty body (`Response(status_code=204)`), ORM cascades |
| `POST /transfers` | two accounts, two guarded updates, two inserts, one commit |
| Health | no auth, no DB |

## 5. Frontend side of the same request

`TransactionForm` (validation) → `useForm.submit` → `api.createTransaction(body)` → `request('/transactions', {method:'POST', body})` → `fetch` → response → either `data` (page closes modal, reloads lists) or `ApiError(status, describe(detail))` (form banner). See [React_Architecture §5](../03_Frontend/React_Architecture.md).

## 6. Timing and observability

Typical log pair for the request (illustrative):

```json
{"event":"balance_updated","account_id":3,"old_balance":10000.0,"new_balance":7500.0,"request_id":"req_…"}
{"event":"transaction_created","transaction_id":41,"type":"debit","amount":2500.0,"category":"food","request_id":"req_…"}
{"event":"http_request","method":"POST","path":"/api/v1/transactions","status_code":201,"duration_ms":14,"status":"success","request_id":"req_…"}
```
(plus `budget_alert_triggered` at warning level if a threshold was crossed). With `OTEL_CONSOLE=true` spans `http.request`, `auth.validate`, `db.query` are printed.
