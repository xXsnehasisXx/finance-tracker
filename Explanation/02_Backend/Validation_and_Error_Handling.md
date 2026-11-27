# Validation and Error Handling

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Sources: [`core/exceptions.py`](../../backend/app/core/exceptions.py), [`app/main.py`](../../backend/app/main.py), [`schemas/__init__.py`](../../backend/app/schemas/__init__.py). Frontend counterpart: [Client_Side_Validation](../03_Frontend/Client_Side_Validation.md).

## 1. Server-side validation vs client-side validation

| | Client-side (React) | Server-side (FastAPI) |
|---|---|---|
| Purpose | fast feedback, fewer wasted requests | **the only trustworthy check**; also used by Streamlit/MCP/agents/curl |
| Can be bypassed? | Yes (devtools, other clients) | No |
| Where | `forms.jsx`, `AuthPages.jsx`, `Profile.jsx` | Pydantic schemas → service rules → DB constraints |

The backend never relies on the frontend. Most front-end rules are intentionally duplicated here; a few rules exist only in the backend (e.g. password ≤ 72 bytes, year range for budgets, insufficient balance, uniqueness).

## 2. Three validation layers (defence in depth)

1. **Pydantic (HTTP boundary).** Types, ranges (`gt=0`, `ge=0`, `min_length`, `max_length`, `max_digits=14`, `decimal_places=2`), enums, `EmailStr`, custom `field_validator`s (strip & non-blank for names/descriptions, lower-case email, bcrypt byte limit, no budget for salary). Failure → **422**.
2. **Service layer (business rules).** Ownership, salary-credit-only, insufficient balance, duplicate budget/email, same-account transfer. Failure → `AppError` subclass.
3. **Database constraints (last line).** `UNIQUE` (email, budget key, alert key), `CHECK` (amount > 0, month 1–12, limit > 0), FK, NOT NULL. A violation surfaces as `IntegrityError`, converted to 409 where a race is plausible (register, create budget).

## 3. Exception hierarchy

```python
class AppError(Exception):            status_code = 400;  detail
class NotFoundError(AppError):        status_code = 404
class ForbiddenError(AppError):       status_code = 403
class ConflictError(AppError):        status_code = 409
class InsufficientBalanceError(AppError): status_code = 400
class DomainValidationError(AppError):    status_code = 422
```

`main.py` registers handlers:

```python
@app.exception_handler(AppError)
async def app_error_handler(_, exc): return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_handler(_, exc):
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})
```

The custom 422 handler flattens Pydantic errors to `loc/msg/type` only (it drops `input` and `ctx`, which avoids echoing submitted values such as passwords back in the response).

`HTTPException` (used for 401 auth failures and the analytics `month`/`year` pairing 422) is handled by FastAPI's default handler and also returns `{"detail": "..."}`.

## 4. Status-code catalogue

| Code | When | Example `detail` |
|---|---|---|
| 200 / 201 / 204 | success / created / deleted | — |
| 400 | insufficient balance | `Insufficient balance` |
| 401 | missing/invalid token, wrong login | `Not authenticated`, `Could not validate credentials`, `Incorrect email or password` |
| 403 | another user's account/budget/transaction | `You do not have access to this account` |
| 404 | id does not exist | `Account not found`, `Budget not found`, `Transaction not found` |
| 409 | duplicate email or budget | `Email is already registered`, `A budget for this category, month and year already exists` |
| 422 | schema/rule violation | list of `{loc,msg,type}`; or string such as `The salary category is income only (credit)`, `Source and destination accounts must be different`, `month and year must be provided together` |
| 500 | unexpected exception | logged as `unhandled_exception` with traceback; default FastAPI response |

## 5. Transactions and error handling

`create_transaction` / `create_transfer` catch **any** exception, `rollback()`, and re-raise, so a failure after the balance update (e.g. a DB error on insert) never leaves a half-applied change. The session is closed by `get_db`'s `finally`.

## 6. Logging errors safely

* `auth_failure` events record a `reason` and path, never the token or password.
* The request middleware logs method/path/status/duration only (no bodies).
* The AI layer logs error *types* (`error_type=type(exc).__name__`) rather than messages that could contain data.
* Test assertions: tokens absent from logs (see [Authentication_and_JWT §8](Authentication_and_JWT.md)).

## 7. Mapping to the UI and AI clients

* React `api.js::describe(detail)` turns a 422 array into `field: message; …` text, a string detail into itself; network failure → `ApiError(0, "Cannot reach the server. Is the backend running?")`.
* `ai/common/api_client.py` maps statuses to readable strings (401 *"Not authenticated…"*, 403 *"Access denied…"*, 404/409/422 with detail, ≥ 500 generic) and converts timeouts/connection errors into `ApiResult(ok=False, error=…)`; AI tools never raise.

## 8. Known gaps

* No rate limiting, no request-size limits beyond field lengths.
* A whitespace-only `name` in `PATCH /users/me` or `PATCH /accounts/{id}` is accepted by the schema (length ≥ 1) and stripped to empty — registration/creation have non-blank validators, updates do not.
* `transaction_date` has no min/max (future or far-past dates are accepted).
* `currency` is validated only as a 3-character string (no ISO list); everything is displayed in INR by the frontend.
