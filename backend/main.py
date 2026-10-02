"""Authenticated API for the Support Desk AI demo."""
from contextlib import asynccontextmanager
import logging
import secrets
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from backend.config import Settings
from backend.database import Audit, Database, Order, Run, Ticket, now, record
from backend.seed import seed
from backend.workflow import Workflow

logger = logging.getLogger(__name__)


class TicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    order_id: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=4000)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: Literal["approve", "reject"]
    reviewer: str = Field(min_length=2, max_length=100)
    note: str = Field(default="", max_length=1000)


def create_app(settings=None):
    settings = settings or Settings.from_env()
    settings.validate()
    db = Database(settings.database_url)
    workflow = Workflow(db, settings)

    @asynccontextmanager
    async def lifespan(app):
        with db.serial():
            db.setup()
            workflow.setup()
        if settings.seed_demo:
            seed(db)
        yield
        db.engine.dispose()

    app = FastAPI(title="Support Desk AI", version="1.0.0", lifespan=lifespan)
    app.state.db = db
    app.state.workflow = workflow

    def authorize(x_api_key: str = Header(default="")):
        if not secrets.compare_digest(x_api_key.encode(), settings.api_key.encode()):
            raise HTTPException(401, "A valid backend API key is required")

    auth = [Depends(authorize)]

    def get_ticket(session, ticket_id):
        ticket = session.get(Ticket, ticket_id)
        if ticket is None:
            raise HTTPException(404, "Ticket not found")
        return ticket

    def save_graph_state(run_id, graph, config):
        state = graph.get_state(config)
        values = dict(state.values)
        with db.Session.begin() as session:
            run = session.get(Run, run_id)
            if values:
                run.payload = values
                run.status = values.get("status", "investigating")
            run.updated_at = now()
            ticket = session.get(Ticket, run.ticket_id)
            ticket.status = {"awaiting_approval": "awaiting_approval", "resolved": "resolved",
                             "investigating": "investigating"}.get(run.status, "manual_review")
            return record(run)

    def invoke(run_id, command):
        config = {"configurable": {"thread_id": run_id}}
        try:
            with workflow.graph() as graph:
                graph.invoke(command, config=config)
                return save_graph_state(run_id, graph, config)
        except Exception:
            # Never include provider responses, secrets, or connection strings in the API response.
            logger.error("Investigation interrupted for run %s; recovery remains available", run_id)
            with db.Session.begin() as session:
                run = session.get(Run, run_id)
                run.status = "interrupted"
                run.updated_at = now()
                ticket = session.get(Ticket, run.ticket_id)
                ticket.status = "manual_review"
                db.audit(session, run.ticket_id, "workflow_interrupted", detail=run_id)
            raise HTTPException(503, "Workflow interrupted. Use Resume saved workflow; approved actions are idempotent.")

    @app.get("/health")
    def health():
        with db.Session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok", "service": "Support Desk AI", "simulation": True}

    @app.get("/api/config", dependencies=auth)
    def configuration():
        return {"ai_mode": settings.ai_mode, "simulation": True, "version": "1.0.0"}

    @app.get("/api/orders", dependencies=auth)
    def orders():
        with db.Session() as session:
            return [record(row) for row in session.scalars(select(Order).order_by(Order.id))]

    @app.get("/api/tickets", dependencies=auth)
    def tickets():
        with db.Session() as session:
            return [record(row) for row in session.scalars(select(Ticket).order_by(Ticket.created_at.desc()))]

    @app.post("/api/tickets", dependencies=auth, status_code=201)
    def create_ticket(body: TicketInput):
        with db.serial(), db.Session.begin() as session:
            if session.get(Order, body.order_id) is None:
                raise HTTPException(404, "Choose an existing demo order")
            ticket = Ticket(id=f"TKT-{uuid4().hex[:10]}", **body.model_dump(), status="open")
            session.add(ticket)
            session.flush()
            db.audit(session, ticket.id, "ticket_created", "dashboard", ticket.subject)
            return record(ticket)

    @app.get("/api/tickets/{ticket_id}", dependencies=auth)
    def ticket_detail(ticket_id: str):
        with db.Session() as session:
            ticket = get_ticket(session, ticket_id)
            runs = session.scalars(select(Run).where(Run.ticket_id == ticket_id).order_by(Run.created_at.desc()))
            audit = session.scalars(select(Audit).where(Audit.ticket_id == ticket_id).order_by(Audit.id.desc()))
            return {"ticket": record(ticket), "runs": [record(row) for row in runs],
                    "audit": [record(row) for row in audit]}

    @app.post("/api/tickets/{ticket_id}/investigate", dependencies=auth)
    def investigate(ticket_id: str):
        with db.serial():
            with db.Session.begin() as session:
                ticket = get_ticket(session, ticket_id)
                existing = session.scalar(select(Run).where(Run.ticket_id == ticket_id).order_by(Run.created_at.desc()))
                if existing and existing.status in {"investigating", "awaiting_approval", "interrupted"}:
                    return record(existing)
                if ticket.status == "resolved":
                    raise HTTPException(409, "This ticket is already resolved")
                run = Run(id=f"RUN-{uuid4().hex}", ticket_id=ticket_id, status="investigating", payload={})
                session.add(run)
                ticket.status = "investigating"
                session.flush()
                run_id = run.id
                db.audit(session, ticket_id, "investigation_started", detail=run_id)
            return invoke(run_id, {"run_id": run_id, "ticket_id": ticket_id, "status": "investigating"})

    @app.post("/api/runs/{run_id}/decision", dependencies=auth)
    def decision(run_id: str, body: DecisionInput):
        with db.serial():
            with db.Session.begin() as session:
                run = session.get(Run, run_id)
                if run is None:
                    raise HTTPException(404, "Investigation not found")
                if run.decision:
                    if run.decision != body.action:
                        raise HTTPException(409, "This investigation already has a different decision")
                    # Retry identical requests using the original reviewer and note.
                    if run.status not in {"interrupted", "awaiting_approval", "investigating"}:
                        return record(run)
                elif run.status != "awaiting_approval":
                    raise HTTPException(409, "This investigation is not awaiting approval")
                else:
                    run.decision = body.action
                    run.reviewer = body.reviewer
                    run.decision_note = body.note
                    db.audit(session, run.ticket_id, f"human_{body.action}", body.reviewer, body.note)
                saved = {"action": run.decision, "reviewer": run.reviewer, "note": run.decision_note}
            with workflow.graph() as graph:
                checkpoint = graph.get_state({"configurable": {"thread_id": run_id}})
                paused = any(task.interrupts for task in checkpoint.tasks)
            return invoke(run_id, Command(resume=saved) if paused else None)

    @app.post("/api/runs/{run_id}/resume", dependencies=auth)
    def resume(run_id: str):
        with db.serial():
            with db.Session() as session:
                run = session.get(Run, run_id)
                if run is None:
                    raise HTTPException(404, "Investigation not found")
                if run.status not in {"interrupted", "investigating", "awaiting_approval"}:
                    return record(run)
                saved = {"action": run.decision, "reviewer": run.reviewer, "note": run.decision_note}
                initial = {"run_id": run.id, "ticket_id": run.ticket_id, "status": "investigating"}
            config = {"configurable": {"thread_id": run_id}}
            with workflow.graph() as graph:
                state = graph.get_state(config)
                if not state.values:
                    command = initial
                elif any(task.interrupts for task in state.tasks):
                    if not saved["action"]:
                        return save_graph_state(run_id, graph, config)
                    command = Command(resume=saved)
                elif not state.next:
                    return save_graph_state(run_id, graph, config)
                else:
                    command = None
            return invoke(run_id, command)

    return app


app = create_app()
