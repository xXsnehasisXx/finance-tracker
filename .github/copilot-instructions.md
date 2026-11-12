# GitHub Copilot Project Instructions — Finance Tracker

## 1. Project Identity

Project: POC-02 — Personal Finance Tracker & Analytics

Domain: Banking

Objective: Build a complete, functional, AI-powered personal finance tracking application following the supplied POC specification.

The primary source of truth is the Finance Tracker POC PDF in the project documentation. Supporting reference materials are located in the `extras/` directory.

## 2. Strict Technology Requirements

### Frontend
- React
- Vite
- JavaScript (ES6+)
- JSX only
- Responsive CSS

TypeScript, TSX and other frontend frameworks are prohibited.

### Backend
- Python
- FastAPI
- SQLAlchemy
- SQLite
- JWT Bearer Authentication
- structlog

### AI Stack
- LangChain
- ChromaDB
- Gemini 2.0 Flash for the RAG application
- LangChain tool calling
- fastmcp
- Streamlit
- LangGraph

### Testing
- pytest
- httpx TestClient

Do not replace any specified technology with an alternative.

Do not introduce additional frameworks, databases, ORMs, agent orchestration platforms or frontend frameworks.

Minimal supporting dependencies required to implement specified functionality are permitted. Document their purpose.

## 3. Development Rules

1. Inspect the existing repository before creating or modifying files.
2. Never assume a file or directory does not exist without checking.
3. Preserve existing working code.
4. Avoid unnecessary rewrites.
5. Maintain a clear separation between frontend, backend, database and AI components.
6. Use reusable React components.
7. Keep API routes, business logic, database operations and schemas appropriately separated.
8. Use SQLAlchemy relationships and constraints correctly.
9. Use environment variables for credentials and secrets.
10. Never hardcode API keys or JWT secrets.
11. Never expose sensitive information in logs.
12. Implement appropriate error handling and input validation.
13. Keep code readable, modular and maintainable.
14. Use meaningful filenames, variable names and function names.
15. Do not create duplicate implementations of existing functionality.

## 4. Database and Financial Integrity

The required entities are:

- USER
- ACCOUNT
- TRANSACTION
- BUDGET
- BUDGET_ALERT

Follow the data relationships and business rules in the POC.

Critical rules:

- Every debit decreases the relevant account balance.
- Every credit increases the relevant account balance.
- Budget warning triggers at 80% utilization.
- Budget exceeded alert triggers at 100% utilization.
- Enforce one budget per user, category and month.
- Transactions belong to accounts, not directly to users.
- Prevent unauthorized cross-user data access.
- Maintain consistency when transactions are edited or deleted.
- Use appropriate database transactions for related financial updates.

Use decimal-safe financial arithmetic rather than binary floating-point calculations for monetary values.

## 5. AI Implementation

Implement the five POC phases sequentially.

Phase 1: Full-stack finance application.

Phase 2: RAG chatbot using LangChain, ChromaDB and Gemini 2.0 Flash, grounded in the application user manual.

Phase 3: Context-aware tool-calling agent integrating financial REST APIs and RAG.

Phase 4: MCP server using fastmcp and a Streamlit conversational interface.

Phase 5: LangGraph multi-agent pipeline with:
- Transaction Analyzer
- Budget Advisor
- Savings Optimizer
- Report Generator

Keep the AI components modular and separate from core financial transaction processing.

AI agents must not independently invent or modify financial records.

All financial operations must pass through validated backend business logic.

## 6. Reference Material Rules

Inspect the `extras/` directory recursively.

Read relevant reference files and understand their contents before implementation.

Use the supplied Finance Tracker POC PDF as the primary specification.

Supporting files are references, not permission to introduce unrelated technology.

Do not modify, delete or overwrite original reference materials.

If a reference contradicts the POC, report the discrepancy and follow the POC unless explicitly instructed otherwise.

## 7. Frontend Quality

- Build a modern, professional financial dashboard.
- Use responsive layouts for desktop, tablet and mobile.
- Provide clear navigation.
- Include loading, empty, success and error states.
- Ensure forms have proper validation.
- Display financial values consistently in INR (₹).
- Use meaningful visualizations without introducing an unapproved charting framework.
- Keep UI components reusable.

## 8. Testing and Validation

- Test all API endpoints.
- Test financial calculations.
- Test account balance updates.
- Test budget threshold conditions.
- Test authentication and authorization.
- Test cross-user access restrictions.
- Test RAG retrieval and tool execution.
- Test MCP tools and agent workflows.
- Fix regressions before proceeding to the next phase.

Use pytest and httpx TestClient for backend testing.

Never claim a feature is working unless it has been implemented and verified.

## 9. Copilot Agent Working Method

- Work in small, controlled implementation stages.
- Inspect existing code before changing it.
- Explain the intended changes before large modifications.
- Avoid regenerating entire files when a targeted change is sufficient.
- Do not install unnecessary packages.
- Do not run destructive commands without approval.
- Never delete user files or reference documents.
- Run relevant tests after every significant change.
- Report errors honestly.
- Maintain a project progress document.

## 10. Time Constraint

The project must be prepared within 4–5 working days.

Prioritize:
1. Working application and database.
2. Financial business rules.
3. Core dashboard and CRUD workflows.
4. RAG integration.
5. Tool-calling agent.
6. MCP integration.
7. Multi-agent demonstration.
8. Testing and final documentation.

Do not sacrifice financial correctness or security to save time.

If time becomes insufficient, prioritize complete demonstrable workflows over superficial implementations.

## 11. Completion Criteria

A phase is complete only when:

- Its required functionality exists.
- Its integration with previous phases works.
- Relevant tests pass.
- No critical regression is introduced.
- Its implementation is documented.

Maintain `PROJECT_PROGRESS.md` with:
- Completed tasks.
- Pending tasks.
- Files created or modified.
- Tests executed and results.
- Known issues.
- Remaining work.

Always follow the supplied POC specification and these project instructions.
