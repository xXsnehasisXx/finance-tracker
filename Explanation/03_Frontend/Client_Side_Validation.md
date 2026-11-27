# Client-Side Validation

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Sources: [`components/forms.jsx`](../../frontend/src/components/forms.jsx), [`pages/AuthPages.jsx`](../../frontend/src/pages/AuthPages.jsx), [`pages/Profile.jsx`](../../frontend/src/pages/Profile.jsx), [`pages/Transactions.jsx`](../../frontend/src/pages/Transactions.jsx). Every rule below exists in code; anything not listed is **not** validated on the client. Server rules: [Validation_and_Error_Handling](../02_Backend/Validation_and_Error_Handling.md).

## 1. Client-side vs server-side validation

* **Client-side** validation improves UX (instant feedback, avoids a round-trip). It runs in the user's browser and can be bypassed, so it is never a security control.
* **Server-side** validation (Pydantic + services + DB) is authoritative. Every client rule below is repeated on the backend unless stated otherwise.

## 2. Mechanics common to all forms

| Aspect | Implementation |
|---|---|
| Native HTML validation | **Disabled** — every `<form>` has `noValidate`, so `type="email"`, `min`, `max`, `required` do not block submission or show browser bubbles (only `maxLength` still limits typing) |
| When validation runs | **On submit only.** There is no `onChange`/`onBlur` validation |
| How invalid submissions are prevented | `useForm.submit` / page `submit` computes an errors object, calls `setErrors(found)`; if it has keys, it returns before any request |
| Error display | `Field` shows the message under the control (`.field-msg`, red border via `.field-error`) |
| Error lifetime | errors are replaced wholesale on every submit; editing a field does **not** clear its message until the next submit |
| Server errors | `useForm` catches the `ApiError` and shows it in a banner (`FormError`, `role="alert"`); Login/Register show it in their own `.form-error` div; Profile/page-level actions use toasts |
| Double-submit | `busy` state disables the submit button and changes its label to "Saving…" |

Shared helpers in `forms.jsx`:

```js
const MONEY = /^\d+(\.\d{1,2})?$/        // digits, optional . and 1–2 decimals; no sign, no commas, no leading "."
const amountError = (v) => (!v ? 'Amount is required'
  : !MONEY.test(v) || Number(v) <= 0 ? 'Enter an amount greater than 0 (max 2 decimals)' : '')
```

## 3. Rules per form

### 3.1 Login (`AuthPages.jsx::Login`)
| Field | Input | Client rule | Message | Backend duplicate? |
|---|---|---|---|---|
| email | `type="email"` | non-empty after `trim()` | `Enter your email and password` (single message for both) | ✅ credentials checked (401) |
| password | `type="password"` | non-empty | same | ✅ |

No email-format check on login (native validation is off).

### 3.2 Register (`AuthPages.jsx::Register`)
| Field | Rule | Message | Backend duplicate |
|---|---|---|---|
| name | required (`trim()`) | `Name is required` | ✅ 1–120, non-blank |
| email | regex `/^\S+@\S+\.\S+$/` | `Enter a valid email` | ✅ `EmailStr` (stricter), lower-cased, uniqueness 409 |
| password | `length >= 8` (characters) | `At least 8 characters` | ✅ min 8 **and** ≤ 72 bytes (the byte limit is *not* checked on the client) |
| monthly_income | optional; if non-empty must match `/^\d+(\.\d{1,2})?$/` | `Enter a valid amount` | ✅ ≥ 0, ≤ 2 dp, ≤ 14 digits |
| phone | none | — | ✅ ≤ 30 chars |

Submit sends `monthly_income: Number(form.monthly_income || 0)` and `phone: form.phone.trim() || null`. After successful registration the user is auto-logged-in.

### 3.3 Account form (`AccountForm`)
| Field | Rule | Message | Backend |
|---|---|---|---|
| account_name | required (`trim()`) | `Account name is required` | ✅ 1–120, non-blank |
| account_type | `<select>` of `savings/checking/credit` (cannot be invalid via UI) | — | ✅ enum |
| balance | must match `MONEY` (0 allowed, negatives/blank rejected) | `Enter a balance of 0 or more` | ✅ `ge=0`, 2 dp |

Label changes with type: credit → "Outstanding amount owed (₹)". No client max length on the name (backend 120).

### 3.4 Rename (`RenameForm`)
`account_name` required (`trim()`), message `Account name is required`. Hint: "The account type cannot be changed."

### 3.5 Transaction form (`TransactionForm`)
| Field | Input | Rule | Message |
|---|---|---|---|
| account_id | `<select>` | truthy | `Choose an account` |
| type | select debit/credit | — | — |
| category | select | **conditional:** `category === 'salary' && type === 'debit'` is invalid | `Salary is income only (credit)` (shown on the category field) |
| amount | text, `inputMode="decimal"` | `amountError` (required, `MONEY`, > 0) | `Amount is required` / `Enter an amount greater than 0 (max 2 decimals)` |
| description | text, `maxLength=500` | required (`trim()`) | `Description is required` |
| merchant | text, `maxLength=200` | optional | — (empty → `null`) |
| transaction_date | `type="date"` | required (non-empty) | `Date is required` |

Not validated client-side: balance sufficiency (backend returns 400 `Insufficient balance`, shown in the banner), date range (future/past allowed), max digits (backend 14).

### 3.6 Transfer form (`TransferForm`)
| Rule | Message |
|---|---|
| source ≠ destination (string compare of ids) | `Choose a different account` (on "To") |
| amount via `amountError` | as above |
| description required (default "Transfer") | `Description is required` |

Date is a `type="date"` input with no required check; balances are not checked (server decides).

### 3.6.1 Budget form (`BudgetForm`)
| Field | Rule |
|---|---|
| category | `<select>` built from `BUDGET_CATEGORIES` (excludes `salary`, hint text explains) |
| monthly_limit | `amountError` (required, `MONEY`, > 0) |
| month | `<select>` 1–12 |
| year | `<input type="number" min="2000" max="2100">` — **min/max are not enforced** (because of `noValidate`) and there is no JS check; the backend enforces 2000–2100 and the 422 is shown in the banner. A cleared year becomes `Number('') = 0`, also rejected by the backend |

Duplicate-budget detection is server-side only (409 shown in the banner).

### 3.7 Profile (`Profile.jsx`)
| Field | Rule | Message |
|---|---|---|
| name | required (`trim()`) | `Name is required` |
| monthly_income | **required** and must match `/^\d+(\.\d{1,2})?$/` (an empty value fails) | `Enter a valid amount` |
| phone | none | — |
| email | disabled input (not editable) | — |

### 3.8 Transactions filter bar (`Transactions.jsx`)
`invalidRange = date_from && date_to && date_from > date_to` renders an inline `"From" date must be before "To" date.` message. It does **not** stop the request.

## 4. Summary matrix

| Rule | Client | Server |
|---|---|---|
| Required text fields | ✅ | ✅ |
| Money format (≤ 2 dp, positive) | ✅ regex | ✅ `Decimal`, `max_digits`, `gt/ge` |
| Email format | ✅ simple regex (register only) | ✅ `EmailStr` |
| Password min length | ✅ 8 | ✅ 8 + 72-byte max |
| Salary must be credit | ✅ | ✅ |
| Budget has no `salary` | ✅ (options hidden) | ✅ |
| Source ≠ destination | ✅ | ✅ |
| Budget month/year range | month via select; year ❌ | ✅ |
| Date required | ✅ | ✅ (parse) |
| Insufficient balance | ❌ | ✅ |
| Unique email / budget | ❌ | ✅ |
| Max field lengths | partial (`maxLength` on description/merchant) | ✅ |

## 5. Suggested improvements (not implemented)

Validate on blur, clear a field's error on edit, enforce the 72-byte password limit and budget-year range in JS, and add `required`/`aria-invalid` attributes. These are listed so reviewers do not assume they exist.
