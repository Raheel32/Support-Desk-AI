# Support Desk AI

A complete educational support-workflow demo with a Streamlit dashboard, FastAPI backend, and durable LangGraph approvals. Investigate a fictional failed order, inspect transaction evidence, approve or reject a proposal, and record a simulated refund.

Start with [the online deployment guide](docs/ONLINE_SETUP.md). It covers putting this package into `Raheel32/Support-Desk-AI`, deploying FastAPI on Render, storing data in Neon PostgreSQL, and hosting the dashboard on Streamlit Community Cloud. Your computer can be switched off after deployment.

## What is included

- Password-protected Streamlit workspace with overview, ticket search, creation, investigation, evidence, and activity history.
- Backend API-key authentication and input validation.
- Six fictional cases, including successful approval, prior refund, pending payment, missing evidence, and action failure.
- Database analyst, log analyst, policy supervisor, approval interrupt, and action-execution stages.
- Persistent checkpoints: PostgreSQL online and SQLite for local development.
- Idempotent simulated refunds, revalidation immediately before execution, and recovery after a process interruption.
- Optional Gemini-generated explanation with an explicit rules-based fallback.
- Deployment configuration, Codespaces setup, GitHub Actions checks, and automated integration tests.

## Important scope

This is a working learning demo, not a connection to the existing POS and not a real refund service. The analyst stages use fixed read queries and deterministic policy checks. Gemini provides an explanation when configured; it does not choose arbitrary tools, write SQL, decide refund amounts, or bypass human approval. There is no autonomous LLM router in this version.

The commerce adapter and AI workflow share one FastAPI process in this demo. The action executor calls the simulated commerce service directly. Replacing that adapter with authenticated POS API calls is a separate integration task that needs provider access. Logical read-only analyst functions are not a database-level permission boundary; real integration requires restricted database credentials or provider read APIs.

Authentication uses one workspace password and one backend key. Reviewer names are self-reported labels, not verified individual identities. Use only fictional records. Individual accounts, role permissions, tenant isolation, rate limits, production migrations, background workers, and real payment processing are outside this demo.

## Online components

| Component | Service | Purpose |
| --- | --- | --- |
| Source code | GitHub | Version history and deployments |
| Dashboard | Streamlit Community Cloud | Open and review cases in a browser |
| Backend | Render Python web service | Run the API and LangGraph workflow |
| Database | Neon PostgreSQL | Keep records and checkpoints across restarts |
| Optional explanation | Google Gemini API | Explain the evidence |
| Optional browser editor | GitHub Codespaces | Edit and test without installing tools locally |

Use `AI_MODE=rules` first. This mode does not call an AI provider and needs no model key. Enable Gemini later using the deployment guide. Hosting and provider accounts have their own quotas and billing terms.

## Local Windows quick start

Open PowerShell in `D:\Support Desk AI`. Create `.venv` if it does not exist:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

If `.env` already exists, edit its settings instead of overwriting it. Choose a workspace password in `APP_PASSWORD` and keep the same `BACKEND_API_KEY` for the API and dashboard. The included example values are for local development only.

Start the backend in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Start Streamlit in another terminal, from the same project root:

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

Open `http://localhost:8501` and use the password from `.env`. The backend health check is `http://localhost:8000/health` and API documentation is `http://localhost:8000/docs`.

Run checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## First walkthrough

1. Sign in and open **Ticket workspace**.
2. Select **TKT-1001** and choose **Investigate ticket**.
3. Open **Evidence** and verify the failed order, captured payment, and order-failure log.
4. Return to **Investigation**. The proposed simulated refund is PKR 2,500.00.
5. Enter a reviewer name, add an optional note, and check the evidence confirmation.
6. Choose **Approve simulated refund**. The result has a refund reference and the ticket becomes resolved.
7. For rejection, create a new ticket linked to another eligible order before approving it. Rejection leaves the ticket in manual review and creates no refund.
8. Investigate **TKT-1006** and approve to demonstrate an intentional gateway failure. The ticket stays unresolved.

The same already-refunded order cannot be used for another successful refund. Seed data is inserted only when missing and is never reset on restart.

## Files to understand first

| File | Responsibility |
| --- | --- |
| `frontend/streamlit_app.py` | Screens and API requests |
| `backend/main.py` | API routes, authentication, decisions, recovery |
| `backend/workflow.py` | Analyst stages, supervisor, approval interrupt, explanation |
| `backend/commerce.py` | Refund rules, evidence fingerprints, simulated execution |
| `backend/database.py` | Business tables, audit history, concurrency lock |
| `backend/seed.py` | Six fictional sample scenarios |
| `backend/config.py` | Environment settings and production validation |
| `render.yaml` | Backend hosting configuration |
| `docs/ONLINE_SETUP.md` | Browser-based deployment instructions |
| `docs/ARCHITECTURE.md` | Design, limitations, and POS integration boundary |
| `docs/VERIFICATION.md` | Checks performed and remaining hosting validation |

## API summary

All `/api/*` routes require `X-API-Key: <BACKEND_API_KEY>`. Streamlit adds this header on the server, keeping the key out of browser-side requests.

| Method | Route | Result |
| --- | --- | --- |
| GET | `/health` | Service/database connectivity check |
| GET | `/api/config` | Mode and demo metadata |
| GET | `/api/orders` | Fictional orders available for linking |
| GET | `/api/tickets` | Ticket list |
| POST | `/api/tickets` | Create a ticket for an existing order |
| GET | `/api/tickets/{id}` | Ticket, runs, and audit history |
| POST | `/api/tickets/{id}/investigate` | Start or retrieve a pending investigation |
| POST | `/api/runs/{id}/decision` | Approve/reject the saved proposal |
| POST | `/api/runs/{id}/resume` | Recover saved progress without inventing approval |

The earlier unauthenticated `/tickets` starter route is replaced by `/api/tickets`. `main.py` remains a compatibility entry point for `uvicorn main:app`.

## Updating the project

Review changed files and run the tests before committing. Never commit `.env` or `.streamlit/secrets.toml`.

```powershell
git status
git add backend frontend tests docs .github .devcontainer .streamlit/config.toml .streamlit/secrets.toml.example .env.example .gitignore main.py requirements.txt requirements-dev.txt render.yaml README.md
git diff --cached --stat
git commit -m "Add complete Streamlit support desk demo"
git push origin main
```

After hosting is linked to the repository, use each provider's configured redeployment behavior to publish updates. Check the deployed health endpoint and the dashboard after changes.
