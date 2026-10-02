# Verification report

The project was checked with Python 3.12.14 using the pinned dependencies in the requirements files.

## Automated checks

The initial complete suite passed 22 tests, including:

- Backend authentication, health, ticket listing, creation, and missing-ticket behavior.
- Approval required before refund; rejection creates no refund.
- Ineligible, pending, missing, already-refunded, and mismatched-amount cases.
- Transaction changes between investigation and approval.
- Duplicate and concurrent approval requests.
- Two tickets referencing the same payment.
- Paused approval surviving application restart.
- Recovery after a simulated crash immediately after the refund transaction commits.
- Idempotent startup seeding.
- Invalid approval payload rejection.
- Gemini provider failure fallback and advisory-only AI text.
- Streamlit login, overview, investigation, approval, success result, ticket creation, and help screen through AppTest.

Run the suite with `python -m pytest -q` after installing `requirements-dev.txt`.

## Validation boundaries

Integration tests use SQLite databases and real LangGraph checkpoint persistence. The Streamlit AppTest exercises the app with the real FastAPI test client; it is not a visual browser screenshot test.

PostgreSQL/Neon configuration and the deployment files are provided, but no user-owned Neon, Render, or Streamlit service was provisioned during packaging. Verify the online persistence and approval flow after deployment using the checklist in `ONLINE_SETUP.md`.

Gemini requests are tested with mocked provider responses. No live model request was made because no user API key was provided. Real POS and payment systems are not connected.
