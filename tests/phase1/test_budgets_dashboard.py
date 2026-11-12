"""Budgets, alert thresholds, dashboard rules (assets/liabilities/income/expenses), transfers, clock semantics."""
import datetime

import pytest


def _acct(client, headers, name="Acc", type_="savings", balance=100000):
    return client.post("/api/v1/accounts", json={"account_name": name, "account_type": type_, "balance": balance}, headers=headers).json()


def _txn(client, headers, account_id, amount, type_="debit", category="food", date="2026-06-10"):
    r = client.post("/api/v1/transactions", json={"account_id": account_id, "amount": amount, "type": type_, "category": category,
                                                  "description": "x", "transaction_date": date}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _budget(client, headers, category="food", limit=10000, month=6, year=2026):
    r = client.post("/api/v1/budgets", json={"category": category, "monthly_limit": limit, "month": month, "year": year}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _alerts(client, headers, **params):
    return client.get("/api/v1/budget-alerts", params=params, headers=headers).json()


# ------------------------------------------------------------------ budgets
def test_budget_validation(client, auth_headers):
    base = {"category": "food", "monthly_limit": 100, "month": 6, "year": 2026}
    assert client.post("/api/v1/budgets", json={**base, "category": "salary"}, headers=auth_headers).status_code == 422
    assert client.post("/api/v1/budgets", json={**base, "monthly_limit": 0}, headers=auth_headers).status_code == 422
    assert client.post("/api/v1/budgets", json={**base, "month": 13}, headers=auth_headers).status_code == 422
    assert client.post("/api/v1/budgets", json={**base, "category": "bogus"}, headers=auth_headers).status_code == 422
    assert client.post("/api/v1/budgets", json=base).status_code == 401


def test_unique_budget_per_user_category_month_but_not_across_users_or_months(client, auth_headers, other_headers):
    _budget(client, auth_headers)
    assert client.post("/api/v1/budgets", json={"category": "food", "monthly_limit": 1, "month": 6, "year": 2026}, headers=auth_headers).status_code == 409
    _budget(client, auth_headers, month=7)
    _budget(client, auth_headers, category="health")
    _budget(client, other_headers)  # a different user may have the same category/month


@pytest.mark.parametrize("spent,expect", [
    (7999.99, []),
    (8000, ["warning_80"]),
    (9999.99, ["warning_80"]),
    (10000, ["warning_80", "exceeded"]),
    (12000, ["warning_80", "exceeded"]),
])
def test_alert_threshold_boundaries(client, auth_headers, spent, expect):
    acct = _acct(client, auth_headers)
    _budget(client, auth_headers)
    _txn(client, auth_headers, acct["id"], spent)
    assert sorted(a["alert_type"] for a in _alerts(client, auth_headers)) == sorted(expect)


def test_alerts_fire_once_and_escalate(client, auth_headers):
    acct = _acct(client, auth_headers)
    _budget(client, auth_headers)
    _txn(client, auth_headers, acct["id"], 8000)
    _txn(client, auth_headers, acct["id"], 500)  # still only warning
    assert [a["alert_type"] for a in _alerts(client, auth_headers)] == ["warning_80"]
    _txn(client, auth_headers, acct["id"], 1500)  # reaches 100%
    assert sorted(a["alert_type"] for a in _alerts(client, auth_headers)) == ["exceeded", "warning_80"]
    _txn(client, auth_headers, acct["id"], 500)  # beyond 100%: no duplicates
    assert len(_alerts(client, auth_headers)) == 2


def test_no_budget_no_alert_and_credits_never_alert(client, auth_headers):
    acct = _acct(client, auth_headers)
    _txn(client, auth_headers, acct["id"], 9000, category="entertainment")  # no entertainment budget
    _budget(client, auth_headers, category="food", limit=1000)
    _txn(client, auth_headers, acct["id"], 5000, "credit", "other")
    assert _alerts(client, auth_headers) == []


def test_alert_uses_transaction_month_and_other_categories_do_not_count(client, auth_headers):
    acct = _acct(client, auth_headers)
    _budget(client, auth_headers, limit=1000, month=6)
    _txn(client, auth_headers, acct["id"], 900, date="2026-05-30")  # previous month
    _txn(client, auth_headers, acct["id"], 900, category="transport")  # other category
    assert _alerts(client, auth_headers) == []
    _txn(client, auth_headers, acct["id"], 800, date="2026-06-01")
    assert [a["alert_type"] for a in _alerts(client, auth_headers)] == ["warning_80"]


def test_budget_spent_counts_all_user_accounts_and_status_fields(client, auth_headers):
    a1, a2 = _acct(client, auth_headers, "A"), _acct(client, auth_headers, "B", "checking")
    _budget(client, auth_headers, limit=2000)
    _txn(client, auth_headers, a1["id"], 500)
    _txn(client, auth_headers, a2["id"], 700)
    b = client.get("/api/v1/budgets?month=6&year=2026", headers=auth_headers).json()[0]
    assert (b["spent"], b["remaining"], b["utilization_percent"], b["has_alert"]) == (1200.0, 800.0, 60.0, False)
    assert client.get("/api/v1/budgets?month=7&year=2026", headers=auth_headers).json() == []


def test_delete_budget_removes_alerts(client, auth_headers):
    acct = _acct(client, auth_headers)
    b = _budget(client, auth_headers, limit=100)
    _txn(client, auth_headers, acct["id"], 100)
    assert len(_alerts(client, auth_headers)) == 2
    assert client.delete(f"/api/v1/budgets/{b['id']}", headers=auth_headers).status_code == 204
    assert _alerts(client, auth_headers) == [] and client.get(f"/api/v1/budgets/{b['id']}", headers=auth_headers).status_code == 404


# ------------------------------------------------------------------ transfers / dashboard rules
def test_transfer_moves_money_atomically_and_checks_balance(client, auth_headers):
    sav, card = _acct(client, auth_headers, "Sav", "savings", 10000), _acct(client, auth_headers, "Card", "credit", 4000)
    r = client.post("/api/v1/transfers", json={"source_account_id": sav["id"], "destination_account_id": card["id"], "amount": 1500, "transfer_date": "2026-06-12"}, headers=auth_headers)
    assert r.status_code == 201
    b = r.json()
    assert b["source_balance"] == 8500.0 and b["destination_balance"] == 2500.0  # repayment lowers the amount owed
    assert b["debit"]["is_transfer"] and b["credit"]["is_transfer"] and b["debit"]["transfer_group"] == b["credit"]["transfer_group"] == b["transfer_group"]
    # insufficient source: nothing changes at all
    r = client.post("/api/v1/transfers", json={"source_account_id": sav["id"], "destination_account_id": card["id"], "amount": 9000}, headers=auth_headers)
    assert r.status_code == 400
    assert client.get(f"/api/v1/accounts/{sav['id']}", headers=auth_headers).json()["balance"] == 8500.0
    assert client.get(f"/api/v1/accounts/{card['id']}", headers=auth_headers).json()["balance"] == 2500.0
    # validation
    for body in ({"source_account_id": sav["id"], "destination_account_id": sav["id"], "amount": 5},
                 {"source_account_id": sav["id"], "destination_account_id": card["id"], "amount": 0},
                 {"source_account_id": 9999, "destination_account_id": card["id"], "amount": 5}):
        assert client.post("/api/v1/transfers", json=body, headers=auth_headers).status_code in (404, 422)


def test_dashboard_credit_card_purchase_and_repayment_not_double_counted(client, auth_headers):
    sav = _acct(client, auth_headers, "Sav", "savings", 50000)
    card = _acct(client, auth_headers, "Card", "credit", 0)
    _budget(client, auth_headers, "food", 10000)
    _txn(client, auth_headers, sav["id"], 80000, "credit", "salary", "2026-06-01")
    _txn(client, auth_headers, card["id"], 6000, "debit", "food", "2026-06-05")  # card purchase = expense when incurred
    before = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert before["monthly_income"] == 80000.0 and before["monthly_expenses"] == 6000.0
    assert (before["total_assets"], before["total_liabilities"], before["total_balance"]) == (130000.0, 6000.0, 124000.0)

    client.post("/api/v1/transfers", json={"source_account_id": sav["id"], "destination_account_id": card["id"], "amount": 6000, "transfer_date": "2026-06-20"}, headers=auth_headers)
    after = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert after["monthly_income"] == 80000.0  # repayment credit is not income
    assert after["monthly_expenses"] == 6000.0  # repayment debit is not an extra expense
    assert after["savings_rate"] == before["savings_rate"] == 92.5
    assert (after["total_assets"], after["total_liabilities"], after["total_balance"]) == (124000.0, 0.0, 124000.0)
    assert after["top_3_categories"] == [{"category": "food", "amount": 6000.0}]
    budget = client.get("/api/v1/budgets", headers=auth_headers).json()[0]
    assert budget["spent"] == 6000.0  # repayment (category other) does not touch budgets


def test_credit_on_credit_account_is_not_income(client, auth_headers):
    card = _acct(client, auth_headers, "Card", "credit", 5000)
    _txn(client, auth_headers, card["id"], 1000, "credit", "other", "2026-06-02")  # refund/payment
    d = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert d["monthly_income"] == 0 and d["savings_rate"] == 0 and d["total_liabilities"] == 4000.0


def test_transfers_excluded_from_summary_categories_but_included_in_raw_totals(client, auth_headers):
    sav, card = _acct(client, auth_headers, "S", "savings", 1000), _acct(client, auth_headers, "C", "credit", 500)
    client.post("/api/v1/transfers", json={"source_account_id": sav["id"], "destination_account_id": card["id"], "amount": 200}, headers=auth_headers)
    s = client.get(f"/api/v1/accounts/{sav['id']}/summary", headers=auth_headers).json()
    assert s["total_debit"] == 200.0 and s["spending_by_category"] == {} and s["balance"] == 800.0
    tx = client.get("/api/v1/transactions", headers=auth_headers).json()
    assert tx["total"] == 2 and all(t["is_transfer"] for t in tx["items"])  # visible in history, flagged


def test_dashboard_empty_zero_and_period_selection(client, auth_headers):
    d = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert d["monthly_income"] == 0 and d["monthly_expenses"] == 0 and d["savings_rate"] == 0 and d["top_3_categories"] == [] and d["budget_alerts_count"] == 0
    acct = _acct(client, auth_headers)
    _txn(client, auth_headers, acct["id"], 400, "debit", "food", "2026-05-10")
    assert client.get("/api/v1/dashboard", headers=auth_headers).json()["monthly_expenses"] == 0
    assert client.get("/api/v1/dashboard?month=5&year=2026", headers=auth_headers).json()["monthly_expenses"] == 400.0
    assert client.get("/api/v1/dashboard?month=13", headers=auth_headers).status_code == 422


def test_dashboard_top3_alert_count_and_recent(client, auth_headers):
    acct = _acct(client, auth_headers, balance=500000)
    _budget(client, auth_headers, "food", 6000)  # alerts fire on debit recording, so the budget exists first
    for cat, amt in (("food", 5000), ("transport", 4000), ("health", 3000), ("utilities", 2000), ("food", 1000)):
        _txn(client, auth_headers, acct["id"], amt, "debit", cat)  # food reaches 6000 -> 100% -> 2 alerts
    d = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert [c["category"] for c in d["top_3_categories"]] == ["food", "transport", "health"] and d["top_3_categories"][0]["amount"] == 6000.0
    assert d["budget_alerts_count"] == 2 and len(d["recent_transactions"]) == 5
    assert d["budget_utilization"][0]["category"] == "food" and d["budget_utilization"][0]["utilization_percent"] == 100.0


def test_analytics_endpoints(client, auth_headers):
    acct = _acct(client, auth_headers, balance=100000)
    _txn(client, auth_headers, acct["id"], 300, "debit", "food", "2026-06-02")
    _txn(client, auth_headers, acct["id"], 700, "debit", "transport", "2026-05-02")
    _txn(client, auth_headers, acct["id"], 5000, "credit", "salary", "2026-06-01")
    cats = client.get("/api/v1/analytics/spending-by-category", headers=auth_headers).json()
    assert {c["category"]: c["amount"] for c in cats} == {"transport": 700.0, "food": 300.0}
    june = client.get("/api/v1/analytics/spending-by-category?month=6&year=2026", headers=auth_headers).json()
    assert june == [{"category": "food", "amount": 300.0}]
    assert client.get("/api/v1/analytics/spending-by-category?month=6", headers=auth_headers).status_code == 422
    iv = client.get("/api/v1/analytics/income-vs-expense", headers=auth_headers).json()
    assert len(iv) == 6 and iv[-1]["month"] == "2026-06" and iv[-1]["income"] == 5000.0 and iv[-1]["expenses"] == 300.0 and iv[-2]["expenses"] == 700.0


# ------------------------------------------------------------------ clock semantics (production behaviour)
@pytest.mark.real_clock
def test_dashboard_default_period_is_real_current_month(client, auth_headers):
    today = datetime.date.today()
    acct = _acct(client, auth_headers)
    _txn(client, auth_headers, acct["id"], 123, "debit", "food", today.isoformat())
    _txn(client, auth_headers, acct["id"], 999, "debit", "food", (today.replace(day=1) - datetime.timedelta(days=1)).isoformat())
    d = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert (d["month"], d["year"], d["monthly_expenses"]) == (today.month, today.year, 123.0)


def test_spec_clock_is_frozen_only_for_phase1_tests():
    from app.core.clock import get_today
    assert get_today() == datetime.date(2026, 6, 18)


@pytest.mark.real_clock
def test_real_clock_opt_out_uses_system_date():
    from app.core.clock import get_today
    assert get_today() == datetime.date.today()


def test_production_code_contains_no_hardcoded_spec_date():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2] / "backend"
    offenders = [str(p) for p in root.rglob("*.py") if "2026-06" in p.read_text() or "date(2026, 6" in p.read_text()]
    assert offenders == []
