"""Accounts + transactions: validation, account-type balance rules, atomicity, authorization."""
import pytest


def _acct(client, headers, name="Acc", type_="savings", balance=1000):
    r = client.post("/api/v1/accounts", json={"account_name": name, "account_type": type_, "balance": balance}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _txn(client, headers, account_id, amount, type_="debit", category="food", date="2026-06-10", **extra):
    return client.post("/api/v1/transactions", json={
        "account_id": account_id, "amount": amount, "type": type_, "category": category,
        "description": "x", "transaction_date": date, **extra}, headers=headers)


def test_account_crud_and_validation(client, auth_headers):
    a = _acct(client, auth_headers, "HDFC Savings", "savings", 50000)
    assert a["balance"] == 50000.0 and a["currency"] == "INR"
    assert client.post("/api/v1/accounts", json={"account_name": "x", "account_type": "gold", "balance": 1}, headers=auth_headers).status_code == 422
    assert client.post("/api/v1/accounts", json={"account_name": "x", "account_type": "savings", "balance": -5}, headers=auth_headers).status_code == 422
    assert client.post("/api/v1/accounts", json={"account_name": "x", "account_type": "savings", "balance": 1}).status_code == 401
    assert len(client.get("/api/v1/accounts", headers=auth_headers).json()) == 1
    r = client.patch(f"/api/v1/accounts/{a['id']}", json={"account_name": "Renamed"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["account_name"] == "Renamed" and r.json()["account_type"] == "savings"


def test_delete_account_cascades_transactions(client, auth_headers, db_session):
    from app.models import Transaction

    a = _acct(client, auth_headers)
    _txn(client, auth_headers, a["id"], 100)
    assert db_session.query(Transaction).count() == 1
    assert client.delete(f"/api/v1/accounts/{a['id']}", headers=auth_headers).status_code == 204
    assert db_session.query(Transaction).count() == 0
    assert client.get(f"/api/v1/accounts/{a['id']}", headers=auth_headers).status_code == 404


def test_debit_credit_update_balance(client, auth_headers):
    a = _acct(client, auth_headers, balance=50000)
    _txn(client, auth_headers, a["id"], 2000)
    _txn(client, auth_headers, a["id"], 80000, "credit", "salary")
    _txn(client, auth_headers, a["id"], 1500)
    assert client.get(f"/api/v1/accounts/{a['id']}", headers=auth_headers).json()["balance"] == 126500.0


@pytest.mark.parametrize("acct_type", ["savings", "checking"])
def test_insufficient_balance_rejected_and_balance_unchanged(client, auth_headers, acct_type, db_session):
    from app.models import Transaction

    a = _acct(client, auth_headers, type_=acct_type, balance=1000)
    r = _txn(client, auth_headers, a["id"], 1000.01)
    assert r.status_code == 400 and "Insufficient balance" in r.json()["detail"]
    assert client.get(f"/api/v1/accounts/{a['id']}", headers=auth_headers).json()["balance"] == 1000.0
    assert db_session.query(Transaction).count() == 0
    assert _txn(client, auth_headers, a["id"], 1000).status_code == 201  # exactly zero is allowed
    assert client.get(f"/api/v1/accounts/{a['id']}", headers=auth_headers).json()["balance"] == 0.0


def test_credit_account_balance_is_amount_owed(client, auth_headers):
    card = _acct(client, auth_headers, "ICICI Card", "credit", 0)
    assert _txn(client, auth_headers, card["id"], 5000).status_code == 201  # spend: debt increases, no rejection
    assert client.get(f"/api/v1/accounts/{card['id']}", headers=auth_headers).json()["balance"] == 5000.0
    assert _txn(client, auth_headers, card["id"], 2000, "credit", "other").status_code == 201  # payment/refund: debt decreases
    assert client.get(f"/api/v1/accounts/{card['id']}", headers=auth_headers).json()["balance"] == 3000.0


def test_transaction_validation(client, auth_headers):
    a = _acct(client, auth_headers)
    assert _txn(client, auth_headers, a["id"], 0).status_code == 422
    assert _txn(client, auth_headers, a["id"], -5).status_code == 422
    assert _txn(client, auth_headers, a["id"], 10, category="shopping").status_code == 422
    assert _txn(client, auth_headers, a["id"], 10, type_="expense").status_code == 422
    assert _txn(client, auth_headers, a["id"], 10, date="15/06/2026").status_code == 422
    assert _txn(client, auth_headers, a["id"], 10, category="salary").status_code == 422  # salary is income only
    assert _txn(client, auth_headers, a["id"], 10.005).status_code == 422  # more than 2 decimal places
    assert client.post("/api/v1/transactions", json={"account_id": a["id"], "amount": 5, "type": "debit", "category": "food", "transaction_date": "2026-06-01"}, headers=auth_headers).status_code == 422


def test_decimal_safe_arithmetic(client, auth_headers):
    a = _acct(client, auth_headers, balance=1.0)
    for _ in range(10):
        assert _txn(client, auth_headers, a["id"], 0.1).status_code == 201
    assert client.get(f"/api/v1/accounts/{a['id']}", headers=auth_headers).json()["balance"] == 0.0  # float math would leave 1.4e-16 / reject


def test_filters_pagination_and_invalid_dates(client, auth_headers):
    a = _acct(client, auth_headers, balance=100000)
    for i in range(25):
        _txn(client, auth_headers, a["id"], 10, category="food" if i % 2 else "transport", date=f"2026-06-{i + 1:02d}")
    _txn(client, auth_headers, a["id"], 500, "credit", "salary", "2026-06-01")
    p1 = client.get("/api/v1/transactions", headers=auth_headers).json()
    assert p1["total"] == 26 and len(p1["items"]) == 20 and p1["pages"] == 2 and p1["page"] == 1
    assert len(client.get("/api/v1/transactions?page=2", headers=auth_headers).json()["items"]) == 6
    f = client.get("/api/v1/transactions?category=food&type=debit&date_from=2026-06-01&date_to=2026-06-10", headers=auth_headers).json()
    assert f["total"] == 5 and all(t["category"] == "food" and "2026-06-01" <= t["transaction_date"] <= "2026-06-10" for t in f["items"])
    assert client.get("/api/v1/transactions?date_from=2026/06/01", headers=auth_headers).status_code == 422
    assert client.get("/api/v1/transactions?category=nope", headers=auth_headers).status_code == 422
    assert client.get("/api/v1/transactions?page_size=1000", headers=auth_headers).status_code == 422


def test_empty_account_summary_is_zeros(client, auth_headers):
    a = _acct(client, auth_headers, balance=0)
    d = client.get(f"/api/v1/accounts/{a['id']}/summary", headers=auth_headers).json()
    assert d["total_credit"] == 0 and d["total_debit"] == 0 and d["spending_by_category"] == {} and len(d["monthly_trend"]) == 6


def test_summary_monthly_trend_last_six_months(client, auth_headers):
    a = _acct(client, auth_headers, balance=100000)
    _txn(client, auth_headers, a["id"], 100, date="2026-01-15")
    _txn(client, auth_headers, a["id"], 200, date="2026-06-15")
    _txn(client, auth_headers, a["id"], 999, date="2025-12-31")  # outside the 6-month window
    trend = client.get(f"/api/v1/accounts/{a['id']}/summary", headers=auth_headers).json()["monthly_trend"]
    assert [t["month"] for t in trend] == ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    assert trend[0]["spending"] == 100.0 and trend[-1]["spending"] == 200.0 and sum(t["spending"] for t in trend) == 300.0


# ------------------------------------------------------------------ authorization (cross-user)
def test_cross_user_access_is_blocked(client, auth_headers, other_headers):
    a = _acct(client, auth_headers, balance=1000)
    t = _txn(client, auth_headers, a["id"], 50).json()
    b = client.post("/api/v1/budgets", json={"category": "food", "monthly_limit": 100, "month": 6, "year": 2026}, headers=auth_headers).json()
    # other user cannot read/modify/delete/spend from my resources
    assert client.get(f"/api/v1/accounts/{a['id']}", headers=other_headers).status_code == 403
    assert client.get(f"/api/v1/accounts/{a['id']}/summary", headers=other_headers).status_code == 403
    assert client.patch(f"/api/v1/accounts/{a['id']}", json={"account_name": "hax"}, headers=other_headers).status_code == 403
    assert client.delete(f"/api/v1/accounts/{a['id']}", headers=other_headers).status_code == 403
    assert client.get(f"/api/v1/transactions/{t['id']}", headers=other_headers).status_code == 403
    assert _txn(client, other_headers, a["id"], 1).status_code == 403
    assert client.get(f"/api/v1/transactions?account_id={a['id']}", headers=other_headers).status_code == 403
    assert client.get(f"/api/v1/budgets/{b['id']}", headers=other_headers).status_code == 403
    assert client.delete(f"/api/v1/budgets/{b['id']}", headers=other_headers).status_code == 403
    # lists never leak
    assert client.get("/api/v1/accounts", headers=other_headers).json() == []
    assert client.get("/api/v1/transactions", headers=other_headers).json()["total"] == 0
    assert client.get("/api/v1/budgets", headers=other_headers).json() == []
    assert client.get("/api/v1/dashboard", headers=other_headers).json()["total_balance"] == 0
    # my data is untouched
    assert client.get(f"/api/v1/accounts/{a['id']}", headers=auth_headers).json()["balance"] == 950.0


def test_cannot_transfer_to_or_from_foreign_account(client, auth_headers, other_headers):
    mine = _acct(client, auth_headers, balance=500)
    theirs = _acct(client, other_headers, balance=500)
    for src, dst in ((mine, theirs), (theirs, mine)):
        r = client.post("/api/v1/transfers", json={"source_account_id": src["id"], "destination_account_id": dst["id"], "amount": 10}, headers=auth_headers)
        assert r.status_code == 403
    assert client.get(f"/api/v1/accounts/{mine['id']}", headers=auth_headers).json()["balance"] == 500.0
    assert client.get(f"/api/v1/accounts/{theirs['id']}", headers=other_headers).json()["balance"] == 500.0
