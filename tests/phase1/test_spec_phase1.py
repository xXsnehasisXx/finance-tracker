"""POC-02 Phase 1 spec tests (TC-02-P1-*), reproduced from extras/tests/phase1-test-spec.md.
Run with the frozen spec clock (2026-06-18) provided by the repo-root conftest.py.
"""
import datetime
from unittest.mock import MagicMock


# ------------------------------------------------------------------ UNIT
def _txn_mock(account_id, amount, type_, category, description, date, merchant=None):
    m = MagicMock()
    m.account_id = account_id
    m.amount = amount
    m.type = type_
    m.category = category
    m.description = description
    m.transaction_date = date
    if merchant is not None:
        m.merchant = merchant
    dump = {"account_id": account_id, "amount": amount, "type": type_, "category": category,
            "description": description, "transaction_date": date}
    m.model_dump.return_value = dump
    return m


def test_tc_p1_unit_01_debit_decreases_balance(db_session):
    from app.models.account import Account
    from app.services.transaction_service import create_transaction

    account = Account(account_name="Test Savings", account_type="savings", balance=10000.0, user_id=1, currency="INR")
    db_session.add(account)
    db_session.commit()
    txn = _txn_mock(account.id, 2000.0, "debit", "food", "Grocery shopping", datetime.date(2026, 6, 15), "BigBazaar")
    result = create_transaction(db_session, txn, user_id=1)
    db_session.refresh(account)
    assert account.balance == 8000.0
    assert result.amount == 2000.0
    assert result.type == "debit"


def test_tc_p1_unit_02_credit_increases_balance(db_session):
    from app.models.account import Account
    from app.services.transaction_service import create_transaction

    account = Account(account_name="Test Account", account_type="savings", balance=5000.0, user_id=1, currency="INR")
    db_session.add(account)
    db_session.commit()
    txn = _txn_mock(account.id, 80000.0, "credit", "salary", "Monthly salary", datetime.date(2026, 6, 1))
    result = create_transaction(db_session, txn, user_id=1)
    db_session.refresh(account)
    assert account.balance == 85000.0
    assert result.type == "credit"


def _budget_fixture(db_session, spent, day):
    from app.models.account import Account
    from app.models.budget import Budget
    from app.models.transaction import Transaction

    account = Account(account_name="Test", account_type="savings", balance=50000.0, user_id=1, currency="INR")
    db_session.add(account)
    db_session.flush()
    budget = Budget(user_id=1, category="food", monthly_limit=10000.0, month=6, year=2026)
    db_session.add(budget)
    db_session.flush()
    db_session.add(Transaction(account_id=account.id, amount=spent, type="debit", category="food",
                               description="Food", transaction_date=datetime.date(2026, 6, day)))
    db_session.flush()
    return budget


def test_tc_p1_unit_03_alert_at_80_percent(db_session):
    from app.models.budget_alert import AlertType, BudgetAlert
    from app.services.budget_alert_service import check_and_create_alerts

    budget = _budget_fixture(db_session, 8000.0, 10)
    check_and_create_alerts(db_session, 1, "food", datetime.date(2026, 6, 10))
    db_session.commit()
    alert = db_session.query(BudgetAlert).filter(BudgetAlert.budget_id == budget.id, BudgetAlert.alert_type == AlertType.warning_80).first()
    assert alert is not None and alert.alert_type == AlertType.warning_80


def test_tc_p1_unit_04_alert_at_100_percent(db_session):
    from app.models.budget_alert import AlertType, BudgetAlert
    from app.services.budget_alert_service import check_and_create_alerts

    budget = _budget_fixture(db_session, 10000.0, 15)
    check_and_create_alerts(db_session, 1, "food", datetime.date(2026, 6, 15))
    db_session.commit()
    assert db_session.query(BudgetAlert).filter(BudgetAlert.budget_id == budget.id, BudgetAlert.alert_type == AlertType.exceeded).first() is not None


def test_tc_p1_unit_05_duplicate_alert_not_created(db_session):
    from app.models.budget_alert import AlertType, BudgetAlert
    from app.services.budget_alert_service import check_and_create_alerts

    budget = _budget_fixture(db_session, 8500.0, 10)
    check_and_create_alerts(db_session, 1, "food", datetime.date(2026, 6, 10))
    db_session.flush()
    check_and_create_alerts(db_session, 1, "food", datetime.date(2026, 6, 10))
    db_session.commit()
    assert db_session.query(BudgetAlert).filter(BudgetAlert.budget_id == budget.id, BudgetAlert.alert_type == AlertType.warning_80).count() == 1


def test_tc_p1_unit_06_category_enum_validation():
    from app.models.transaction import TransactionCategory

    values = [c.value for c in TransactionCategory]
    for cat in ["food", "transport", "utilities", "entertainment", "health", "salary", "other"]:
        assert cat in values
    assert "shopping" not in values and "rent" not in values


def test_tc_p1_unit_07_monthly_summary_calculation(db_session):
    from sqlalchemy import and_, func

    from app.models.account import Account
    from app.models.transaction import Transaction

    account = Account(account_name="Test", account_type="savings", balance=50000.0, user_id=1, currency="INR")
    db_session.add(account)
    db_session.flush()
    db_session.add_all([
        Transaction(account_id=account.id, amount=8000.0, type="debit", category="food", description="Food", transaction_date=datetime.date(2026, 6, 10)),
        Transaction(account_id=account.id, amount=3000.0, type="debit", category="transport", description="Transport", transaction_date=datetime.date(2026, 6, 15)),
        Transaction(account_id=account.id, amount=80000.0, type="credit", category="salary", description="Salary", transaction_date=datetime.date(2026, 6, 1)),
    ])
    db_session.commit()

    def total(kind):
        return db_session.query(func.sum(Transaction.amount)).filter(and_(
            Transaction.account_id == account.id, Transaction.type == kind,
            func.strftime("%Y", Transaction.transaction_date) == "2026",
            func.strftime("%m", Transaction.transaction_date) == "06")).scalar()

    assert total("debit") == 11000.0
    assert total("credit") == 80000.0


def test_tc_p1_unit_08_savings_rate_calculation():
    from app.services.dashboard_service import savings_rate

    assert abs(savings_rate(80000, 55000) - 31.25) < 0.01
    assert savings_rate(0, 5000) == 0.0
    assert savings_rate(80000, 0) == 100.0
    assert savings_rate(50000, 60000) == -20.0


# ------------------------------------------------------------------ API
def test_tc_p1_api_01_post_debit_returns_201(client, auth_headers, test_account):
    r = client.post("/api/v1/transactions", json={
        "account_id": test_account["id"], "amount": 1500.0, "type": "debit", "category": "food",
        "description": "Weekly grocery run", "merchant": "Reliance Fresh", "transaction_date": "2026-06-15"}, headers=auth_headers)
    assert r.status_code == 201
    d = r.json()
    assert d["amount"] == 1500.0 and d["category"] == "food" and d["type"] == "debit" and "id" in d


def test_tc_p1_api_02_invalid_account_returns_404(client, auth_headers):
    r = client.post("/api/v1/transactions", json={
        "account_id": 99999, "amount": 500.0, "type": "debit", "category": "food",
        "description": "Test", "transaction_date": "2026-06-15"}, headers=auth_headers)
    assert r.status_code == 404


def test_tc_p1_api_03_account_summary_aggregations(client, auth_headers, test_account):
    for _ in range(3):
        client.post("/api/v1/transactions", json={
            "account_id": test_account["id"], "amount": 2000.0, "type": "debit", "category": "food",
            "description": "Food expense", "transaction_date": "2026-06-10"}, headers=auth_headers)
    r = client.get(f"/api/v1/accounts/{test_account['id']}/summary", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    for key in ("total_credit", "total_debit", "balance", "spending_by_category", "monthly_trend"):
        assert key in d
    assert d["total_debit"] == 6000.0 and "food" in d["spending_by_category"]


def test_tc_p1_api_04_category_filter(client, auth_headers, test_account):
    for amt, cat, desc, day in ((500.0, "food", "Pizza", "2026-06-10"), (200.0, "transport", "Cab", "2026-06-11")):
        client.post("/api/v1/transactions", json={
            "account_id": test_account["id"], "amount": amt, "type": "debit", "category": cat,
            "description": desc, "transaction_date": day}, headers=auth_headers)
    r = client.get(f"/api/v1/transactions?account_id={test_account['id']}&category=food", headers=auth_headers)
    assert r.status_code == 200
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    assert len(items) >= 1 and all(t["category"] == "food" for t in items)


def test_tc_p1_api_05_post_budget_returns_201(client, auth_headers):
    r = client.post("/api/v1/budgets", json={"category": "food", "monthly_limit": 10000.0, "month": 6, "year": 2026}, headers=auth_headers)
    assert r.status_code == 201
    d = r.json()
    assert d["category"] == "food" and d["monthly_limit"] == 10000.0 and d["month"] == 6 and d["year"] == 2026


def test_tc_p1_api_06_duplicate_budget_returns_409(client, auth_headers):
    body = {"category": "transport", "monthly_limit": 5000.0, "month": 6, "year": 2026}
    client.post("/api/v1/budgets", json=body, headers=auth_headers)
    assert client.post("/api/v1/budgets", json=body, headers=auth_headers).status_code == 409


def test_tc_p1_api_07_budgets_utilization(client, auth_headers, test_account):
    client.post("/api/v1/budgets", json={"category": "entertainment", "monthly_limit": 2000.0, "month": 6, "year": 2026}, headers=auth_headers)
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"], "amount": 1000.0, "type": "debit", "category": "entertainment",
        "description": "Movie tickets", "transaction_date": "2026-06-10"}, headers=auth_headers)
    r = client.get("/api/v1/budgets", headers=auth_headers)
    assert r.status_code == 200
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    ent = next((b for b in items if b["category"] == "entertainment"), None)
    assert ent is not None
    assert "spent" in ent and "remaining" in ent and "utilization_percent" in ent
    assert ent["spent"] == 1000.0 and ent["utilization_percent"] == 50.0


def test_tc_p1_api_08_dashboard_all_metrics(client, auth_headers, test_account):
    """Unmodified spec scenario: no period parameters; relies on the frozen spec clock (2026-06-18)."""
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"], "amount": 80000.0, "type": "credit", "category": "salary",
        "description": "Monthly salary", "transaction_date": "2026-06-01"}, headers=auth_headers)
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"], "amount": 5000.0, "type": "debit", "category": "food",
        "description": "Groceries", "transaction_date": "2026-06-10"}, headers=auth_headers)
    r = client.get("/api/v1/dashboard", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    for key in ("total_balance", "monthly_income", "monthly_expenses", "savings_rate", "top_3_categories", "budget_alerts_count"):
        assert key in d
    assert d["monthly_income"] == 80000.0 and d["monthly_expenses"] == 5000.0


# ------------------------------------------------------------------ DB
def test_tc_p1_db_01_transaction_persisted(client, auth_headers, test_account):
    r = client.post("/api/v1/transactions", json={
        "account_id": test_account["id"], "amount": 750.0, "type": "debit", "category": "transport",
        "description": "Monthly metro pass", "merchant": "DMRC", "transaction_date": "2026-06-01"}, headers=auth_headers)
    assert r.status_code == 201
    g = client.get(f"/api/v1/transactions/{r.json()['id']}", headers=auth_headers)
    assert g.status_code == 200
    d = g.json()
    assert d["amount"] == 750.0 and d["category"] == "transport" and d["merchant"] == "DMRC" and d["transaction_date"] == "2026-06-01"


def test_tc_p1_db_02_account_balance_updated(client, auth_headers, test_account):
    initial = test_account["balance"]
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"], "amount": 3000.0, "type": "debit", "category": "utilities",
        "description": "Electricity bill", "transaction_date": "2026-06-05"}, headers=auth_headers)
    r = client.get(f"/api/v1/accounts/{test_account['id']}", headers=auth_headers)
    assert r.status_code == 200 and r.json()["balance"] == initial - 3000.0


def test_tc_p1_db_03_budget_created(client, auth_headers):
    r = client.post("/api/v1/budgets", json={"category": "health", "monthly_limit": 3000.0, "month": 6, "year": 2026}, headers=auth_headers)
    assert r.status_code == 201
    g = client.get(f"/api/v1/budgets/{r.json()['id']}", headers=auth_headers)
    assert g.status_code == 200
    d = g.json()
    assert d["category"] == "health" and d["monthly_limit"] == 3000.0 and d["month"] == 6


def test_tc_p1_db_04_budget_alert_created_at_threshold(client, auth_headers, test_account):
    client.post("/api/v1/budgets", json={"category": "food", "monthly_limit": 5000.0, "month": 6, "year": 2026}, headers=auth_headers)
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"], "amount": 4500.0, "type": "debit", "category": "food",
        "description": "Grocery month", "transaction_date": "2026-06-20"}, headers=auth_headers)
    r = client.get("/api/v1/budgets", headers=auth_headers)
    assert r.status_code == 200
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    food = next((b for b in items if b["category"] == "food"), None)
    assert food is not None and food.get("has_alert") is True
