"""Simulated commerce backend. Replace this adapter for a real POS integration.

No bank or payment gateway is contacted. Amounts use integer minor units.
"""
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select

from backend.database import Order, Payment, Refund, Run, Ticket, record


def snapshot(db, ticket_id):
    with db.Session() as session:
        ticket = session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError("Ticket not found")
        order = session.get(Order, ticket.order_id)
        payment = session.scalar(select(Payment).where(Payment.order_id == ticket.order_id))
        refund = session.scalar(select(Refund).where(Refund.payment_id == payment.id)) if payment else None
        return {"ticket": record(ticket), "order": record(order) if order else None,
                "payment": record(payment) if payment else None,
                "refund": record(refund) if refund else None}


def fingerprint(evidence):
    keys = {"order": evidence["order"], "payment": evidence["payment"], "refund": evidence["refund"]}
    return hashlib.sha256(json.dumps(keys, sort_keys=True).encode()).hexdigest()


def eligibility(evidence, logs):
    order, payment, refund = evidence["order"], evidence["payment"], evidence["refund"]
    if not order or not payment:
        return False, "The order or payment record is missing. A person must verify the transaction."
    if refund or payment["status"] == "refunded":
        return False, "A refund is already recorded. Check its reference; do not issue another refund."
    if order["status"] != "failed":
        return False, "The order is not failed. This demo's automatic refund policy does not apply."
    if payment["status"] != "captured":
        return False, "Payment is not confirmed as captured. Verify the payment before any refund."
    if payment["amount_minor"] <= 0 or payment["amount_minor"] != order["amount_minor"] or payment["currency"] != order["currency"]:
        return False, "Order and payment amounts or currencies do not match. Manual review is required."
    if not any(log["event"] == "ORDER_CREATION_FAILED" for log in logs):
        return False, "There is no order-failure log supporting this refund. Manual review is required."
    return True, "The order failed, payment was captured, amounts match, and no previous refund exists."


def execute_simulated_refund(db, state):
    """Enforce stored approval, revalidate evidence and execute idempotently."""
    run_id, ticket_id = state["run_id"], state["ticket_id"]
    with db.Session.begin() as session:
        run = session.get(Run, run_id)
        if not run or run.decision != "approve":
            return {"status": "manual_review", "message": "A stored human approval is required."}
        previous = session.scalar(select(Refund).where(Refund.run_id == run_id))
        if previous:
            return {"status": "resolved", "message": "The simulated refund was already completed.", "refund": record(previous)}

        ticket = session.get(Ticket, ticket_id)
        order = session.scalar(select(Order).where(Order.id == ticket.order_id).with_for_update())
        payment = session.scalar(select(Payment).where(Payment.order_id == order.id).with_for_update())
        previous_payment_refund = session.scalar(select(Refund).where(Refund.payment_id == payment.id)) if payment else None
        current = {"order": record(order), "payment": record(payment) if payment else None,
                   "refund": record(previous_payment_refund) if previous_payment_refund else None}
        if fingerprint(current) != state["evidence_fingerprint"]:
            db.audit(session, ticket_id, "action_blocked", detail="Evidence changed after investigation.")
            return {"status": "manual_review", "message": "Transaction data changed after investigation. Start a new investigation."}
        eligible, reason = eligibility(current, state["logs"])
        if not eligible:
            return {"status": "manual_review", "message": reason}
        if order.simulate_failure:
            db.audit(session, ticket_id, "action_failed", detail="Intentional demo gateway failure; no refund created.")
            return {"status": "action_failed", "message": "Simulated gateway failure. No refund was issued; ticket remains open for review."}
        refund = Refund(id=f"REF-{uuid4().hex[:12]}", payment_id=payment.id, run_id=run_id,
                        amount_minor=payment.amount_minor, currency=payment.currency)
        session.add(refund)
        payment.status = "refunded"
        session.flush()
        db.audit(session, ticket_id, "simulated_refund_completed", run.reviewer or "reviewer", refund.id)
        return {"status": "resolved", "message": "Simulated refund completed. No real money moved.", "refund": record(refund)}
