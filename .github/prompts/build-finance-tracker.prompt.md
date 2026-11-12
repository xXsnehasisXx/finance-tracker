# MASTER PROMPT — BUILD POC-02 PERSONAL FINANCE TRACKER & ANALYTICS

Act as a Senior Full-Stack Python Developer, React Developer, Database Architect and AI Engineer.

You are responsible for implementing a complete, functional Personal Finance Tracker & Analytics application based on the supplied POC-02 specification.

This is a real development assignment, not a tutorial or a mockup exercise.

Your objective is to deliver a working application with all five specified development phases within a maximum of 4–5 working days.

Follow `.github/copilot-instructions.md` throughout the project.

---

# 1. FIRST: UNDERSTAND THE PROJECT

Before writing any code, inspect the entire currently opened workspace.

Perform the following tasks:

1. Inspect the complete directory structure.
2. Identify all existing source code and configuration files.
3. Recursively inspect the `extras/` directory.
4. Identify all PDFs, Markdown files, Python files, JSON files and other useful reference materials.
5. Read the contents of relevant supporting documents.
6. Locate and read the Finance Tracker POC-02 PDF.
7. Extract all requirements, entities, business rules, phase descriptions, API specifications and technology requirements.
8. Inspect any existing implementation before deciding what needs to be created.

Do not modify, delete or overwrite reference files.

Do not assume that the repository is empty.

If the POC PDF is not found in the workspace, report that and request the document to be attached. Do not invent missing requirements.

Create a concise `PROJECT_ANALYSIS.md` containing:
- Project overview.
- Requirements extracted from the POC.
- Existing repository structure.
- Relevant supporting files discovered.
- Proposed architecture.
- Database relationships.
- API implementation plan.
- Five-phase implementation roadmap.
- Risks and dependencies.

After completing the initial inspection, proceed with implementation. Do not spend excessive time producing documentation.

# 2. STRICT TECHNOLOGY STACK

Use ONLY the specified project technologies.

Frontend:
- React
- Vite
- JavaScript
- JSX
- CSS

Backend:
- Python
- FastAPI
- SQLAlchemy
- SQLite
- JWT Bearer Authentication
- structlog

Phase 2:
- LangChain
- ChromaDB
- Gemini 2.0 Flash

Phase 3:
- LangChain tools and tool calling
- REST API integration
- RAG integration

Phase 4:
- fastmcp
- Streamlit

Phase 5:
- LangGraph
- Four specialized agents

Testing:
- pytest
- httpx TestClient

STRICT RESTRICTIONS:

- No TypeScript.
- No TSX.
- No Node.js backend.
- No Express.js.
- No MongoDB.
- No PostgreSQL.
- No alternative ORM.
- No alternative AI orchestration framework.
- No unnecessary frontend or backend frameworks.
- No replacement of the technologies specified in the POC.

Do not introduce additional major technologies or frameworks.

Use only minimal supporting packages where technically necessary, and document why they are needed.

# 3. APPLICATION ARCHITECTURE

Create a clean and maintainable project structure.

Suggested structure:

finance-tracker/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── layouts/
│   │   ├── services/
│   │   ├── contexts/
│   │   ├── hooks/
│   │   ├── styles/
│   │   ├── utils/
│   │   └── App.jsx
│   ├── index.html
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── ai/
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── run.py
│
├── ai/
│   ├── rag/
│   ├── tools/
│   ├── mcp/
│   ├── streamlit_app/
│   └── agents/
│
├── docs/
├── extras/
├── .github/
├── .env.example
├── .gitignore
├── README.md
└── PROJECT_PROGRESS.md

You may adjust this structure if the existing repository already has a better organization.

Do not create duplicate frontend, backend or AI directories.

Keep the frontend, REST backend and AI components clearly separated.

# 4. PHASE 1 — FULL-STACK FINANCE TRACKER

Implement the complete core application.

## Database entities

Implement the following entities according to the POC:

USER:
- id
- name
- email
- phone
- monthly_income
- created_at

ACCOUNT:
- id
- user_id
- account_name
- account_type
- balance
- currency
- created_at

TRANSACTION:
- id
- account_id
- amount
- type
- category
- description
- merchant
- transaction_date
- created_at

BUDGET:
- id
- user_id
- category
- monthly_limit
- month
- year
- created_at

BUDGET_ALERT:
- id
- budget_id
- alert_type
- triggered_at

Implement the foreign keys, relationships, constraints and validation.

## Authentication

Implement:
- User registration.
- User login.
- Secure password handling.
- JWT access tokens.
- Protected endpoints.
- Authenticated frontend sessions.
- Logout functionality.
- Authorization checks for user-owned resources.

Never store plaintext passwords.

## Account management

Users should be able to:
- Create accounts.
- View accounts.
- Edit account details.
- View individual balances.
- Delete accounts only when business rules permit.

Support savings, checking and credit account types as described in the POC.

## Transaction management

Users should be able to:
- Add income transactions.
- Add expense transactions.
- View transactions.
- Edit transactions.
- Delete transactions.
- Filter by category.
- Filter by date.
- Filter by transaction type.
- View transaction details.

Categories must include:
- Food
- Transport
- Utilities
- Entertainment
- Health
- Salary
- Other

Implement automatic balance updates.

IMPORTANT FINANCIAL LOGIC:

For a debit:
- Decrease account balance.

For a credit:
- Increase account balance.

When an existing transaction is edited or deleted, correctly reverse its previous balance effect before applying the new effect.

Use atomic database transactions for financial operations.

Avoid floating-point monetary calculations. Use decimal-safe calculations and suitable SQLite storage.

## Budget management

Implement:
- Monthly budgets.
- Category-specific budgets.
- Budget creation.
- Budget editing.
- Budget deletion.
- Budget utilization calculations.
- Budget warning at 80%.
- Budget exceeded alert at 100%.
- Budget history.

Enforce the unique constraint for user, category, month and year.

## Dashboard

Build a professional dashboard containing:

- Total account balance.
- Monthly income.
- Monthly expenses.
- Net cash flow.
- Savings rate.
- Spending by category.
- Recent transactions.
- Monthly budget utilization.
- Budget alerts.
- Income versus expense overview.

All dashboard figures must be calculated from actual database records.

Do not hardcode dashboard statistics.

## API implementation

Create REST endpoints for all required functionality.

Use versioned API routes under `/api/v1`.

Include suitable endpoints for:
- Authentication.
- Users.
- Accounts.
- Transactions.
- Budgets.
- Budget alerts.
- Dashboard analytics.

Keep API routing separate from business logic.

# 5. PHASE 2 — RAG APPLICATION

Implement a documentation-based financial FAQ assistant.

Requirements:

1. Create a user manual based on the actual application functionality.
2. Load the manual into a LangChain document-processing pipeline.
3. Split documents into appropriate chunks.
4. Generate embeddings.
5. Store and retrieve document embeddings using ChromaDB.
6. Connect Gemini 2.0 Flash.
7. Implement contextual question answering.
8. Ground responses in retrieved documentation.
9. Handle questions outside the knowledge base appropriately.

Example questions:

- How do I create a monthly budget?
- How do I add a grocery expense?
- What categories are available?
- How does the 80% budget warning work?
- How can I view my transaction history?

Do not make the chatbot invent application features.

Include a source-aware retrieval workflow.

# 6. PHASE 3 — CONTEXT ENGINEERING AND TOOL INTEGRATION

Extend the Phase 2 chatbot into a financial assistant.

The assistant must access live application data using LangChain tools and existing REST APIs.

Implement tools for:

- Retrieving accounts.
- Retrieving transactions.
- Calculating monthly income.
- Calculating monthly expenses.
- Retrieving budgets.
- Checking budget utilization.
- Retrieving spending by category.
- Calculating savings rate.

Example interaction:

User: "Am I over budget on food this month?"

Expected workflow:

1. Understand the user's question.
2. Identify the relevant category and month.
3. Call the transaction retrieval tool.
4. Call the budget retrieval tool.
5. Calculate actual utilization.
6. Retrieve relevant budgeting guidance through RAG.
7. Generate an answer using actual application data.

The agent must never invent financial values.

Use the authenticated user's context when accessing data.

Do not allow the agent to access another user's information.

# 7. PHASE 4 — MCP SERVER AND CONVERSATIONAL INTERFACE

Implement an MCP server using fastmcp.

Expose appropriate financial application operations as MCP tools.

Include tools for:

- Adding transactions.
- Retrieving transactions.
- Retrieving accounts.
- Retrieving budgets.
- Checking budget utilization.
- Retrieving financial summaries.

Implement a Streamlit conversational interface.

Example interaction:

User: "Add a ₹500 grocery expense for today."

Expected workflow:

1. Extract amount, category and date.
2. Identify the relevant account.
3. Ask for missing information when necessary.
4. Validate the transaction.
5. Request confirmation before executing a financial write operation.
6. Execute the operation through the MCP tool.
7. Confirm success only after the backend verifies the operation.
8. Display the updated transaction information.

Do not bypass the backend business logic.

Keep the MCP implementation separate from the core REST API.

# 8. PHASE 5 — MULTI-AGENT FINANCIAL HEALTH REPORT

Implement a LangGraph workflow containing four specialized agents.

AGENT 1: TRANSACTION ANALYZER

Responsibilities:
- Analyze transaction history.
- Identify spending patterns.
- Identify high-spending categories.
- Compare spending across periods.

AGENT 2: BUDGET ADVISOR

Responsibilities:
- Evaluate budget utilization.
- Identify exceeded budgets.
- Identify spending risks.
- Suggest budget adjustments.

AGENT 3: SAVINGS OPTIMIZER

Responsibilities:
- Analyze income and expenses.
- Calculate savings rate.
- Identify discretionary spending.
- Recommend realistic savings opportunities.

AGENT 4: REPORT GENERATOR

Responsibilities:
- Receive the outputs of the previous agents.
- Consolidate financial findings.
- Produce a structured financial health report.
- Generate clear, actionable recommendations.

Use LangGraph to coordinate the agents and manage shared workflow state.

Ensure agents use actual financial data retrieved through validated tools.

Include appropriate error handling and observability.

The final report should include:
- Income overview.
- Expense overview.
- Spending patterns.
- Budget performance.
- Savings analysis.
- Financial risks.
- Actionable recommendations.

# 9. FRONTEND DESIGN REQUIREMENTS

Build a polished and professional financial dashboard.

Use React, JavaScript and CSS.

Design requirements:

- Responsive desktop and mobile layouts.
- Sidebar navigation.
- Dashboard overview.
- Accounts page.
- Transactions page.
- Budgets page.
- Analytics section.
- Profile section.
- AI assistant entry point.
- Clear empty states.
- Loading indicators.
- Form validation.
- Success and error notifications.

Use a consistent visual design.

Avoid unnecessary animations and excessive decorative effects.

Prioritize usability and functional workflows over visual complexity.

All displayed financial data must come from the backend.

# 10. TESTING REQUIREMENTS

Write automated tests using pytest and httpx TestClient.

Prioritize:

- Registration and authentication.
- JWT validation.
- User authorization.
- Account CRUD.
- Transaction CRUD.
- Credit and debit calculations.
- Transaction edit and deletion reversals.
- Budget calculations.
- 80% and 100% threshold conditions.
- Duplicate budget prevention.
- Dashboard aggregations.
- AI tool authorization.
- MCP tool execution.
- Multi-agent error handling.

Run tests after every significant implementation stage.

Fix critical errors before continuing.

Do not hide failing tests or mark incomplete functionality as completed.

# 11. FOUR-TO-FIVE-DAY EXECUTION PLAN

Optimize the implementation for the available time.

DAY 1:
- Repository analysis.
- Architecture.
- Database.
- Authentication.
- Core FastAPI endpoints.
- Account and transaction operations.

DAY 2:
- Budget management.
- Financial business logic.
- Dashboard analytics.
- React frontend.
- Integration with backend.

DAY 3:
- Complete frontend workflows.
- Testing and corrections.
- RAG implementation.
- LangChain integration.
- Gemini 2.0 Flash integration.

DAY 4:
- Tool-calling agent.
- Financial API tools.
- fastmcp server.
- Streamlit conversational interface.

DAY 5:
- LangGraph multi-agent pipeline.
- Financial health report.
- Integration testing.
- Bug fixes.
- README and final documentation.

If a phase requires simplification, preserve its required architecture and demonstrate its essential workflow. Never replace a required technology with a mock implementation while claiming it is complete.

# 12. DEVELOPMENT WORKFLOW

Follow this workflow:

1. Inspect before modifying.
2. Plan the current implementation stage.
3. Implement only the necessary files.
4. Check imports and dependencies.
5. Run relevant tests.
6. Fix errors.
7. Verify integration.
8. Update PROJECT_PROGRESS.md.
9. Move to the next stage.

Do not generate the entire project in one enormous code-generation operation.

Avoid repeated rewrites and unnecessary dependencies.

Do not create fake data to simulate completed integrations.

Use seed data only for explicitly identified development/demo scenarios.

Maintain a working application throughout development.

# 13. FINAL DELIVERY

At the end, provide:

1. Complete source code.
2. Working React frontend.
3. Working FastAPI backend.
4. SQLite database initialization.
5. Environment variable example file.
6. API documentation.
7. RAG implementation.
8. Tool-calling implementation.
9. MCP server.
10. Streamlit chat interface.
11. LangGraph multi-agent implementation.
12. Automated test suite.
13. README with setup and execution instructions.
14. PROJECT_PROGRESS.md.
15. Known limitations and incomplete items, if any.

Provide exact commands to install dependencies and run each component.

The project must be executable on a local development machine.

FINAL INSTRUCTION:

Take ownership of the development process.

Be systematic, efficient and precise.

Do not ask unnecessary questions when requirements are already available in the POC or reference files.

When requirements are ambiguous, make the smallest reasonable assumption, document it and continue.

Never sacrifice financial data integrity, authentication or security for speed.

Begin by inspecting the repository and its reference materials. Then proceed with implementation in the prescribed order.
