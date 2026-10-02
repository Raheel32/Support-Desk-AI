"""Streamlit dashboard. All business records and actions live in the API."""
import os
import secrets

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Support Desk AI", page_icon="🟢", layout="wide")


def setting(name, default=""):
    value = os.getenv(name)
    if value is not None:
        return value
    try:
        return str(st.secrets.get(name, default))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default


st.markdown("""
<style>
.stApp {background:#f5f7f6;}
.block-container {max-width:1280px;padding-top:2.1rem;padding-bottom:3rem;}
h1,h2,h3 {letter-spacing:-.035em;}
[data-testid="stMetric"] {background:white;padding:20px;border:1px solid #e0e8e3;border-radius:14px;}
[data-testid="stSidebar"] {background:#edf2ef;}
[data-testid="stForm"] {background:white;border-radius:14px;}
.eyebrow {color:#267454;font-size:12px;letter-spacing:.15em;font-weight:700;margin-bottom:8px;}
.intro {color:#596b61;font-size:17px;max-width:760px;}
</style>
""", unsafe_allow_html=True)

password = setting("APP_PASSWORD")
api_key = setting("BACKEND_API_KEY")
api_url = setting("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

if not password or not api_key:
    st.title("Support Desk AI")
    st.info("Finish setup by adding APP_PASSWORD and BACKEND_API_KEY to your Streamlit secrets. See docs/ONLINE_SETUP.md.")
    st.stop()

if not st.session_state.get("authenticated"):
    left, center, right = st.columns([1, 2, 1])
    with center:
        st.markdown('<div class="eyebrow">SUPPORT OPERATIONS</div>', unsafe_allow_html=True)
        st.title("A clearer path to resolution.")
        st.write("Investigate a ticket, review the evidence, and approve the next step.")
        with st.form("login"):
            entered = st.text_input("Workspace password", type="password")
            submitted = st.form_submit_button("Open workspace", type="primary", width="stretch")
        if submitted:
            if secrets.compare_digest(entered.encode(), password.encode()):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("The workspace password is incorrect.")
        st.caption("Learning demo · Fictional records · Simulated refunds only")
    st.stop()


def api(method, path, **kwargs):
    try:
        response = httpx.request(method, f"{api_url}{path}", headers={"X-API-Key": api_key},
                                 timeout=httpx.Timeout(90, connect=10), **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", "Request failed")
            except ValueError:
                detail = "Backend returned an unexpected response"
            st.error(f"Request failed ({response.status_code}): {detail}")
            st.stop()
        return response.json()
    except httpx.TimeoutException:
        st.warning("The backend did not respond in time. A sleeping host may be starting. Refresh to check the saved result before repeating an action.")
        st.stop()
    except (httpx.HTTPError, ValueError):
        st.error("Cannot reach the backend. Check API_BASE_URL and the backend service status, then refresh.")
        st.stop()


def money(minor, currency="PKR"):
    return f"{currency} {minor / 100:,.2f}"


def label(value):
    return value.replace("_", " ").title()


with st.sidebar:
    st.markdown("### Support Desk AI")
    st.caption("INVESTIGATE · REVIEW · RESOLVE")
    page = st.radio("Workspace", ["Overview", "Ticket workspace", "Create ticket", "How it works"], key="page")
    st.divider()
    st.caption("All records are fictional. Refunds update demo records only.")
    if st.button("Refresh records", width="stretch"):
        st.rerun()
    if st.button("Sign out", width="stretch"):
        st.session_state.clear()
        st.rerun()

config = api("GET", "/api/config")
tickets = api("GET", "/api/tickets")
st.markdown('<div class="eyebrow">SUPPORT DESK / WORKSPACE</div>', unsafe_allow_html=True)

if page == "Overview":
    st.title("Every case. A clear next step.")
    st.markdown('<p class="intro">Review evidence before taking action. Your approval stays at the center of every refund.</p>', unsafe_allow_html=True)
    st.caption(f"Explanation mode: {label(config['ai_mode'])} · Simulated commerce backend")
    columns = st.columns(4)
    metrics = [("Total tickets", len(tickets)), ("Awaiting approval", sum(t["status"] == "awaiting_approval" for t in tickets)),
               ("Resolved", sum(t["status"] == "resolved" for t in tickets)),
               ("Manual review", sum(t["status"] == "manual_review" for t in tickets))]
    for column, (title, value) in zip(columns, metrics):
        column.metric(title, value)
    st.subheader("Start with a sample case")
    st.write("Open Ticket workspace and select TKT-1001 to investigate a captured payment on a failed order. Review the proposal, then approve or reject it.")
    st.dataframe([{ "Ticket": t["id"], "Subject": t["subject"], "Priority": label(t["priority"]),
                    "Status": label(t["status"]), "Order": t["order_id"]} for t in tickets], hide_index=True, width="stretch")
    with st.expander("What do the sample cases demonstrate?"):
        st.table([
            {"Ticket": "TKT-1001", "Scenario": "Eligible simulated refund; approval required"},
            {"Ticket": "TKT-1002", "Scenario": "Delivered order; manual review"},
            {"Ticket": "TKT-1003", "Scenario": "Already refunded; no duplicate refund"},
            {"Ticket": "TKT-1004", "Scenario": "Pending payment; manual review"},
            {"Ticket": "TKT-1005", "Scenario": "Missing payment record; manual review"},
            {"Ticket": "TKT-1006", "Scenario": "Eligible proposal, but simulated execution fails"},
        ])

elif page == "Create ticket":
    st.title("Create a support ticket")
    st.write("Link the complaint to an existing fictional order so the investigation can find its records.")
    orders = api("GET", "/api/orders")
    with st.form("new_ticket", clear_on_submit=True):
        order = st.selectbox("Related order", [o["id"] for o in orders])
        subject = st.text_input("Subject", max_chars=200)
        description = st.text_area("What happened?", max_chars=4000)
        priority = st.selectbox("Priority", ["medium", "low", "high", "urgent"])
        create = st.form_submit_button("Create ticket", type="primary")
    if create:
        if len(subject.strip()) < 5 or len(description.strip()) < 10:
            st.error("Use at least 5 characters for the subject and 10 for the description.")
        else:
            created = api("POST", "/api/tickets", json={"order_id": order, "subject": subject,
                          "description": description, "priority": priority})
            st.success(f"Created {created['id']}. Open Ticket workspace to investigate it.")

elif page == "Ticket workspace":
    st.title("Investigate with evidence")
    filter_col, search_col = st.columns([1, 2])
    statuses = ["All"] + sorted({t["status"] for t in tickets})
    status = filter_col.selectbox("Status", statuses, format_func=label)
    query = search_col.text_input("Search tickets", placeholder="Ticket ID, subject, or order ID")
    filtered = [t for t in tickets if (status == "All" or t["status"] == status)
                and query.lower() in f"{t['id']} {t['subject']} {t['order_id']}".lower()]
    if not filtered:
        st.info("No matching tickets. Change the filters or create a ticket.")
        st.stop()
    filtered = sorted(filtered, key=lambda t: t["id"])
    lookup = {t["id"]: t for t in filtered}
    tid = st.selectbox("Choose a ticket", list(lookup), format_func=lambda key: f"{key} · {lookup[key]['subject']}")
    detail = api("GET", f"/api/tickets/{tid}")
    ticket = detail["ticket"]
    st.subheader(ticket["subject"])
    st.write(ticket["description"])
    st.caption(f"{ticket['id']} · {ticket['order_id']} · {label(ticket['priority'])} priority · {label(ticket['status'])}")
    latest = detail["runs"][0] if detail["runs"] else None
    pending = latest and latest["status"] in {"awaiting_approval", "investigating", "interrupted"}
    col1, col2 = st.columns([1, 2])
    if col1.button("Investigate ticket", type="primary", disabled=bool(pending) or ticket["status"] == "resolved"):
        with st.spinner("Reading transaction records and preparing findings…"):
            api("POST", f"/api/tickets/{tid}/investigate")
        st.rerun()
    if latest and latest["status"] in {"interrupted", "investigating"}:
        if col2.button("Resume saved workflow"):
            with st.spinner("Recovering saved progress…"):
                api("POST", f"/api/runs/{latest['id']}/resume")
            st.rerun()
    investigation_tab, evidence_tab, history_tab = st.tabs(["Investigation", "Evidence", "History"])
    with investigation_tab:
        if latest:
            state = latest["payload"]
            st.write(f"**Investigation status:** {label(latest['status'])}")
            plan = state.get("plan", {})
            if plan:
                st.markdown(f"**Proposed action:** {label(plan['action'])}")
                st.write(plan["reason"])
                if plan["requires_approval"]:
                    st.metric("Proposed simulated refund", money(plan["amount_minor"], plan["currency"]))
                if state.get("explanation_mode") == "gemini":
                    with st.expander("AI explanation", expanded=True):
                        st.write(state["explanation"])
                        st.caption("AI-generated explanation. Check the evidence and policy finding above.")
                if state.get("provider_warning"):
                    st.warning(state["provider_warning"])
            for step in state.get("steps", []):
                st.caption(step)
            if latest["status"] == "awaiting_approval":
                with st.form(f"decision_{latest['id']}"):
                    st.write("Review the evidence before making your decision.")
                    reviewer = st.text_input("Reviewer name", max_chars=100)
                    note = st.text_area("Decision note", max_chars=1000)
                    confirmed = st.checkbox("I reviewed the evidence and the proposed amount.")
                    approve_col, reject_col = st.columns(2)
                    approve = approve_col.form_submit_button("Approve simulated refund", type="primary")
                    reject = reject_col.form_submit_button("Reject proposal")
                if approve or reject:
                    if len(reviewer.strip()) < 2:
                        st.error("Enter a reviewer name with at least 2 characters.")
                    elif approve and not confirmed:
                        st.error("Review the evidence and check the confirmation before approving.")
                    else:
                        with st.spinner("Saving decision…"):
                            api("POST", f"/api/runs/{latest['id']}/decision", json={
                                "action": "approve" if approve else "reject", "reviewer": reviewer, "note": note})
                        st.rerun()
            result = state.get("result")
            if result:
                (st.success if result["status"] == "resolved" else st.warning)(result["message"])
                if result.get("refund"):
                    st.code(result["refund"]["id"], language=None)
            if latest["status"] == "rejected":
                st.info("Proposal rejected. No refund was issued. The ticket remains available for manual review.")
        else:
            st.info("Start an investigation to collect evidence and prepare a proposal.")
    with evidence_tab:
        if latest and latest["payload"].get("evidence"):
            state = latest["payload"]
            st.caption("Snapshot captured at investigation time. The backend checks it again before execution.")
            evidence = state["evidence"]
            left, right = st.columns(2)
            with left:
                st.write("**Order record**")
                st.json(evidence["order"])
            with right:
                st.write("**Payment record**")
                st.json(evidence["payment"])
            st.write("**Prior refund**")
            st.json(evidence["refund"] or {"message": "No prior refund found"})
            st.write("**Transaction logs**")
            st.dataframe(state.get("logs", []), hide_index=True, width="stretch")
        else:
            st.info("Evidence will appear after investigation.")
    with history_tab:
        st.write("**Activity history**")
        st.dataframe(detail["audit"], hide_index=True, width="stretch")
        for run in detail["runs"]:
            with st.expander(f"{label(run['status'])} · {run['created_at']}"):
                st.write(f"Reviewer: {run['reviewer'] or 'Not yet reviewed'}")
                st.write(run["decision_note"] or "No decision note")
                st.json(run["payload"])

else:
    st.title("Understand the workflow")
    st.write("A ticket points to an order. The database analyst reads its payment and refund records, then the log analyst reads transaction events. A supervisor applies the demo policy and optionally asks Gemini to explain the evidence.")
    st.write("Eligible proposals pause in LangGraph until a person approves or rejects them. Approval resumes the saved workflow. The commerce adapter rechecks the records and creates one simulated refund. A ticket is resolved only after success.")
    st.info("Rules mode uses deterministic Python logic. Gemini mode adds an AI explanation; it cannot change the amount, policy decision, or approval requirement.")
    st.write("The dashboard talks to FastAPI. FastAPI stores business records and workflow checkpoints in PostgreSQL when hosted, or SQLite for a quick local demo.")
    st.caption("This is a single-workspace educational demo with a shared password and a self-reported reviewer name. Production use needs individual accounts, authorization, and a real POS adapter.")
