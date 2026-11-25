"""
bank_core.py - Maple Bank's MCP server.

It works just like your weather server, except the tools read and change
bank.db instead of calling a weather API.

Run it directly (it will sit and wait for a client):
    python bank_core.py
Usually you won't run it yourself: try_bank.py, and later agent.py and
proxy.py, start it automatically.
"""

import sqlite3
from pathlib import Path
from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).parent / "bank.db"

mcp = FastMCP("bank-core", log_level="WARNING")   # hide routine INFO logs


# --- small helpers so each tool doesn't repeat database code ---------------
def query(sql, *params):
    """Run a SELECT and return the rows as a list of dicts."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute(sql, params).fetchall()]
    db.close()
    return rows


def execute(sql, *params):
    """Run an INSERT/UPDATE and save it."""
    db = sqlite3.connect(DB_PATH)
    db.execute(sql, params)
    db.commit()
    db.close()


# --- the tools the AI can use -----------------------------------------------
# The docstring under each function becomes the tool's DESCRIPTION.
# The AI reads these descriptions to decide which tool to call.

@mcp.tool()
def get_balance(account_id: str) -> dict:
    """Returns the current balance for a bank account."""
    rows = query("SELECT account_id, owner, balance FROM accounts WHERE account_id = ?",
                 account_id)
    return rows[0] if rows else {"error": f"No account {account_id}"}


@mcp.tool()
def list_transactions(account_id: str, limit: int = 20) -> list[dict]:
    """Lists recent transactions for an account, including merchant and memo."""
    return query(
        "SELECT txn_id, date, amount, merchant, memo FROM transactions "
        "WHERE account_id = ? ORDER BY date DESC LIMIT ?",
        account_id, limit)


@mcp.tool()
def list_payees(account_id: str) -> list[dict]:
    """Lists the saved payees (people or companies) this account can send money to."""
    return query("SELECT name, account_number, added_at FROM payees WHERE owner_account = ?",
                 account_id)


@mcp.tool()
def list_bills(account_id: str) -> list[dict]:
    """Lists bills for an account, with amount, due date, status and the biller's note."""
    return query(
        "SELECT bill_id, payee_name, payee_account, amount, due_date, status, note "
        "FROM bills WHERE account_id = ?",
        account_id)


@mcp.tool()
def add_payee(account_id: str, payee_name: str, payee_account: str) -> str:
    """Adds a new payee so that money can be sent to them."""
    execute("INSERT INTO payees VALUES (?, ?, ?, datetime('now'))",
            account_id, payee_name, payee_account)
    return f"Payee '{payee_name}' ({payee_account}) added."


@mcp.tool()
def transfer_funds(from_account: str, to_account: str, amount: float) -> str:
    """Transfers money from an account to one of its saved payees."""
    # Like a real bank, you can only pay someone on your payee list.
    # (That's why an attack has to call add_payee first.)
    if not query("SELECT 1 FROM payees WHERE owner_account = ? AND account_number = ?",
                 from_account, to_account):
        return f"Error: {to_account} is not a saved payee. Add them with add_payee first."

    acct = query("SELECT balance FROM accounts WHERE account_id = ?", from_account)
    if not acct:
        return f"Error: no account {from_account}"
    if acct[0]["balance"] < amount:
        return "Error: insufficient funds"

    # NOTE: on purpose, there is NO amount limit and NO confirmation step.
    # That "too much power" is a weakness the scanner should flag later.
    execute("UPDATE accounts SET balance = balance - ? WHERE account_id = ?",
            amount, from_account)
    execute("INSERT INTO transfers_log (from_account, to_account, amount) VALUES (?, ?, ?)",
            from_account, to_account, amount)
    # If this payment matches an unpaid bill, mark the bill as paid
    execute("UPDATE bills SET status = 'paid' WHERE account_id = ? AND payee_account = ? "
            "AND amount = ? AND status = 'unpaid'",
            from_account, to_account, amount)
    return f"Transferred ${amount:.2f} from {from_account} to {to_account}."


if __name__ == "__main__":
    mcp.run()   # stdio: talks through standard input/output, like your weather server
