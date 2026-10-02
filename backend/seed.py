"""Insert missing fictional fixtures without resetting existing user work."""
from backend.database import EventLog, Order, Payment, Refund, Ticket

CASES = [
    ("1001", "failed", "captured", "Payment deducted but order failed", "ORDER_CREATION_FAILED", False),
    ("1002", "delivered", "captured", "Delivered order refund request", "ORDER_DELIVERED", False),
    ("1003", "failed", "refunded", "Check whether my refund was processed", "REFUND_COMPLETED", False),
    ("1004", "failed", "pending", "Payment is still processing", "PAYMENT_PENDING", False),
    ("1005", "failed", None, "Cannot find my payment confirmation", "PAYMENT_RECORD_MISSING", False),
    ("1006", "failed", "captured", "Payment deducted; test action failure", "ORDER_CREATION_FAILED", True),
]


def seed(db):
    with db.serial(), db.Session.begin() as session:
        for suffix, order_status, payment_status, subject, event, failure in CASES:
            oid, pid, tid = f"ORD-{suffix}", f"PAY-{suffix}", f"TKT-{suffix}"
            if session.get(Order, oid) is not None:
                continue
            session.add(Order(id=oid, customer=f"Demo customer {suffix[-1]}", status=order_status,
                              amount_minor=250000, currency="PKR", item="Pakistani pantry essentials",
                              simulate_failure=failure))
            session.flush()
            if payment_status:
                session.add(Payment(id=pid, order_id=oid, status=payment_status,
                                    amount_minor=250000, currency="PKR"))
                session.flush()
            session.add(Ticket(id=tid, order_id=oid, subject=subject,
                               description=f"Fictional demo case: {subject}. Please investigate my order.",
                               priority="high" if suffix in {"1001", "1006"} else "medium", status="open"))
            session.add(EventLog(id=f"LOG-{suffix}", order_id=oid, event=event,
                                 message=f"Demo event {event} recorded for {oid}."))
            if payment_status == "refunded":
                session.add(Refund(id=f"REF-{suffix}", payment_id=pid, run_id=f"seed-{suffix}",
                                   amount_minor=250000, currency="PKR"))
            db.audit(session, tid, "ticket_created", "demo_seed", subject)
