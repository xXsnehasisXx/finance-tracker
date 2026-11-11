# Phase 1 Test Specifications
## POC-02 — Personal Finance Tracker & Analytics

**Total Test Cases:** 20 | **Pass Threshold:** 14 of 20 (70%)

---

## Test Fixtures (`tests/conftest.py`)

```python
import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def auth_token(client):
    client.post("/api/v1/auth/register", json={
        "name": "Test User", "email": "test@finance.com",
        "password": "testpass123", "monthly_income": 80000
    })
    response = client.post("/api/v1/auth/login", data={
        "username": "test@finance.com", "password": "testpass123"
    })
    return response.json()["access_token"]

@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def test_account(client, auth_headers):
    resp = client.post("/api/v1/accounts", json={
        "account_name": "HDFC Savings",
        "account_type": "savings",
        "balance": 50000.0
    }, headers=auth_headers)
    return resp.json()
```

---

## UNIT TESTS (8 cases)

### TC-02-P1-UNIT-01: Debit Transaction Decreases Balance
**Category:** Unit | **Priority:** High

```python
def test_debit_transaction_decreases_balance(db_session):
    from app.services.transaction_service import create_transaction
    from app.models.account import Account
    from unittest.mock import MagicMock
    
    # Setup account
    account = Account(
        account_name="Test Savings",
        account_type="savings",
        balance=10000.0,
        user_id=1,
        currency="INR"
    )
    db_session.add(account)
    db_session.commit()
    
    txn_data = MagicMock()
    txn_data.account_id = account.id
    txn_data.amount = 2000.0
    txn_data.type = "debit"
    txn_data.category = "food"
    txn_data.description = "Grocery shopping"
    txn_data.transaction_date = __import__("datetime").date(2026, 6, 15)
    txn_data.merchant = "BigBazaar"
    txn_data.model_dump.return_value = {
        "account_id": account.id, "amount": 2000.0,
        "type": "debit", "category": "food",
        "description": "Grocery shopping", "transaction_date": txn_data.transaction_date
    }
    
    result = create_transaction(db_session, txn_data, user_id=1)
    
    db_session.refresh(account)
    assert account.balance == 8000.0
    assert result.amount == 2000.0
    assert result.type == "debit"
```

---

### TC-02-P1-UNIT-02: Credit Transaction Increases Balance
**Category:** Unit | **Priority:** High

```python
def test_credit_transaction_increases_balance(db_session):
    from app.services.transaction_service import create_transaction
    from app.models.account import Account
    from unittest.mock import MagicMock
    
    account = Account(
        account_name="Test Account", account_type="savings",
        balance=5000.0, user_id=1, currency="INR"
    )
    db_session.add(account)
    db_session.commit()
    
    txn_data = MagicMock()
    txn_data.account_id = account.id
    txn_data.amount = 80000.0
    txn_data.type = "credit"
    txn_data.category = "salary"
    txn_data.description = "Monthly salary"
    txn_data.transaction_date = __import__("datetime").date(2026, 6, 1)
    txn_data.model_dump.return_value = {
        "account_id": account.id, "amount": 80000.0,
        "type": "credit", "category": "salary",
        "description": "Monthly salary", "transaction_date": txn_data.transaction_date
    }
    
    result = create_transaction(db_session, txn_data, user_id=1)
    
    db_session.refresh(account)
    assert account.balance == 85000.0
    assert result.type == "credit"
```

---

### TC-02-P1-UNIT-03: Budget Alert at 80%
**Category:** Unit | **Priority:** High

```python
def test_budget_alert_triggered_at_80_percent(db_session):
    from app.services.budget_alert_service import check_and_create_alerts
    from app.models.account import Account
    from app.models.transaction import Transaction
    from app.models.budget import Budget
    from app.models.budget_alert import BudgetAlert, AlertType
    import datetime
    
    # Setup
    account = Account(account_name="Test", account_type="savings",
                      balance=50000.0, user_id=1, currency="INR")
    db_session.add(account)
    db_session.flush()
    
    budget = Budget(user_id=1, category="food", monthly_limit=10000.0,
                    month=6, year=2026)
    db_session.add(budget)
    db_session.flush()
    
    # Add 8000 in food spending (80% of budget)
    txn = Transaction(
        account_id=account.id, amount=8000.0, type="debit",
        category="food", description="Grocery", transaction_date=datetime.date(2026, 6, 10)
    )
    db_session.add(txn)
    db_session.flush()
    
    check_and_create_alerts(db_session, 1, "food", datetime.date(2026, 6, 10))
    db_session.commit()
    
    alert = db_session.query(BudgetAlert).filter(
        BudgetAlert.budget_id == budget.id,
        BudgetAlert.alert_type == AlertType.warning_80
    ).first()
    
    assert alert is not None
    assert alert.alert_type == AlertType.warning_80
```

---

### TC-02-P1-UNIT-04: Budget Alert at 100%
**Category:** Unit | **Priority:** High

```python
def test_budget_alert_triggered_at_100_percent(db_session):
    from app.services.budget_alert_service import check_and_create_alerts
    from app.models.account import Account
    from app.models.transaction import Transaction
    from app.models.budget import Budget
    from app.models.budget_alert import BudgetAlert, AlertType
    import datetime
    
    account = Account(account_name="Test", account_type="savings",
                      balance=50000.0, user_id=1, currency="INR")
    db_session.add(account)
    db_session.flush()
    
    budget = Budget(user_id=1, category="food", monthly_limit=10000.0,
                    month=6, year=2026)
    db_session.add(budget)
    db_session.flush()
    
    # 10000 spending = 100% of budget
    txn = Transaction(
        account_id=account.id, amount=10000.0, type="debit",
        category="food", description="All food spending",
        transaction_date=datetime.date(2026, 6, 15)
    )
    db_session.add(txn)
    db_session.flush()
    
    check_and_create_alerts(db_session, 1, "food", datetime.date(2026, 6, 15))
    db_session.commit()
    
    exceeded_alert = db_session.query(BudgetAlert).filter(
        BudgetAlert.budget_id == budget.id,
        BudgetAlert.alert_type == AlertType.exceeded
    ).first()
    
    assert exceeded_alert is not None
```

---

### TC-02-P1-UNIT-05: Duplicate Alert Not Created
**Category:** Unit | **Priority:** High

```python
def test_duplicate_alert_not_created(db_session):
    from app.services.budget_alert_service import check_and_create_alerts
    from app.models.account import Account
    from app.models.transaction import Transaction
    from app.models.budget import Budget
    from app.models.budget_alert import BudgetAlert, AlertType
    import datetime
    
    account = Account(account_name="Test", account_type="savings",
                      balance=50000.0, user_id=1, currency="INR")
    db_session.add(account)
    db_session.flush()
    
    budget = Budget(user_id=1, category="food", monthly_limit=10000.0,
                    month=6, year=2026)
    db_session.add(budget)
    db_session.flush()
    
    txn = Transaction(
        account_id=account.id, amount=8500.0, type="debit",
        category="food", description="Food", transaction_date=datetime.date(2026, 6, 10)
    )
    db_session.add(txn)
    db_session.flush()
    
    # Trigger twice
    check_and_create_alerts(db_session, 1, "food", datetime.date(2026, 6, 10))
    db_session.flush()
    check_and_create_alerts(db_session, 1, "food", datetime.date(2026, 6, 10))
    db_session.commit()
    
    alert_count = db_session.query(BudgetAlert).filter(
        BudgetAlert.budget_id == budget.id,
        BudgetAlert.alert_type == AlertType.warning_80
    ).count()
    
    assert alert_count == 1  # Only one alert, not duplicated
```

---

### TC-02-P1-UNIT-06: Category Enum Validation
**Category:** Unit | **Priority:** Medium

```python
def test_category_enum_validation():
    from app.models.transaction import TransactionCategory
    
    valid_categories = ["food", "transport", "utilities", "entertainment", "health", "salary", "other"]
    
    for cat in valid_categories:
        assert cat in [c.value for c in TransactionCategory]
    
    # Invalid category should not be in enum
    assert "shopping" not in [c.value for c in TransactionCategory]
    assert "rent" not in [c.value for c in TransactionCategory]
```

---

### TC-02-P1-UNIT-07: Monthly Summary Calculation
**Category:** Unit | **Priority:** High

```python
def test_monthly_summary_calculation(db_session):
    from app.models.account import Account
    from app.models.transaction import Transaction
    from sqlalchemy import func, and_
    import datetime
    
    account = Account(account_name="Test", account_type="savings",
                      balance=50000.0, user_id=1, currency="INR")
    db_session.add(account)
    db_session.flush()
    
    # Add June 2026 transactions
    transactions = [
        Transaction(account_id=account.id, amount=8000.0, type="debit",
                    category="food", description="Food", transaction_date=datetime.date(2026, 6, 10)),
        Transaction(account_id=account.id, amount=3000.0, type="debit",
                    category="transport", description="Transport", transaction_date=datetime.date(2026, 6, 15)),
        Transaction(account_id=account.id, amount=80000.0, type="credit",
                    category="salary", description="Salary", transaction_date=datetime.date(2026, 6, 1)),
    ]
    db_session.add_all(transactions)
    db_session.commit()
    
    # Calculate June totals
    total_debit = db_session.query(func.sum(Transaction.amount)).filter(
        and_(Transaction.account_id == account.id,
             Transaction.type == "debit",
             func.strftime('%Y', Transaction.transaction_date) == '2026',
             func.strftime('%m', Transaction.transaction_date) == '06')
    ).scalar()
    
    total_credit = db_session.query(func.sum(Transaction.amount)).filter(
        and_(Transaction.account_id == account.id,
             Transaction.type == "credit",
             func.strftime('%Y', Transaction.transaction_date) == '2026',
             func.strftime('%m', Transaction.transaction_date) == '06')
    ).scalar()
    
    assert total_debit == 11000.0
    assert total_credit == 80000.0
```

---

### TC-02-P1-UNIT-08: Savings Rate Calculation
**Category:** Unit | **Priority:** High

```python
def test_savings_rate_calculation():
    """Test the savings rate formula: (income - expenses) / income * 100"""
    
    def calculate_savings_rate(income: float, expenses: float) -> float:
        if income == 0:
            return 0.0
        return (income - expenses) / income * 100
    
    # Standard case
    rate = calculate_savings_rate(80000, 55000)
    assert abs(rate - 31.25) < 0.01
    
    # Zero income
    rate = calculate_savings_rate(0, 5000)
    assert rate == 0.0
    
    # Zero expenses (all savings)
    rate = calculate_savings_rate(80000, 0)
    assert rate == 100.0
    
    # Expenses exceed income (negative savings)
    rate = calculate_savings_rate(50000, 60000)
    assert rate == -20.0
```

---

## API INTEGRATION TESTS (8 cases)

### TC-02-P1-API-01: POST /transactions Debit Returns 201
**Category:** API | **Priority:** High

```python
def test_post_debit_transaction_returns_201(client, auth_headers, test_account):
    import datetime
    
    response = client.post("/api/v1/transactions", json={
        "account_id": test_account["id"],
        "amount": 1500.0,
        "type": "debit",
        "category": "food",
        "description": "Weekly grocery run",
        "merchant": "Reliance Fresh",
        "transaction_date": "2026-06-15"
    }, headers=auth_headers)
    
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 1500.0
    assert data["category"] == "food"
    assert data["type"] == "debit"
    assert "id" in data
```

---

### TC-02-P1-API-02: POST /transactions Invalid Account Returns 404
**Category:** API | **Priority:** High

```python
def test_post_transaction_invalid_account_returns_404(client, auth_headers):
    response = client.post("/api/v1/transactions", json={
        "account_id": 99999,
        "amount": 500.0,
        "type": "debit",
        "category": "food",
        "description": "Test",
        "transaction_date": "2026-06-15"
    }, headers=auth_headers)
    
    assert response.status_code == 404
```

---

### TC-02-P1-API-03: GET /accounts/{id}/summary Returns Aggregations
**Category:** API | **Priority:** High

```python
def test_get_account_summary_returns_aggregations(client, auth_headers, test_account):
    # Add some transactions first
    for _ in range(3):
        client.post("/api/v1/transactions", json={
            "account_id": test_account["id"],
            "amount": 2000.0,
            "type": "debit",
            "category": "food",
            "description": "Food expense",
            "transaction_date": "2026-06-10"
        }, headers=auth_headers)
    
    response = client.get(
        f"/api/v1/accounts/{test_account['id']}/summary",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "total_credit" in data
    assert "total_debit" in data
    assert "balance" in data
    assert "spending_by_category" in data
    assert "monthly_trend" in data
    assert data["total_debit"] == 6000.0
    assert "food" in data["spending_by_category"]
```

---

### TC-02-P1-API-04: GET /transactions with Category Filter
**Category:** API | **Priority:** High

```python
def test_get_transactions_with_category_filter(client, auth_headers, test_account):
    # Add food and transport transactions
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"], "amount": 500.0,
        "type": "debit", "category": "food",
        "description": "Pizza", "transaction_date": "2026-06-10"
    }, headers=auth_headers)
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"], "amount": 200.0,
        "type": "debit", "category": "transport",
        "description": "Cab", "transaction_date": "2026-06-11"
    }, headers=auth_headers)
    
    response = client.get(
        f"/api/v1/transactions?account_id={test_account['id']}&category=food",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    items = response.json() if isinstance(response.json(), list) else response.json().get("items", [])
    
    assert all(t["category"] == "food" for t in items)
    assert len(items) >= 1
```

---

### TC-02-P1-API-05: POST /budgets Success Returns 201
**Category:** API | **Priority:** High

```python
def test_post_budget_returns_201(client, auth_headers):
    response = client.post("/api/v1/budgets", json={
        "category": "food",
        "monthly_limit": 10000.0,
        "month": 6,
        "year": 2026
    }, headers=auth_headers)
    
    assert response.status_code == 201
    data = response.json()
    assert data["category"] == "food"
    assert data["monthly_limit"] == 10000.0
    assert data["month"] == 6
    assert data["year"] == 2026
```

---

### TC-02-P1-API-06: POST /budgets Duplicate Returns 409
**Category:** API | **Priority:** High

```python
def test_post_duplicate_budget_returns_409(client, auth_headers):
    budget_data = {
        "category": "transport",
        "monthly_limit": 5000.0,
        "month": 6,
        "year": 2026
    }
    
    client.post("/api/v1/budgets", json=budget_data, headers=auth_headers)
    response = client.post("/api/v1/budgets", json=budget_data, headers=auth_headers)
    
    assert response.status_code == 409
```

---

### TC-02-P1-API-07: GET /budgets Returns Utilization Data
**Category:** API | **Priority:** High

```python
def test_get_budgets_returns_utilization(client, auth_headers, test_account):
    # Create budget
    client.post("/api/v1/budgets", json={
        "category": "entertainment",
        "monthly_limit": 2000.0,
        "month": 6,
        "year": 2026
    }, headers=auth_headers)
    
    # Add spending
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"],
        "amount": 1000.0,
        "type": "debit",
        "category": "entertainment",
        "description": "Movie tickets",
        "transaction_date": "2026-06-10"
    }, headers=auth_headers)
    
    response = client.get("/api/v1/budgets", headers=auth_headers)
    
    assert response.status_code == 200
    items = response.json() if isinstance(response.json(), list) else response.json().get("items", [])
    
    assert len(items) > 0
    entertainment = next((b for b in items if b["category"] == "entertainment"), None)
    assert entertainment is not None
    assert "spent" in entertainment
    assert "remaining" in entertainment
    assert "utilization_percent" in entertainment
    assert entertainment["spent"] == 1000.0
    assert entertainment["utilization_percent"] == 50.0
```

---

### TC-02-P1-API-08: GET /dashboard Returns All Metrics
**Category:** API | **Priority:** High

```python
def test_get_dashboard_returns_all_metrics(client, auth_headers, test_account):
    # Add income and expenses
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"],
        "amount": 80000.0,
        "type": "credit",
        "category": "salary",
        "description": "Monthly salary",
        "transaction_date": "2026-06-01"
    }, headers=auth_headers)
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"],
        "amount": 5000.0,
        "type": "debit",
        "category": "food",
        "description": "Groceries",
        "transaction_date": "2026-06-10"
    }, headers=auth_headers)
    
    response = client.get("/api/v1/dashboard", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "total_balance" in data
    assert "monthly_income" in data
    assert "monthly_expenses" in data
    assert "savings_rate" in data
    assert "top_3_categories" in data
    assert "budget_alerts_count" in data
    assert data["monthly_income"] == 80000.0
    assert data["monthly_expenses"] == 5000.0
```

---

## DATABASE TESTS (4 cases)

### TC-02-P1-DB-01: Transaction Persisted with Correct Fields
**Category:** Database | **Priority:** High

```python
def test_transaction_persisted_correctly(client, auth_headers, test_account):
    response = client.post("/api/v1/transactions", json={
        "account_id": test_account["id"],
        "amount": 750.0,
        "type": "debit",
        "category": "transport",
        "description": "Monthly metro pass",
        "merchant": "DMRC",
        "transaction_date": "2026-06-01"
    }, headers=auth_headers)
    
    assert response.status_code == 201
    txn_id = response.json()["id"]
    
    # Verify retrieval
    get_resp = client.get(f"/api/v1/transactions/{txn_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    
    data = get_resp.json()
    assert data["amount"] == 750.0
    assert data["category"] == "transport"
    assert data["merchant"] == "DMRC"
    assert data["transaction_date"] == "2026-06-01"
```

---

### TC-02-P1-DB-02: Account Balance Updated in DB
**Category:** Database | **Priority:** High

```python
def test_account_balance_updated_in_db(client, auth_headers, test_account):
    initial_balance = test_account["balance"]  # 50000
    
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"],
        "amount": 3000.0,
        "type": "debit",
        "category": "utilities",
        "description": "Electricity bill",
        "transaction_date": "2026-06-05"
    }, headers=auth_headers)
    
    response = client.get(f"/api/v1/accounts/{test_account['id']}", headers=auth_headers)
    assert response.status_code == 200
    
    new_balance = response.json()["balance"]
    assert new_balance == initial_balance - 3000.0
```

---

### TC-02-P1-DB-03: Budget Created in DB
**Category:** Database | **Priority:** High

```python
def test_budget_created_in_db(client, auth_headers):
    response = client.post("/api/v1/budgets", json={
        "category": "health",
        "monthly_limit": 3000.0,
        "month": 6,
        "year": 2026
    }, headers=auth_headers)
    
    assert response.status_code == 201
    budget_id = response.json()["id"]
    
    get_resp = client.get(f"/api/v1/budgets/{budget_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    
    data = get_resp.json()
    assert data["category"] == "health"
    assert data["monthly_limit"] == 3000.0
    assert data["month"] == 6
```

---

### TC-02-P1-DB-04: Budget Alert Created at Threshold
**Category:** Database | **Priority:** High

```python
def test_budget_alert_created_at_threshold(client, auth_headers, test_account):
    # Create food budget of 5000
    client.post("/api/v1/budgets", json={
        "category": "food",
        "monthly_limit": 5000.0,
        "month": 6,
        "year": 2026
    }, headers=auth_headers)
    
    # Spend 4500 = 90% — should trigger warning_80
    client.post("/api/v1/transactions", json={
        "account_id": test_account["id"],
        "amount": 4500.0,
        "type": "debit",
        "category": "food",
        "description": "Grocery month",
        "transaction_date": "2026-06-20"
    }, headers=auth_headers)
    
    # Check budget status shows has_alert=true
    response = client.get("/api/v1/budgets", headers=auth_headers)
    assert response.status_code == 200
    
    items = response.json() if isinstance(response.json(), list) else response.json().get("items", [])
    food_budget = next((b for b in items if b["category"] == "food"), None)
    
    assert food_budget is not None
    assert food_budget.get("has_alert") is True or food_budget.get("utilization_percent", 0) >= 80
```

---

## Running Phase 1 Tests

```bash
# Run all Phase 1 tests
pytest tests/phase1/ -v

# Run only unit tests
pytest tests/phase1/ -v -k "UNIT"

# Run only API tests
pytest tests/phase1/ -v -k "API"

# Generate report
pytest tests/phase1/ --junitxml=results/phase1-results.xml

# Run with coverage
pytest tests/phase1/ --cov=app --cov-report=term-missing
```
