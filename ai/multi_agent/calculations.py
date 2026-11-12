"""Deterministic financial calculations for the Phase 5 agents (Decimal arithmetic; no LLM involved).

Every figure in the final report comes from these functions applied to data fetched through the REST API.
The LLM may only add short narrative text, which is rejected if it contains numbers that are not in the facts.
"""
import calendar
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

CENT = Decimal("0.01")
NEEDS = ("food", "utilities", "health", "transport")      # simplified 50/30/20 mapping (documented assumption)
WANTS = ("entertainment", "other")
TARGETS = {"needs": 50, "wants": 30, "savings": 20}


def D(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0))
    except Exception:  # noqa: BLE001
        return Decimal(0)


def f2(value: Any) -> float:
    return float(D(value).quantize(CENT, rounding=ROUND_HALF_UP))


def inr(value: Any) -> str:
    return f"₹{D(value).quantize(CENT, rounding=ROUND_HALF_UP):,.2f}"


def pct(numerator: Any, denominator: Any) -> float:
    d = D(denominator)
    return f2(D(numerator) / d * 100) if d > 0 else 0.0


def title(s: str) -> str:
    return str(s).replace("_", " ").title()


def month_bounds(year: int, month: int) -> tuple[str, str]:
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


def previous_period(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def savings_rate(income: Any, expenses: Any) -> float:
    income = D(income)
    if income <= 0:
        return 0.0
    return f2((income - D(expenses)) / income * 100)


# ---------------------------------------------------------------- Transaction Analyzer
def analyze_transactions(transactions: list[dict], dashboard: dict, previous: dict | None = None) -> dict:
    """Spending patterns for one month. Totals come from the dashboard (authoritative income/expense rules); category and
    merchant detail come from the transactions, excluding transfers between the user's own accounts."""
    real = [t for t in transactions if not t.get("is_transfer")]
    debits = [t for t in real if t.get("type") == "debit"]
    credits = [t for t in real if t.get("type") == "credit"]

    by_category: dict[str, Decimal] = {}
    merchants: dict[str, Decimal] = {}
    for t in debits:
        by_category[t["category"]] = by_category.get(t["category"], Decimal(0)) + D(t["amount"])
        if t.get("merchant"):
            merchants[t["merchant"]] = merchants.get(t["merchant"], Decimal(0)) + D(t["amount"])
    by_category = dict(sorted(by_category.items(), key=lambda kv: kv[1], reverse=True))

    total_spent = D(dashboard["monthly_expenses"]) if dashboard else sum((D(t["amount"]) for t in debits), Decimal(0))
    total_income = D(dashboard["monthly_income"]) if dashboard else sum((D(t["amount"]) for t in credits), Decimal(0))

    largest = max(debits, key=lambda t: D(t["amount"]), default=None)
    top_merchant = max(merchants.items(), key=lambda kv: kv[1], default=None)

    unusual: list[str] = []
    if largest and total_spent > 0 and len(debits) > 1 and D(largest["amount"]) >= total_spent * Decimal("0.4"):
        unusual.append(f"One expense ({inr(largest['amount'])} on {largest['transaction_date']}: {largest['description']}) makes up {pct(largest['amount'], total_spent)}% of the month's spending.")
    seen: dict[tuple, int] = {}
    for t in debits:
        key = (t.get("merchant") or t["description"], str(D(t["amount"])), t["transaction_date"])
        seen[key] = seen.get(key, 0) + 1
    for (name, amount, day), count in seen.items():
        if count > 1:
            unusual.append(f"Possible duplicate: {count} identical expenses of {inr(amount)} at {name} on {day}.")

    prev_block = None
    if previous and previous.get("dashboard"):
        prev_spent, prev_income = D(previous["dashboard"]["monthly_expenses"]), D(previous["dashboard"]["monthly_income"])
        prev_cats = {c["category"]: D(c["amount"]) for c in previous.get("categories", [])}
        changes = []
        for cat, amount in by_category.items():
            before = prev_cats.get(cat, Decimal(0))
            changes.append({"category": cat, "current": f2(amount), "previous": f2(before), "change": f2(amount - before),
                            "change_percent": pct(amount - before, before) if before > 0 else None})
            if before > 0 and amount >= before * 2 and amount - before >= 1000:
                unusual.append(f"{title(cat)} spending more than doubled versus last month ({inr(before)} to {inr(amount)}).")
        prev_block = {
            "month": previous["month"], "year": previous["year"], "total_spent": f2(prev_spent), "total_income": f2(prev_income),
            "spent_change": f2(total_spent - prev_spent), "spent_change_percent": pct(total_spent - prev_spent, prev_spent) if prev_spent > 0 else None,
            "category_changes": changes,
        }

    return {
        "total_transactions": len(real),
        "transfer_legs_excluded": len(transactions) - len(real),
        "total_spent": f2(total_spent),
        "total_income": f2(total_income),
        "spending_by_category": {k: f2(v) for k, v in by_category.items()},
        "largest_expense": ({"description": largest["description"], "amount": f2(largest["amount"]), "category": largest["category"], "date": largest["transaction_date"]} if largest else None),
        "top_merchant": ({"merchant": top_merchant[0], "amount": f2(top_merchant[1])} if top_merchant else None),
        "unusual_patterns": unusual,
        "previous_period": prev_block,
    }


# ---------------------------------------------------------------- Budget Advisor
def _utilization(b: dict) -> Decimal:
    if b.get("utilization_percent") is not None:
        return D(b["utilization_percent"])
    return D(pct(b.get("spent", 0), b.get("monthly_limit", 0)))


def budget_item_score(util: Decimal) -> Decimal:
    """100 up to 80% used, falling linearly to 50 at 100%, then to 0 at 150% used."""
    if util <= 80:
        return Decimal(100)
    if util <= 100:
        return Decimal(100) - (util - 80) * Decimal("2.5")
    return max(Decimal(0), Decimal(50) - (util - 100))


def analyze_budgets(budget_data: list[dict], spending_analysis: dict) -> dict:
    over, warning, ok = [], [], []
    scores = []
    for b in budget_data:
        util = _utilization(b)
        limit, spent = D(b.get("monthly_limit", 0)), D(b.get("spent", 0))
        scores.append(budget_item_score(util))
        row = {"category": b["category"], "spent": f2(spent), "limit": f2(limit), "utilization_percent": f2(util)}
        if util >= 100:
            over.append({**row, "overage_amount": f2(spent - limit), "overage_percent": f2(util - 100)})
        elif util >= 80:
            warning.append({**row, "remaining": f2(limit - spent)})
        else:
            ok.append({**row, "remaining": f2(limit - spent)})
    budgeted = {b["category"] for b in budget_data}
    no_budget = [{"category": c, "spent": a} for c, a in spending_analysis.get("spending_by_category", {}).items() if c not in budgeted and D(a) > 0]
    total_limit = sum((D(b.get("monthly_limit", 0)) for b in budget_data), Decimal(0))
    total_spent = sum((D(b.get("spent", 0)) for b in budget_data), Decimal(0))
    score = int((sum(scores, Decimal(0)) / len(scores)).quantize(Decimal(1), rounding=ROUND_HALF_UP)) if scores else 50
    return {
        "over_budget_categories": over,
        "warning_categories": warning,
        "under_budget_categories": [o for o in ok if D(o["remaining"]) > D(o["limit"]) * Decimal("0.2")],
        "no_budget_categories": no_budget,
        "total_budget_utilization": pct(total_spent, total_limit),
        "budget_health_score": max(0, min(100, score)),
        "has_budgets": bool(budget_data),
    }


def budget_recommendations(analysis: dict) -> list[str]:
    recs = []
    for o in analysis.get("over_budget_categories", []):
        if "overage_amount" in o:
            recs.append(f"{title(o['category'])} is over budget by {inr(o['overage_amount'])} ({o.get('overage_percent', 0)}% above the {inr(o['limit'])} limit). Cut the remaining {title(o['category']).lower()} spending, or raise the limit to {inr(D(o['limit']) + D(o['overage_amount']))} if this level is unavoidable.")
    for w in analysis.get("warning_categories", []):
        recs.append(f"{title(w['category'])} has used {w['utilization_percent']}% of its budget; only {inr(w['remaining'])} is left for the rest of the month.")
    for n in analysis.get("no_budget_categories", [])[:2]:
        recs.append(f"Set a monthly budget for {title(n['category'])}: you spent {inr(n['spent'])} there with no limit in place.")
    if not analysis.get("has_budgets"):
        recs.append("No budgets are set for this month. Start with budgets for your top two spending categories.")
    return recs[:6]


# ---------------------------------------------------------------- Savings Optimizer
def savings_metrics(spending: dict, dashboard: dict | None = None) -> dict:
    dashboard = dashboard or {}
    income = D(spending.get("total_income", dashboard.get("monthly_income", 0)))
    expenses = D(spending.get("total_spent", dashboard.get("monthly_expenses", 0)))
    cats = {c: D(a) for c, a in spending.get("spending_by_category", {}).items()}
    needs = sum((cats.get(c, Decimal(0)) for c in NEEDS), Decimal(0))
    wants = sum((cats.get(c, Decimal(0)) for c in WANTS), Decimal(0))
    saved = income - expenses
    return {
        "income": f2(income), "expenses": f2(expenses), "saved": f2(saved), "savings_rate": savings_rate(income, expenses),
        "needs": f2(needs), "wants": f2(wants), "needs_percent": pct(needs, income), "wants_percent": pct(wants, income),
        "savings_percent": pct(saved, income) if income > 0 else 0.0,
        "total_assets": f2(dashboard["total_assets"]) if dashboard.get("total_assets") is not None else None,
        "emergency_months": (float((D(dashboard["total_assets"]) / expenses).quantize(Decimal("0.1"))) if dashboard.get("total_assets") is not None and expenses > 0 else None),
    }


def rate_label(rate: float) -> str:
    return "excellent" if rate > 30 else "good" if rate >= 20 else "moderate" if rate >= 10 else "low"


def build_recommendations(spending: dict, budget: dict, dashboard: dict | None = None) -> list[str]:
    m = savings_metrics(spending, dashboard)
    recs: list[str] = []
    income, expenses, rate = D(m["income"]), D(m["expenses"]), m["savings_rate"]
    if income <= 0:
        return ["No income was recorded for this month, so a savings rate cannot be calculated. Record your salary and other income to get savings advice."]
    recs.append(f"Your savings rate is {rate}% ({inr(m['saved'])} saved from {inr(income)} of income), which is {rate_label(rate)}. The 50/30/20 rule targets 20% or more.")
    if rate < 20:
        gap = income * Decimal("0.2") - D(m["saved"])
        recs.append(f"Stretch goal: save an extra {inr(gap)} per month to reach a 20% savings rate.")
    if m["wants_percent"] > TARGETS["wants"]:
        excess = D(m["wants"]) - income * Decimal("0.3")
        recs.append(f"Discretionary spending (entertainment and other) is {m['wants_percent']}% of income against a 30% guideline. Reducing it by {inr(excess)} would bring it in line.")
    cats = spending.get("spending_by_category", {})
    top_wants = max(((c, D(cats[c])) for c in WANTS if c in cats), key=lambda kv: kv[1], default=None)
    if top_wants and top_wants[1] > 0:
        cut = (top_wants[1] * Decimal("0.15")).quantize(CENT)
        recs.append(f"Trimming {title(top_wants[0])} spending by 15% would save about {inr(cut)} per month ({inr(cut * 12)} per year).")
    for o in budget.get("over_budget_categories", [])[:2]:
        if "overage_amount" in o:
            recs.append(f"Bring {title(o['category'])} back within its budget: that alone recovers {inr(o['overage_amount'])}.")
    if m["needs_percent"] > TARGETS["needs"]:
        recs.append(f"Essential spending (food, utilities, health, transport) is {m['needs_percent']}% of income against a 50% guideline; review recurring bills for savings.")
    if m["emergency_months"] is not None:
        lo, hi = expenses * 3, expenses * 6
        if m["emergency_months"] < 3:
            recs.append(f"Your savings and checking balances cover about {m['emergency_months']} months of expenses. Build towards an emergency fund of 3 to 6 months ({inr(lo)} to {inr(hi)}).")
        else:
            recs.append(f"Your savings and checking balances cover about {m['emergency_months']} months of expenses, within or above the 3 to 6 month emergency-fund guideline.")
    return recs[:8]


# ---------------------------------------------------------------- Report Generator
def health_score(budget_score: int, rate: float) -> int:
    """50% budget health + 50% savings rate measured against a 30% target (capped 0-100)."""
    rate_part = max(0.0, min(100.0, rate / 30 * 100))
    return int(round(0.5 * budget_score + 0.5 * rate_part))


def rating(score: int) -> str:
    return "Excellent" if score >= 80 else "Good" if score >= 60 else "Fair" if score >= 40 else "Needs attention"


def financial_risks(spending: dict, budget: dict, metrics: dict) -> list[str]:
    risks = []
    if D(metrics["income"]) > 0 and D(metrics["saved"]) < 0:
        risks.append(f"Negative cash flow: expenses exceeded income by {inr(-D(metrics['saved']))}.")
    elif D(metrics["income"]) > 0 and metrics["savings_rate"] < 10:
        risks.append(f"Low savings rate ({metrics['savings_rate']}%): little buffer against unexpected costs.")
    for o in budget.get("over_budget_categories", []):
        if "overage_amount" in o:
            risks.append(f"{title(o['category'])} is over budget by {inr(o['overage_amount'])}.")
    if metrics.get("emergency_months") is not None and metrics["emergency_months"] < 3:
        risks.append(f"Emergency cushion of about {metrics['emergency_months']} months is below the 3-month minimum.")
    prev = spending.get("previous_period")
    if prev and prev.get("spent_change_percent") is not None and prev["spent_change_percent"] > 20:
        risks.append(f"Spending rose {prev['spent_change_percent']}% compared with last month.")
    risks.extend(spending.get("unusual_patterns", [])[:3])
    if not budget.get("has_budgets", True):
        risks.append("No budgets are set, so overspending would not trigger alerts.")
    return risks


def action_items(budget_recs: list[str], savings_recs: list[str], limit: int = 5) -> list[str]:
    items = []
    for r in list(budget_recs[:2]) + list(savings_recs[1:]):
        if r not in items:
            items.append(r)
    return items[:limit] or ["Keep recording income and expenses so next month's report is more accurate."]


# ---------------------------------------------------------------- numeric guard for LLM narrative
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def collect_numbers(obj: Any, out: set | None = None) -> set:
    out = set() if out is None else out
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float, Decimal)):
        out.add(float(obj))
    elif isinstance(obj, str):
        for tok in _NUM.findall(obj):
            try:
                out.add(float(tok.replace(",", "").rstrip(".")))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_numbers(v, out)
    elif isinstance(obj, Iterable):
        for v in obj:
            collect_numbers(v, out)
    return out


def narrative_is_grounded(text: str, facts: Any) -> tuple[bool, list[str]]:
    """True when every significant number in `text` (3+ digits or with decimals) appears in `facts` (allowing rounding)."""
    allowed = collect_numbers(facts)
    bad = []
    for tok in _NUM.findall(text):
        digits = tok.replace(",", "")
        try:
            v = float(digits.rstrip("."))
        except ValueError:
            continue
        significant = "." in digits.rstrip(".") or len(digits.split(".")[0]) >= 3
        if not significant or 2000 <= v <= 2100:
            continue
        if not any(abs(v - a) < 0.005 or round(a) == v or round(a, 1) == v for a in allowed):
            bad.append(tok)
    return (not bad), bad
