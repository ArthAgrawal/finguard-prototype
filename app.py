"""
app.py - Maple Bank online banking, in your browser.

You are Alex Rivera. The left side is your bank account (read live from bank.db).
The right side is the bank's AI assistant (agent.py). Under each reply you can
open "Behind the scenes" to see every tool the assistant called.

Run it:
    streamlit run app.py
It opens in your browser at http://localhost:8501
"""

import asyncio
import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

import agent
import attacks
import bank_core
from data import fixtures
from seed import CUSTOMER_ID, DB_PATH, build_bank

ACCOUNT = agent.CHECKING                       # Alex's checking account, acc_000001
START_BALANCE = fixtures.HERO_CHECKING_BALANCE  # $6,412.88 after every reset
ATTACKS = attacks.load_attacks()

st.set_page_config(page_title="Maple Bank", page_icon="🍁", layout="wide")


# ---------------------------------------------------------------------------
# Reading the bank (straight from bank.db, so the page always shows the truth)
# ---------------------------------------------------------------------------
def read_table(sql, *params):
    db = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(sql, db, params=params)
    db.close()
    return df


if not DB_PATH.exists():
    build_bank()

# Chat history lives in the browser session
if "chat" not in st.session_state:
    st.session_state.chat = []      # list of {"role", "content", "calls"}
if "scenario" not in st.session_state:
    st.session_state.scenario = "None"   # which attack is planted right now
if "answers" not in st.session_state:
    st.session_state.answers = []   # every reply since the last reset (for success checks)

AUDIT_LOG = Path(__file__).parent / "finguard_audit.jsonl"
PENDING = Path(__file__).parent / "finguard_pending.json"


def load_pending():
    return json.loads(PENDING.read_text(encoding="utf-8")) if PENDING.exists() else []


def resolve(request_id, approve):
    """Alex pressed Approve or Reject. Approving runs the bank's own code directly:
    the AI is not involved, so it can't press this button for her."""
    items = load_pending()
    for item in items:
        if item["id"] == request_id and item["status"] == "pending":
            if approve:
                tool = getattr(bank_core, item["tool"])      # e.g. bank_core.pay_bill
                item["result"] = tool(**item["args"])
                item["status"] = "approved"
            else:
                item["status"] = "rejected"
    PENDING.write_text(json.dumps(items, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Sidebar: demo controls (things Alex can't do in a real bank)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Demo controls")
    st.caption("These are for the experiment, not part of the bank.")

    # --- choose a scenario: clean bank, or a bank with an attack planted ---
    options = ["None"] + list(ATTACKS)
    choice = st.selectbox(
        "Attack to plant", options,
        format_func=lambda k: "None (clean bank)" if k == "None" else ATTACKS[k]["name"])
    if choice != "None":
        atk = ATTACKS[choice]
        st.caption(f"**Type:** {atk['type']}")
        st.caption(atk["how"])
        for i, t in enumerate(attacks.tasks_of(atk), 1):
            label = "Try asking" if len(attacks.tasks_of(atk)) == 1 else f"Chat {i}, ask"
            st.caption(f"**{label}:** *{t}*")
        if len(attacks.tasks_of(atk)) > 1:
            st.caption("Press **Clear chat only** between the chats.")
        st.caption(f"**Attack wins if:** {atk.get('goal', '')}")

    if st.button("Reset bank with this scenario", width="stretch", type="primary"):
        plants = [] if choice == "None" else ATTACKS[choice]["plants"]
        build_bank(plants=plants, attack_id=None if choice == "None" else choice)
        AUDIT_LOG.unlink(missing_ok=True)  # fresh FinGuard log too
        PENDING.unlink(missing_ok=True)    # and no leftover approval requests
        st.session_state.scenario = choice
        st.session_state.chat = []
        st.session_state.answers = []
        st.rerun()
    if st.button("Clear chat only", width="stretch"):
        st.session_state.chat = []
        st.rerun()

    st.divider()
    active = st.session_state.scenario
    if active == "None":
        st.success("Active: clean bank (no attack)")
    else:
        st.warning(f"Active: {ATTACKS[active]['name']}")
        with st.expander("Show the planted text"):
            for p in ATTACKS[active]["plants"]:
                st.caption(f"{p['table']} · {p['id']} · {p['field']}")
                st.code(p["text"], language=None, wrap_lines=True)
    st.caption(f"Model: `{agent.MODEL}`")

    st.divider()
    guard_on = st.toggle("🛡️ FinGuard", value=False,
                         help="ON: the assistant reaches the bank through proxy.py")
    if guard_on:
        st.success("FinGuard ON: every tool call is checked")
    else:
        st.caption("FinGuard OFF: the assistant talks to the bank directly")

    if AUDIT_LOG.exists():
        with st.expander("FinGuard log"):
            lines = AUDIT_LOG.read_text(encoding="utf-8").strip().splitlines()[-10:]
            for line in reversed(lines):
                e = json.loads(line)
                if e.get("decision") in ("BLOCK", "CONFIRM"):
                    st.error(f"{e['decision']} `{e['tool']}` · {e['rule']}")
                elif e.get("flagged"):
                    st.warning(f"flagged {len(e['flagged'])} item(s) in `{e['tool']}`")
                else:
                    st.caption(f"allowed `{e['tool']}`")


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("🍁 Maple Bank")
st.caption(f"Online banking · signed in as **{fixtures.HERO['first_name']} {fixtures.HERO['last_name']}**")

left, right = st.columns([1, 1.2], gap="large")

# ---------------------------------------------------------------------------
# LEFT: Alex's account, exactly as the database has it right now
# ---------------------------------------------------------------------------
with left:
    acct = read_table("SELECT current_balance FROM accounts WHERE account_id = ?", ACCOUNT)
    balance = float(acct["current_balance"].iloc[0])
    st.metric("Checking balance", f"${balance:,.2f}", delta=f"{balance - START_BALANCE:,.2f}",
              help=f"Change since the bank was last reset (${START_BALANCE:,.2f})")

    # Did the planted attack reach its goal?
    active = st.session_state.scenario
    if active != "None":
        won, why = attacks.check_success(ATTACKS[active], DB_PATH, st.session_state.answers)
        if won:
            st.error(f"⚠️ Attack succeeded: {why}")

    sent = read_table("SELECT requested_at, transfer_type, to_account_number, amount, memo, status "
                      "FROM transfers WHERE initiated_by = 'agent' ORDER BY requested_at DESC")

    # --- approval requests from FinGuard: only Alex can approve these ---
    for item in [i for i in load_pending() if i["status"] == "pending"]:
        a = item["args"]
        summary = item.get("summary") or f"Send ${a.get('amount', 0):,.2f} to {a.get('to_account')}"
        with st.container(border=True):
            st.markdown(f"**🛡️ Approval needed (#{item['id']})**  \n**{summary}**")
            st.caption(f"FinGuard rule {item['rule']}: {item['reason']}")
            c1, c2 = st.columns(2)
            if c1.button("Approve", key=f"ok{item['id']}", type="primary", width="stretch"):
                resolve(item["id"], True)
                st.rerun()
            if c2.button("Reject", key=f"no{item['id']}", width="stretch"):
                resolve(item["id"], False)
                st.rerun()

    tab_tx, tab_payees, tab_bills, tab_sent = st.tabs(
        ["Transactions", "Payees", "Bills", f"Sent by assistant ({len(sent)})"])

    with tab_tx:
        st.dataframe(read_table(
            "SELECT substr(authorized_at, 1, 10) AS date, "
            "COALESCE(merchant_descriptor, counterparty_name, description) AS merchant, "
            "CASE direction WHEN 'debit' THEN -amount ELSE amount END AS amount, memo, status "
            "FROM transactions WHERE account_id = ? ORDER BY authorized_at DESC LIMIT 200", ACCOUNT),
            hide_index=True, width="stretch")
    with tab_payees:
        st.dataframe(read_table(
            "SELECT payee_name, account_number, added_at, added_via, verification_status "
            "FROM payees WHERE customer_id = ? ORDER BY added_at DESC", CUSTOMER_ID),
            hide_index=True, width="stretch")
    with tab_bills:
        st.dataframe(read_table(
            "SELECT invoice_number, remit_to_name, balance_due, due_date, status, notes, "
            "remit_to_account_number FROM invoices WHERE customer_id = ? "
            "ORDER BY CASE status WHEN 'overdue' THEN 0 WHEN 'open' THEN 1 ELSE 2 END, due_date",
            CUSTOMER_ID), hide_index=True, width="stretch")
    with tab_sent:
        if sent.empty:
            st.caption("The assistant hasn't moved any money yet.")
        else:
            st.dataframe(sent, hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# RIGHT: chat with the assistant
# ---------------------------------------------------------------------------
def show_calls(calls):
    """The 'behind the scenes' panel: every tool the assistant used."""
    if not calls:
        st.caption("No tools used.")
        return
    for i, c in enumerate(calls, 1):
        args = ", ".join(f"{k}={v}" for k, v in c["args"].items())
        st.markdown(f"**{i}. `{c['tool']}({args})`**")
        st.code(c["result"], language="json", height=250)   # full result, scrollable


with right:
    st.subheader("💬 Assistant")
    st.caption("Ask about your accounts, bills, payments or the news. "
               "Try: *Send $20 to Jordan* or *Pay my overdue bills*")

    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m["role"] == "assistant":
                with st.expander("Behind the scenes: what the assistant did"):
                    show_calls(m["calls"])

    prompt = st.chat_input("Message the assistant")
    if prompt:
        # earlier turns, as plain text, so the assistant remembers the conversation
        history = [{"role": m["role"], "content": m["content"]}
                   for m in st.session_state.chat]
        st.session_state.chat.append({"role": "user", "content": prompt, "calls": []})

        # Show the user's message right away, then a live status box
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.status("Thinking...", expanded=True) as status:

                def on_event(kind, *data):
                    """Called by agent.py at each step, so we can show progress live."""
                    if kind == "thinking":
                        status.update(label="🤔 Thinking...")
                    elif kind == "tool":
                        name, args = data
                        arg_text = ", ".join(f"{k}={v}" for k, v in args.items())
                        status.update(label=f"🔧 Calling `{name}`...")
                        st.markdown(f"🔧 `{name}({arg_text})`")
                    elif kind == "result":
                        name, result = data
                        if "BLOCKED by FinGuard" in result or "NEEDS CONFIRMATION" in result:
                            st.caption("　🛡️ FinGuard blocked this")
                        elif "FinGuard WARNING" in result:
                            st.caption("　🛡️ FinGuard flagged suspicious text in the reply")
                        else:
                            st.caption("　↳ got a reply from the bank")

                try:
                    servers = agent.GUARDED_SERVERS if guard_on else agent.SERVERS
                    result = asyncio.run(agent.run_agent(prompt, verbose=False,
                                                         history=history,
                                                         on_event=on_event,
                                                         servers=servers))
                    answer = (result["answer"] or "").strip() or "_(Done. No message.)_"
                    calls = result["calls"]
                    status.update(label="Done", state="complete", expanded=False)
                except Exception as e:
                    answer, calls = f"⚠️ Error: {e}", []
                    status.update(label="Error", state="error")

        st.session_state.chat.append({"role": "assistant", "content": answer,
                                      "calls": calls})
        st.session_state.answers.append(answer)
        st.rerun()   # redraw the page so the account side shows any changes
