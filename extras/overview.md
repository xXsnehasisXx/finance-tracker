# POC-02: Personal Finance Tracker & Analytics

**Domain:** Banking | **Difficulty:** Intermediate | **POC ID:** POC-02

---

## Business Context

Personal financial management is one of the most impactful digital banking services. Studies show that users who actively track their spending save 15-20% more than those who don't. A personal finance tracker helps individuals understand where their money goes, set spending limits, and receive actionable insights — transforming a bank from a mere transaction processor into a trusted financial partner.

In this POC, you will build a comprehensive personal finance tracking system that evolves from a full-stack CRUD application into an AI-powered financial advisor, capable of analyzing spending patterns, alerting on budget overruns, and generating multi-agent financial health reports with personalized recommendations.

---

## What You Will Build Across All 5 Phases

**Phase 1 — Full Stack Application:**
Build a complete personal finance tracker with a REST API backend, React frontend, and SQLite database. Users can manage multiple accounts (savings, checking, credit), record transactions with categories (food, transport, utilities, entertainment, health, salary), set monthly budgets per category, and view a dashboard showing income vs expenses, spending by category, and budget alerts. Built using GitHub Copilot vibe coding.

**Phase 2 — RAG Application:**
Build a Q&A chatbot trained on the app's user manual. Users can ask questions like "How do I set a monthly budget?" or "What categories are available?" and get accurate answers grounded in the documentation.

**Phase 3 — Context Engineering & Tool Integration:**
Extend the chatbot into an agent that can access live financial data. Users can ask "Am I over budget on food this month?" and the agent calls both the REST API (for actual spending) and the RAG chain (for guidance on managing food expenses).

**Phase 4 — MCP Server & Chat Interface:**
Convert the REST API to an MCP server and build a conversational financial assistant. Users can say "Add a ₹500 grocery expense for today" and the assistant records the transaction through natural language.

**Phase 5 — Multi-Agent Financial Health Report:**
Build a LangGraph pipeline with 4 specialized agents — Transaction Analyzer, Budget Advisor, Savings Optimizer, and Report Generator — that automatically produces a comprehensive financial health report with actionable recommendations.

---

## Key Learning Outcomes

1. Design a relational data model for financial transactions with categories and budgets
2. Implement automatic balance updates on transaction creation
3. Build budget alerting logic (warn at 80%, alert at 100%)
4. Create aggregation queries for spending analytics by category and time period
5. Build a RAG pipeline trained on financial documentation
6. Implement context-aware financial analysis tools
7. Convert a financial API to MCP protocol
8. Build a conversational financial assistant with Streamlit
9. Design multi-agent workflows for financial report generation
10. Apply LangGraph Supervisor pattern for sequential agent coordination
11. Implement comprehensive observability for financial AI systems
12. Write automated test suites covering financial calculations and AI outputs

---

## User Personas

### Persona 1: Arjun Kapoor — The Young Professional
- **Background:** 26-year-old software engineer, first job, wants to save for a car
- **Goals:** Track where salary goes, set budgets, see how much he can save monthly
- **Pain Points:** Doesn't know where money disappears, often exceeds dining budget
- **Usage:** Adds transactions via chat (Phase 4), checks monthly report (Phase 5)

### Persona 2: Sunita Patel — The Family Budget Manager
- **Background:** 38-year-old homemaker managing household finances for a family of 4
- **Goals:** Track household expenses by category, ensure bills are paid, control grocery spending
- **Pain Points:** Multiple expense categories, hard to track what's over budget
- **Usage:** Dashboard view (Phase 1), budget alerts (Phase 2 chatbot Q&A)

### Persona 3: Rahul Verma — The Financial Advisor
- **Background:** 45-year-old financial consultant reviewing client finances
- **Goals:** Analyze spending patterns, identify waste, recommend savings strategies
- **Usage:** Phase 5 multi-agent report for comprehensive client analysis

---

## Domain Terminology Glossary

| Term | Definition |
|------|-----------|
| **Net Worth** | Total assets minus total liabilities |
| **Cash Flow** | Net income minus total expenses for a period |
| **Discretionary Spending** | Optional expenses (dining, entertainment) — can be cut |
| **Fixed Expenses** | Recurring mandatory costs (rent, utilities, EMI) |
| **Savings Rate** | Percentage of income saved: (income - expenses) / income × 100 |
| **Budget Variance** | Difference between budgeted and actual spending |
| **50/30/20 Rule** | 50% needs, 30% wants, 20% savings — popular budgeting framework |
| **Expense Category** | Classification of spending: food, transport, utilities, etc. |
| **Income Category** | Sources: salary, freelance, investments, etc. |
| **Zero-Based Budgeting** | Every rupee assigned a purpose before the month begins |
| **Envelope Method** | Physical/virtual envelopes for each spending category |
| **Rolling Average** | Average over a moving time window (last 3 months of expenses) |
| **FIRE** | Financial Independence, Retire Early — aggressive savings movement |
| **Emergency Fund** | 3-6 months of expenses kept liquid for unexpected events |
| **Compound Interest** | Interest on interest — key concept for savings growth |

---

## Data Model

```
┌─────────────────────────────────────────────────┐
│                      USER                        │
│  id | name | email | phone | monthly_income      │
│  created_at                                      │
└─────────────────────┬───────────────────────────┘
                      │ 1:N
                      ▼
┌─────────────────────────────────────────────────┐
│                    ACCOUNT                       │
│  id | user_id (FK) | account_name | account_type │
│  balance | currency | created_at                │
└──────────────────┬──────────────────────────────┘
                   │ 1:N
                   ▼
┌──────────────────────────────────────────────────────────────┐
│                       TRANSACTION                             │
│  id | account_id (FK) | amount | type[credit/debit]          │
│  category[food/transport/utilities/entertainment/health/     │
│           salary/other] | description | merchant             │
│  transaction_date | created_at                               │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                        BUDGET                                │
│  id | user_id (FK) | category | monthly_limit | month | year │
│  created_at                                                  │
└──────────────────────────┬───────────────────────────────────┘
                           │ 1:N
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      BUDGET_ALERT                            │
│  id | budget_id (FK) | alert_type[warning_80/exceeded]       │
│  triggered_at                                                │
└──────────────────────────────────────────────────────────────┘
```

### Business Rules
- Every debit transaction decreases account balance; every credit increases it
- Budget alerts fire at 80% utilization (warning_80) and 100% (exceeded)
- One budget per user per category per month (unique constraint)
- Transactions link to accounts, not directly to users

---

## Phase Progression Roadmap

| Phase | What You Build | Key Technologies Added |
|-------|---------------|----------------------|
| 1 | Finance tracker CRUD app | FastAPI + React + SQLite + JWT + Auto-balance updates |
| 2 | Finance FAQ chatbot | LangChain + ChromaDB + Gemini 2.0 Flash + User manual |
| 3 | Live spending agent | LangChain tools calling Transaction/Budget APIs |
| 4 | Conversational finance assistant | fastmcp + Streamlit chat ("Add ₹500 grocery") |
| 5 | AI financial health report | LangGraph 4-agent pipeline |
