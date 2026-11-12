"""Demo data seeder (explicit demo scenario only). Talks to the running REST API, so all business rules apply.

Usage:  python scripts/seed_demo.py [--base-url http://127.0.0.1:8000/api/v1]
Creates demo@finance.com / DemoPass123 with 3 accounts, ~6 months of transactions, budgets (one near 80%, one exceeded),
a credit-card purchase and a repayment transfer.
"""
import argparse
import datetime
import sys

import httpx

EMAIL, PASSWORD = "demo@finance.com", "DemoPass123"


def month_start(today: datetime.date, back: int) -> datetime.date:
    idx = today.year * 12 + today.month - 1 - back
    return datetime.date(idx // 12, idx % 12 + 1, 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    base = p.parse_args().base_url
    c = httpx.Client(base_url=base, timeout=15)
    today = datetime.date.today()

    r = c.post("/auth/register", json={"name": "Arjun Kapoor", "email": EMAIL, "password": PASSWORD, "monthly_income": 80000})
    if r.status_code == 409:
        print("Demo user already exists; logging in (no data re-created).")
        return
    r.raise_for_status()
    tok = c.post("/auth/login", data={"username": EMAIL, "password": PASSWORD}).json()["access_token"]
    c.headers["Authorization"] = f"Bearer {tok}"

    def post(path, body):
        resp = c.post(path, json=body)
        if resp.status_code >= 300:
            sys.exit(f"{path} failed: {resp.status_code} {resp.text}")
        return resp.json()

    sav = post("/accounts", {"account_name": "HDFC Savings", "account_type": "savings", "balance": 150000})
    chk = post("/accounts", {"account_name": "SBI Salary Account", "account_type": "checking", "balance": 60000})
    card = post("/accounts", {"account_name": "ICICI Credit Card", "account_type": "credit", "balance": 0})

    plan = [("food", 7000), ("transport", 2500), ("utilities", 3200), ("entertainment", 1800), ("health", 1200)]
    for back in range(5, -1, -1):
        d0 = month_start(today, back)
        post("/transactions", {"account_id": sav["id"], "amount": 80000, "type": "credit", "category": "salary",
                               "description": "Monthly salary", "merchant": "Acme Technologies", "transaction_date": d0.isoformat()})
        for i, (cat, amt) in enumerate(plan):
            day = min(3 + i * 5, 27)
            if d0.replace(day=day) > today:
                continue
            post("/transactions", {"account_id": chk["id"] if cat in ("utilities", "transport") else sav["id"], "amount": amt + back * 150,
                                   "type": "debit", "category": cat, "description": f"{cat.title()} spend",
                                   "merchant": {"food": "BigBazaar", "transport": "Ola", "utilities": "BSES", "entertainment": "BookMyShow", "health": "Apollo"}[cat],
                                   "transaction_date": d0.replace(day=day).isoformat()})
    post("/transfers", {"source_account_id": sav["id"], "destination_account_id": chk["id"], "amount": 10000, "transfer_date": month_start(today, 0).isoformat(), "description": "Top up salary account"})

    y, m = today.year, today.month
    post("/budgets", {"category": "food", "monthly_limit": 10000, "month": m, "year": y})
    post("/budgets", {"category": "entertainment", "monthly_limit": 2000, "month": m, "year": y})
    post("/budgets", {"category": "transport", "monthly_limit": 6000, "month": m, "year": y})
    cur = month_start(today, 0)
    # push food to ~90% and entertainment to 100% (alerts fire on debit recording)
    post("/transactions", {"account_id": sav["id"], "amount": 2200, "type": "debit", "category": "food", "description": "Weekend groceries", "merchant": "Reliance Fresh", "transaction_date": cur.isoformat()})
    post("/transactions", {"account_id": sav["id"], "amount": 600, "type": "debit", "category": "entertainment", "description": "OTT annual plan", "merchant": "Netflix", "transaction_date": cur.isoformat()})
    post("/transactions", {"account_id": card["id"], "amount": 6500, "type": "debit", "category": "food", "description": "Dinner and groceries on card", "merchant": "Swiggy", "transaction_date": cur.isoformat()})
    post("/transfers", {"source_account_id": sav["id"], "destination_account_id": card["id"], "amount": 3000, "transfer_date": cur.isoformat(), "description": "Credit card repayment"})
    print(f"Seeded demo data for {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    main()
