"""Demo business records and a separate durable investigation ledger."""
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import RLock

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.config import sqlalchemy_url


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "demo_orders"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    customer: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    item: Mapped[str] = mapped_column(String(200))
    simulate_failure: Mapped[bool] = mapped_column(default=False)


class Payment(Base):
    __tablename__ = "demo_payments"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("demo_orders.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="PKR")


class Ticket(Base):
    __tablename__ = "support_tickets"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("demo_orders.id"))
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class EventLog(Base):
    __tablename__ = "demo_logs"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("demo_orders.id"))
    event: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class Run(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"))
    status: Mapped[str] = mapped_column(String(40), default="investigating")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), default=now)
    updated_at: Mapped[str] = mapped_column(String(50), default=now)


class Refund(Base):
    __tablename__ = "simulated_refunds"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    payment_id: Mapped[str] = mapped_column(ForeignKey("demo_payments.id"), unique=True)
    run_id: Mapped[str] = mapped_column(String(50), unique=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[str] = mapped_column(String(50), default=now)


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(50), index=True)
    event: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(50), default=now)


def record(obj):
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


class Database:
    def __init__(self, url):
        url = sqlalchemy_url(url)
        args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, pool_pre_ping=True, connect_args=args)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)
        self.local_lock = RLock()

    def setup(self):
        Base.metadata.create_all(self.engine)

    @contextmanager
    def serial(self):
        """Serialize demo mutations across threads and PostgreSQL processes.

        A transaction-scoped advisory lock releases even if a process crashes.
        The demo uses one global lock for simplicity; production needs per-case locks.
        """
        with self.local_lock:
            if self.engine.dialect.name == "postgresql":
                with self.engine.begin() as connection:
                    connection.execute(text("SELECT pg_advisory_xact_lock(81422026)"))
                    yield
            else:
                yield

    def audit(self, session, ticket_id, event, actor="system", detail=""):
        session.add(Audit(ticket_id=ticket_id, event=event, actor=actor, detail=detail))
