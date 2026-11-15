"""Phase 5 — MOCK tier: LangGraph pipeline over the REAL FastAPI app (in-process). LLM is absent or scripted.
Numbers are deterministic (calculations.py); the live-Gemini narrative tier is in test_multi_agent_live.py.
"""
import copy
import json
from decimal import Decimal

import httpx
import pytest
from testsupport.fakes import ScriptedChatModel

from multi_agent import agents as agents_mod
from multi_agent import calculations as calc
from multi_agent import graph as graph_mod
from multi_agent.agents import ReportContext, budget_advisor, report_generator, savings_optimizer, transaction_analyzer
from multi_agent.graph import build_financial_report_graph, generate_financial_report, should_continue_after_analysis
from multi_agent.state import FinancialHealthState, initial_state

pytestmark = pytest.mark.mock

M, Y = 10, 2026   # report month used by seeded data (explicit dates: independent of today's date)
BASE = "http://testserver/api/v1"


def scripted(*items):
    return ScriptedChatModel(script=list(items), calls=[])


def seed_month(api, income=80000, food=8500, entertainment=2400, transport=3000, rent_card=0):
    """Savings (₹100k), a credit card and budgets; October transactions plus a lighter September for comparison."""
    sav = api.post("/accounts", {"account_name": "HDFC Savings", "account_type": "savings", "balance": 100000})
    card = api.post("/accounts", {"account_name": "ICICI Card", "account_type": "credit", "balance": 0})
    for cat, limit in (("food", 10000), ("entertainment", 2000), ("transport", 5000)):
        api.post("/budgets", {"category": cat, "monthly_limit": limit, "month": M, "year": Y})

    def t(acct, amount, typ, cat, desc, day, merchant=None, month=M):
        body = {"account_id": acct["id"], "amount": amount, "type": typ, "category": cat, "description": desc, "transaction_date": f"{Y}-{month:02d}-{day:02d}"}
        if merchant:
            body["merchant"] = merchant
        return api.post("/transactions", body)

    t(sav, income, "credit", "salary", "Salary", 1)
    t(sav, food, "debit", "food", "Groceries", 5, "BigBazaar")
    t(sav, entertainment, "debit", "entertainment", "Concert", 9, "BookMyShow")
    t(sav, transport, "debit", "transport", "Cab rides", 12, "Ola")
    if rent_card:
        t(card, rent_card, "debit", "other", "Card purchase", 15, "Amazon")
        api.post("/transfers", {"source_account_id": sav["id"], "destination_account_id": card["id"], "amount": rent_card, "transfer_date": f"{Y}-{M:02d}-20", "description": "Card repayment"})
    t(sav, 70000, "credit", "salary", "Salary", 1, month=9)
    t(sav, 4000, "debit", "food", "Groceries", 6, month=9)
    t(sav, 500, "debit", "entertainment", "Movie", 8, month=9)
    return sav, card


def ctx_for(api, **kw):
    return ReportContext(base_url=BASE, token=api.token, **kw)


def run_node(node, state, ctx):
    return node(state, {"configurable": {"report_ctx": ctx}})


# ======================================================================== state (TC-02-P5-STATE-*)
def test_state_01_has_all_required_fields():
    for f in ["user_id", "report_month", "report_year", "transactions", "budget_data", "dashboard_data", "spending_analysis",
              "budget_analysis", "savings_recommendations", "final_report", "report_status", "errors", "messages"]:
        assert f in FinancialHealthState.__annotations__


def test_state_02_initial_state():
    s = initial_state(1, 6, 2026)
    assert (s["user_id"], s["report_month"], s["report_year"]) == (1, 6, 2026)
    assert s["transactions"] == s["budget_data"] == s["savings_recommendations"] == s["errors"] == s["messages"] == []
    assert s["dashboard_data"] == s["spending_analysis"] == s["budget_analysis"] == {} and s["final_report"] == "" and s["report_status"] == "in_progress"


def test_state_03_04_update_pattern_does_not_mutate_and_persists():
    a = initial_state(1, 6, 2026)
    b = {**a, "messages": list(a["messages"]) + ["Transaction Analyzer: Done"], "transactions": [{"id": 1}]}
    assert a["messages"] == [] and a["transactions"] == [] and len(b["messages"]) == 1
    c = {**b, "budget_analysis": {"budget_health_score": 85}, "messages": b["messages"] + ["Budget Advisor: x"]}
    assert c["transactions"] == [{"id": 1}] and [m.split(":")[0] for m in c["messages"]] == ["Transaction Analyzer", "Budget Advisor"]


def test_nodes_never_mutate_their_input_state(finance_api):
    seed_month(finance_api)
    state = initial_state(finance_api.client.get("/api/v1/users/me", headers=finance_api.headers).json()["id"], M, Y)
    for node in (transaction_analyzer, budget_advisor, savings_optimizer, report_generator):
        before = copy.deepcopy(state)
        state = run_node(node, state, ctx_for(finance_api, use_llm=False))
        assert state is not before
    original = initial_state(1, M, Y)
    snapshot = copy.deepcopy(original)
    run_node(budget_advisor, original, ReportContext(use_llm=False))
    assert original == snapshot


# ======================================================================== calculations (pure)
def test_savings_rate_and_period_helpers():
    assert calc.savings_rate(80000, 55000) == 31.25 and calc.savings_rate(0, 100) == 0.0 and calc.savings_rate(50000, 60000) == -20.0
    assert calc.previous_period(2026, 1) == (2025, 12) and calc.previous_period(2026, 7) == (2026, 6)
    assert calc.month_bounds(2024, 2) == ("2024-02-01", "2024-02-29") and calc.month_bounds(2026, 4) == ("2026-04-01", "2026-04-30")


def test_money_helpers_are_decimal_safe():
    assert calc.f2(Decimal("0.1") + Decimal("0.2")) == 0.3 and calc.inr(1234567.5) == "₹1,234,567.50" and calc.pct(1, 3) == 33.33


@pytest.mark.parametrize("util,score", [(0, 100), (80, 100), (90, 75), (100, 50), (120, 30), (150, 0), (300, 0)])
def test_budget_item_score_curve(util, score):
    assert calc.budget_item_score(Decimal(util)) == score


def test_analyze_budgets_over_warning_ok_and_score():
    budgets = [{"category": "food", "monthly_limit": 10000.0, "spent": 12000.0, "utilization_percent": 120.0},
               {"category": "health", "monthly_limit": 5000.0, "spent": 4200.0, "utilization_percent": 84.0},
               {"category": "transport", "monthly_limit": 5000.0, "spent": 1000.0, "utilization_percent": 20.0}]
    a = calc.analyze_budgets(budgets, {"spending_by_category": {"food": 12000, "other": 700}})
    assert a["over_budget_categories"][0] == {"category": "food", "spent": 12000.0, "limit": 10000.0, "utilization_percent": 120.0, "overage_amount": 2000.0, "overage_percent": 20.0}
    assert [w["category"] for w in a["warning_categories"]] == ["health"] and [u["category"] for u in a["under_budget_categories"]] == ["transport"]
    assert a["no_budget_categories"] == [{"category": "other", "spent": 700}] and a["budget_health_score"] == 73 and a["total_budget_utilization"] == 86.0  # scores 30, 90, 100
    assert calc.analyze_budgets([], {})["budget_health_score"] == 50 and calc.analyze_budgets([], {})["has_budgets"] is False


def test_savings_metrics_and_recommendations_use_real_numbers():
    spending = {"total_income": 80000.0, "total_spent": 60000.0, "spending_by_category": {"food": 20000.0, "entertainment": 15000.0, "utilities": 5000.0}}
    m = calc.savings_metrics(spending, {"total_assets": 120000.0})
    assert (m["savings_rate"], m["saved"], m["wants_percent"], m["needs_percent"], m["emergency_months"]) == (25.0, 20000.0, 18.75, 31.25, 2.0)
    recs = calc.build_recommendations(spending, {"over_budget_categories": [{"category": "food", "overage_amount": 2000.0, "overage_percent": 20.0, "limit": 10000.0}]}, {"total_assets": 120000.0})
    text = " ".join(recs)
    assert "25.0% (₹20,000.00 saved from ₹80,000.00" in text and "good" in text and "₹2,250.00" in text and "₹27,000.00" in text.replace("27,000.00", "27,000.00")
    assert "emergency fund" in text and "₹180,000.00 to ₹360,000.00" in text
    assert calc.build_recommendations({"total_income": 0, "total_spent": 100}, {}) and "No income" in calc.build_recommendations({"total_income": 0, "total_spent": 100}, {})[0]
    low = calc.build_recommendations({"total_income": 80000, "total_spent": 79000, "spending_by_category": {}}, {})
    assert any("Stretch goal" in r and "₹15,000.00" in r for r in low)


def test_health_score_bounds_and_rating():
    assert calc.health_score(100, 30) == 100 and calc.health_score(100, 60) == 100 and calc.health_score(0, -50) == 0 and calc.health_score(50, 15) == 50
    assert [calc.rating(s) for s in (90, 65, 45, 10)] == ["Excellent", "Good", "Fair", "Needs attention"]


def test_health_breakdown_exposes_every_component():
    # Regression: a report showed "75/100" with only "budget 50, savings rate 78.5%" visible. The savings component is capped
    # at 100 (78.5% vs a 30% target), which was not shown; the breakdown now states every input of the formula.
    b = calc.health_breakdown(50, 78.5, has_budgets=True)
    assert (b["score"], b["budget_component"], b["savings_component"]) == (75, 50, 100)
    assert b["formula"] == "50% x budget health 50 + 50% x savings component 100 = 75" and "78.5% / 30% target, capped at 100" in b["savings_note"]
    none = calc.health_breakdown(50, 78.5, has_budgets=False)  # no budgets: no neutral "50" is invented
    assert (none["score"], none["budget_component"]) == (100, None) and "no budgets set" in none["formula"]
    assert calc.health_breakdown(80, 15)["savings_component"] == 50 and calc.health_breakdown(80, 15)["score"] == 65


@pytest.mark.parametrize("has_budgets", [True, False])
@pytest.mark.parametrize("budget_score,rate", [(100, 31.25), (50, 78.5), (73, 12.0), (0, -20.0), (90, 0.0), (65, 29.99)])
def test_report_score_always_matches_its_displayed_formula(budget_score, rate, has_budgets):
    import re

    income, spent = 100000.0, round(100000.0 * (1 - rate / 100), 2)
    state = {**initial_state(1, 6, 2026), "spending_analysis": {"total_spent": spent, "total_income": income, "spending_by_category": {}},
             "budget_analysis": {"budget_health_score": budget_score, "has_budgets": has_budgets, "over_budget_categories": [], "recommendations": []},
             "savings_recommendations": []}
    section = report_generator(state, {"configurable": {"report_ctx": ReportContext(use_llm=False)}})["final_report"].split("## 8. Financial Health Score")[1]
    shown = int(re.search(r"\*\*(\d+)/100", section).group(1))
    expected_savings = round(max(0.0, min(100.0, calc.savings_rate(income, spent) / 30 * 100)))
    if has_budgets:
        m = re.search(r"50% x budget health (\d+) \+ 50% x savings component (\d+) = (\d+)", section)
        assert (int(m.group(1)), int(m.group(2))) == (budget_score, expected_savings)
        assert int(m.group(3)) == shown == round(0.5 * budget_score + 0.5 * expected_savings)
    else:
        assert int(re.search(r"alone counts = (\d+)", section).group(1)) == shown == expected_savings
        assert "50% x budget health" not in section


def test_analyze_transactions_excludes_transfers_and_flags_patterns():
    tx = [{"id": 1, "type": "debit", "category": "food", "amount": 9000.0, "description": "Party", "merchant": "Zomato", "transaction_date": "2026-10-03", "is_transfer": False},
          {"id": 2, "type": "debit", "category": "food", "amount": 500.0, "description": "Lunch", "merchant": "Zomato", "transaction_date": "2026-10-04", "is_transfer": False},
          {"id": 3, "type": "debit", "category": "food", "amount": 500.0, "description": "Lunch", "merchant": "Zomato", "transaction_date": "2026-10-04", "is_transfer": False},
          {"id": 4, "type": "debit", "category": "other", "amount": 50000.0, "description": "Card payment", "merchant": None, "transaction_date": "2026-10-05", "is_transfer": True}]
    prev = {"month": 9, "year": 2026, "dashboard": {"monthly_expenses": 5000.0, "monthly_income": 80000.0}, "categories": [{"category": "food", "amount": 4000.0}]}
    a = calc.analyze_transactions(tx, {"monthly_expenses": 10000.0, "monthly_income": 80000.0}, prev)
    assert a["total_spent"] == 10000.0 and a["spending_by_category"] == {"food": 10000.0} and a["transfer_legs_excluded"] == 1 and a["total_transactions"] == 3
    assert a["largest_expense"]["amount"] == 9000.0 and a["top_merchant"] == {"merchant": "Zomato", "amount": 10000.0}
    kinds = " ".join(a["unusual_patterns"])
    assert "90.0% of the month" in kinds and "Possible duplicate: 2 identical expenses of ₹500.00 at Zomato" in kinds and "more than doubled" in kinds
    assert a["previous_period"]["spent_change_percent"] == 100.0 and a["previous_period"]["category_changes"][0]["change"] == 6000.0


def test_numeric_guard_accepts_grounded_and_rejects_invented_numbers():
    facts = {"income": 80000.0, "expenses": 55000.0, "savings_rate": 31.25, "recs": ["Save ₹2,250.00 per month"]}
    assert calc.narrative_is_grounded("You earned ₹80,000 and spent ₹55,000.00, a savings rate of 31.25% (about 31%).", facts)[0]
    assert calc.narrative_is_grounded("Savings of ₹2,250 are possible in 2026, across 3 areas.", facts)[0]
    ok, bad = calc.narrative_is_grounded("You could save ₹9,999 by cutting food and reach 45.5%.", facts)
    assert not ok and bad == ["9,999", "45.5"]


# ======================================================================== agents with the real API (TC-02-P5-AGENT-*)
def test_agent_01_transaction_analyzer_fetches_and_analyzes(finance_api):
    seed_month(finance_api, rent_card=6000)
    me = finance_api.client.get("/api/v1/users/me", headers=finance_api.headers).json()
    out = run_node(transaction_analyzer, initial_state(me["id"], M, Y), ctx_for(finance_api, use_llm=False))
    a = out["spending_analysis"]
    assert "Transaction Analyzer" in out["messages"][0] and "Processed 7 transactions" in out["messages"][0]  # salary, 3 expenses, card purchase, 2 transfer legs
    assert a["total_income"] == 80000.0 and a["total_spent"] == 19900.0 and a["total_transactions"] == 5 and a["transfer_legs_excluded"] == 2
    assert a["spending_by_category"] == {"food": 8500.0, "transport": 3000.0, "entertainment": 2400.0, "other": 6000.0}
    assert a["previous_period"]["total_spent"] == 4500.0 and a["previous_period"]["spent_change"] == 15400.0
    assert len(out["budget_data"]) == 3 and out["dashboard_data"]["monthly_expenses"] == 19900.0 and out["errors"] == []
    assert any("Entertainment spending more than doubled" in u for u in a["unusual_patterns"])


def test_analyzer_fetches_every_page_of_transactions(finance_api):
    acct = finance_api.post("/accounts", {"account_name": "Big", "account_type": "savings", "balance": 100000})
    for i in range(125):
        finance_api.post("/transactions", {"account_id": acct["id"], "amount": 1, "type": "debit", "category": "other", "description": f"t{i}", "transaction_date": f"{Y}-{M:02d}-{(i % 28) + 1:02d}"})
    me = finance_api.client.get("/api/v1/users/me", headers=finance_api.headers).json()
    out = run_node(transaction_analyzer, initial_state(me["id"], M, Y), ctx_for(finance_api, use_llm=False))
    assert len(out["transactions"]) == 125 and out["spending_analysis"]["total_spent"] == 125.0  # reference code stopped at 20


def test_agent_02_analyzer_handles_api_unavailable_without_raising(monkeypatch):
    monkeypatch.setattr(httpx, "request", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    out = transaction_analyzer(initial_state(1, 6, 2026), {"configurable": {"report_ctx": ReportContext(base_url="http://localhost:9999/api/v1", token="x", use_llm=False)}})
    assert isinstance(out, dict) and "spending_analysis" in out and out["spending_analysis"]["total_spent"] == 0.0
    assert any("unavailable" in e.lower() for e in out["errors"]) and "Transaction Analyzer" in out["messages"][0]
    assert transaction_analyzer(initial_state(1, 6, 2026))["errors"]  # direct 1-arg call (spec style) also safe


def test_analyzer_refuses_to_report_on_another_users_id(finance_api, second_api):
    seed_month(finance_api)
    other_id = finance_api.client.get("/api/v1/users/me", headers=finance_api.headers).json()["id"]
    out = run_node(transaction_analyzer, initial_state(other_id, M, Y), ReportContext(base_url=BASE, token=second_api.token, use_llm=False))
    assert out["report_status"] == "error" and out["transactions"] == [] and out["budget_data"] == [] and "does not match" in out["errors"][0]


def test_agent_03_04_budget_advisor_over_budget_and_score_range():
    state = {**initial_state(1, 6, 2026), "spending_analysis": {"total_spent": 15000.0, "total_income": 80000.0, "spending_by_category": {"food": 12000.0, "transport": 3000.0}},
             "budget_data": [{"category": "food", "monthly_limit": 10000.0, "spent": 12000.0, "utilization_percent": 120.0},
                             {"category": "transport", "monthly_limit": 5000.0, "spent": 3000.0, "utilization_percent": 60.0}]}
    out = budget_advisor(state)
    a = out["budget_analysis"]
    assert a["over_budget_categories"][0]["category"] == "food" and a["over_budget_categories"][0]["overage_amount"] == 2000.0 and 0 <= a["budget_health_score"] <= 100
    assert any("Food is over budget by ₹2,000.00" in r for r in a["recommendations"]) and "Budget Advisor" in out["messages"][-1]
    ok = budget_advisor({**initial_state(1, 6, 2026), "budget_data": [{"category": "food", "monthly_limit": 10000.0, "spent": 5000.0, "utilization_percent": 50.0}]})
    assert ok["budget_analysis"]["budget_health_score"] == 100


def test_agent_05_06_savings_optimizer_recommendations_and_rate():
    state = {**initial_state(1, 6, 2026),
             "spending_analysis": {"total_spent": 60000.0, "total_income": 80000.0, "spending_by_category": {"food": 20000.0, "entertainment": 15000.0}},
             "budget_analysis": {"budget_health_score": 60, "over_budget_categories": [{"category": "food", "overage_percent": 20.0}]},
             "dashboard_data": {"monthly_income": 80000.0, "monthly_expenses": 60000.0}}
    out = savings_optimizer(state)
    assert isinstance(out["savings_recommendations"], list) and len(out["savings_recommendations"]) >= 1
    rate = savings_optimizer({**initial_state(1, 6, 2026), "spending_analysis": {"total_income": 80000.0, "total_spent": 55000.0}, "budget_analysis": {"budget_health_score": 75}, "dashboard_data": {}})
    assert any("31" in m for m in rate["messages"]) and "Current savings rate: 31.2%" in rate["messages"][-1]


def test_agent_07_08_report_generator_markdown_sections_and_score():
    state = {**initial_state(1, 6, 2026),
             "spending_analysis": {"total_spent": 55000.0, "total_income": 80000.0, "spending_by_category": {"food": 15000.0}},
             "budget_analysis": {"budget_health_score": 70, "over_budget_categories": [], "recommendations": ["Reduce food spending"], "has_budgets": True},
             "savings_recommendations": ["Cut entertainment by ₹2000/month", "Set up automatic savings transfer"]}
    out = report_generator({**state}, {"configurable": {"report_ctx": ReportContext(use_llm=False)}})
    r = out["final_report"]
    assert len(r) > 100 and r.startswith("# Financial Health Report — June 2026") and out["report_status"] == "complete"
    for header in ("1. Executive Summary", "2. Income & Expense Overview", "3. Spending Analysis", "4. Budget Performance", "5. Savings Optimizer Recommendations",
                   "6. Financial Risks", "7. Action Items for Next Month", "8. Financial Health Score"):
        assert f"## {header}" in r, header
    assert "**85/100 — Excellent.**" in r and "Cut entertainment by ₹2000/month" in r and "₹55,000.00" in r and "31.25%" in r
    assert "score" in r.lower() and "health" in r.lower()


def test_report_for_failed_data_is_an_honest_error_report():
    state = {**initial_state(1, 6, 2026), "errors": ["Could not verify the user: unavailable"], "spending_analysis": {"total_transactions": 0, "total_spent": 0.0, "total_income": 0.0}}
    out = report_generator(state, {"configurable": {"report_ctx": ReportContext(use_llm=False)}})
    assert out["report_status"] == "error" and "### Data notes" in out["final_report"] and "Could not verify the user" in out["final_report"]


# ---------------------------------------------------------------- LLM narrative: grounded or discarded
def test_grounded_narrative_is_included_and_ungrounded_is_discarded(finance_api):
    seed_month(finance_api)
    me = finance_api.client.get("/api/v1/users/me", headers=finance_api.headers).json()
    good = scripted("Spending was led by food at ₹8,500.00 this month.")
    out = run_node(transaction_analyzer, initial_state(me["id"], M, Y), ctx_for(finance_api, llm=good))
    assert out["spending_analysis"]["narrative"] == "Spending was led by food at ₹8,500.00 this month."
    assert "Spending by category" not in good.prompts[0] and "8500.0" in good.prompts[0] and "ONLY numbers" in good.prompts[0]
    bad = scripted("You spent ₹123,456.00 on food, so cut it by 40.5%.")
    out = run_node(transaction_analyzer, initial_state(me["id"], M, Y), ctx_for(finance_api, llm=bad))
    assert "narrative" not in out["spending_analysis"] and out["spending_analysis"]["total_spent"] == 13900.0  # numbers unaffected


def test_llm_failure_or_missing_key_still_produces_full_report(finance_api, monkeypatch):
    seed_month(finance_api)
    me = finance_api.client.get("/api/v1/users/me", headers=finance_api.headers).json()
    for ctx in (ctx_for(finance_api, llm=scripted(RuntimeError("gemini down"))), ctx_for(finance_api)):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        final = build_financial_report_graph().invoke(initial_state(me["id"], M, Y), config={"configurable": {"report_ctx": ctx}})
        assert final["report_status"] == "complete" and "AI commentary" not in final["final_report"] and len(final["messages"]) == 4


def test_llm_never_changes_the_calculated_numbers(finance_api):
    seed_month(finance_api)
    me = finance_api.client.get("/api/v1/users/me", headers=finance_api.headers).json()
    plain = generate_financial_report(me["id"], M, Y, token=finance_api.token, base_url=BASE, use_llm=False)
    llm = scripted("Income was ₹80,000.00 and expenses ₹13,900.00.")
    narrated = generate_financial_report(me["id"], M, Y, token=finance_api.token, base_url=BASE, llm=llm)
    for key in ("spending_analysis", "budget_analysis", "savings_recommendations"):
        strip = lambda d: {k: v for k, v in d.items() if k != "narrative"} if isinstance(d, dict) else d  # noqa: E731
        assert strip(plain[key]) == strip(narrated[key])
    assert "AI commentary" in narrated["final_report"] and "AI commentary" not in plain["final_report"]


# ======================================================================== routing (TC-02-P5-ROUTE-*)
def test_route_01_02_03_conditional_edges():
    ok = {**initial_state(1, 6, 2026), "report_status": "in_progress", "errors": []}
    assert should_continue_after_analysis(ok) == "budget_advisor"
    assert should_continue_after_analysis({**ok, "errors": ["1", "2", "3"]}) == "report_generator"
    assert should_continue_after_analysis({**ok, "errors": ["1", "2"]}) == "budget_advisor"
    assert should_continue_after_analysis({**ok, "report_status": "error"}) == "report_generator"


def test_route_04_05_06_compiled_graph_structure():
    g = build_financial_report_graph()
    assert hasattr(g, "invoke")
    drawn = g.get_graph()
    assert {"transaction_analyzer", "budget_advisor", "savings_optimizer", "report_generator"} <= set(drawn.nodes)
    edges = {(e.source, e.target) for e in drawn.edges}
    assert ("__start__", "transaction_analyzer") in edges and ("report_generator", "__end__") in edges
    assert {("transaction_analyzer", "budget_advisor"), ("transaction_analyzer", "report_generator"), ("budget_advisor", "savings_optimizer"), ("savings_optimizer", "report_generator")} <= edges


def test_supervisor_routing_is_logged(capsys):
    should_continue_after_analysis({**initial_state(1, 6, 2026), "errors": ["a", "b", "c"]})
    row = next(json.loads(line) for line in capsys.readouterr().out.splitlines() if '"supervisor_route"' in line)
    assert row["to_agent"] == "report_generator" and row["reason"] == "too_many_errors" and row["phase"] == 5


# ======================================================================== end to end (TC-02-P5-E2E-*)
def test_e2e_full_pipeline_complete_report(finance_api):
    seed_month(finance_api, rent_card=6000)
    final = generate_financial_report(None, M, Y, token=finance_api.token, base_url=BASE, use_llm=False)  # user derived from the token
    assert final["report_status"] == "complete" and final["errors"] == []
    assert [m.split(":")[0] for m in final["messages"]] == ["Transaction Analyzer", "Budget Advisor", "Savings Optimizer", "Report Generator"]
    assert isinstance(final["final_report"], str) and len(final["final_report"]) > 500
    assert "total_spent" in final["spending_analysis"] and final["savings_recommendations"]
    r = final["final_report"]
    assert "₹80,000.00" in r and "₹19,900.00" in r and "Entertainment" in r and "🔴" in r  # entertainment 120% of its budget
    assert "Card repayment" not in r  # transfers never appear as spending
    assert r.count("## ") == 8


def test_e2e_error_route_produces_a_partial_error_report(monkeypatch):
    monkeypatch.setattr(httpx, "request", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    final = generate_financial_report(5, M, Y, token="x", base_url="http://localhost:9999/api/v1", use_llm=False)
    assert final["report_status"] == "error" and len(final["messages"]) == 2  # analyzer then straight to the report
    assert "Data notes" in final["final_report"] and any("unavailable" in e.lower() for e in final["errors"])


def test_e2e_empty_account_gives_a_valid_report(finance_api):
    final = generate_financial_report(None, M, Y, token=finance_api.token, base_url=BASE, use_llm=False)
    assert final["report_status"] == "complete" and "No income or expenses were recorded" in final["final_report"] and "No budgets were set" in final["final_report"]


def test_e2e_report_is_scoped_to_the_token_user(finance_api, second_api):
    seed_month(finance_api)
    final = generate_financial_report(None, M, Y, token=second_api.token, base_url=BASE, use_llm=False)
    assert final["spending_analysis"]["total_spent"] == 0.0 and final["budget_data"] == [] and "₹80,000.00" not in final["final_report"]


def test_e2e_report_only_reads_data(finance_api):
    seed_month(finance_api)
    finance_api.calls.clear()
    generate_financial_report(None, M, Y, token=finance_api.token, base_url=BASE, use_llm=False)
    assert finance_api.calls and {m for m, _ in finance_api.calls} == {"GET"}


# ======================================================================== observability
def test_obs_structured_logs_and_spans(finance_api, capsys, monkeypatch):
    from contextlib import contextmanager

    names = []

    @contextmanager
    def rec(name, **kw):
        names.append(name)

        class S:
            def set_attribute(self, *a):
                pass

        yield S()

    for mod in (agents_mod, graph_mod):
        monkeypatch.setattr(mod, "span", rec)
    seed_month(finance_api)
    generate_financial_report(None, M, Y, token=finance_api.token, base_url=BASE, use_llm=False)
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    started = next(r for r in rows if r.get("event") == "report_generation_started")
    done = next(r for r in rows if r.get("event") == "report_generation_completed")
    activations = [r for r in rows if r.get("event") == "agent_activated"]
    assert started["poc_id"] == done["poc_id"] == "POC-02" and started["phase"] == done["phase"] == 5 and done["status"] == "complete" and done["agents_activated"] == 4
    assert [a["agent"] for a in activations] == ["transaction_analyzer", "budget_advisor", "savings_optimizer", "report_generator"]
    assert {"graph.execute", "agent.transaction_analyzer.activate", "agent.budget_advisor.activate", "agent.savings_optimizer.activate",
            "agent.report_generator.activate", "supervisor.route"} <= set(names)
    assert finance_api.token not in json.dumps(rows)


# ======================================================================== CLI + Streamlit report page
def test_cli_report_runner(finance_api, tmp_path, capsys):
    from multi_agent import report_runner

    seed_month(finance_api)
    out_file = tmp_path / "report.md"
    code = report_runner.main(["--email", finance_api.email, "--password", "testpass123", "--month", str(M), "--year", str(Y), "--no-llm", "--output", str(out_file)])
    text = capsys.readouterr().out
    assert code == 0 and "FINANCIAL HEALTH REPORT" in text and "Agent Execution Log" in text and out_file.read_text().startswith("# Financial Health Report")
    assert report_runner.main(["--email", finance_api.email, "--password", "wrong-password", "--no-llm"]) == 2


def test_streamlit_report_page_generates_a_report(finance_api, monkeypatch):
    import os

    from streamlit.testing.v1 import AppTest

    import mcp_server.chat_interface as chat

    seed_month(finance_api)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    at = AppTest.from_file(os.path.join(os.path.dirname(chat.__file__), "chat_interface.py"), default_timeout=90).run()
    at.sidebar.text_input[0].set_value(finance_api.email)
    at.sidebar.text_input[1].set_value("testpass123")
    next(b for b in at.sidebar.button if b.label == "Sign in").click().run()
    at.sidebar.radio[0].set_value("Financial health report").run()
    assert not at.exception
    at.selectbox[0].set_value(M).run()
    at.number_input[0].set_value(Y).run()
    next(b for b in at.button if b.label == "Generate report").click().run()
    assert not at.exception
    assert any("Financial Health Report — October 2026" in m.value for m in at.markdown)
    assert any("Report Generator" in str(e.label) or "agent" in str(e.label).lower() for e in at.expander)
    at.session_state["executor"] and at.session_state["executor"].close()
