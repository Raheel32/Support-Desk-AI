from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Support Desk AI",
    description="A learning demo for investigating support tickets.",
    version="0.1.0",
)

# Fictional data for learning. This is not connected to your POS.
tickets = {
    "TKT-1001": {
        "id": "TKT-1001",
        "subject": "Payment deducted but order failed",
        "description": (
            "I paid PKR 2,500, but my order shows as failed. "
            "Please check what happened."
        ),
        "customer_id": "CUS-1001",
        "order_id": "ORD-1001",
        "status": "open",
        "priority": "high",
    }
}


@app.get("/")
def home():
    return {"message": "Welcome to Support Desk AI"}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Support Desk AI"}


@app.get("/tickets")
def list_tickets():
    return list(tickets.values())


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    ticket = tickets.get(ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    return ticket