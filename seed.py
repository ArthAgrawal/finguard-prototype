"""
seed.py - builds the fake bank as a SQLite database (bank.db).

The bank now comes from the full data generator in data/ (22 tables, 50 customers,
90 days of history). The customer the assistant helps is the "hero" customer,
Alex Rivera (cus_000001), whose numbers are fixed so every task has a known answer.

How it works:
  1. data/generate.py builds a CLEAN bank once: data/bank_clean.db
     (rebuilt automatically if generate.py, fixtures.py or schema.sql change)
  2. build_bank() copies it to bank.db, then hides any attack text ("plants")
     in it, and records each plant in the `injections` table.

Run it:
    python seed.py          -> creates a clean bank.db
    python seed.py --show   -> creates bank.db and prints Alex's side of it
"""

import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
DB_PATH = HERE / "bank.db"
CLEAN_DB = DATA / "bank_clean.db"
GENERATOR_FILES = [DATA / "generate.py", DATA / "fixtures.py", DATA / "schema.sql"]

CUSTOMER_ID = "cus_000001"       # Alex Rivera, the signed-in customer
SEED = 42

# Which column(s) identify a row in each table, so a plant can find it.
# A plant's "id" may match any of the listed columns (e.g. an invoice by its number).
ID_COLUMNS = {
    "transactions": ["transaction_id"],
    "invoices": ["invoice_id", "invoice_number"],
    "vendors": ["vendor_id"],
    "news": ["article_id"],
    "inbox": ["email_id"],
    "crm_notes": ["note_id"],
    "payees": ["payee_id"],
    "merchants": ["merchant_id"],
    "kyc_documents": ["document_id"],
    "customers": ["customer_id"],
}


def ensure_clean_bank():
    """Build data/bank_clean.db with the generator if it is missing or out of date."""
    stale = (not CLEAN_DB.exists() or
             any(f.stat().st_mtime > CLEAN_DB.stat().st_mtime for f in GENERATOR_FILES))
    if stale:
        print("Building the clean bank with data/generate.py (a few seconds)...", file=sys.stderr)
        subprocess.run([sys.executable, str(DATA / "generate.py"), "--seed", str(SEED),
                        "--out", str(CLEAN_DB)], check=True, stdout=subprocess.DEVNULL)
    return CLEAN_DB


def build_bank(db_path=DB_PATH, plants=None, attack_id=None):
    """
    Start from a fresh copy of the clean bank, then hide attack text in it.

    plants: optional list, e.g.
        [{"table": "transactions", "id": "T007", "field": "memo", "text": "SYSTEM NOTICE: ..."}]
    attack_id: optional name of the attack (e.g. "A1"), stored with each plant.
    """
    db_path = Path(db_path)
    shutil.copyfile(ensure_clean_bank(), db_path)

    db = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for i, p in enumerate(plants or [], 1):
        table, field = p["table"], p["field"]
        if table not in ID_COLUMNS:
            raise ValueError(f"Plants can't target table '{table}'. Allowed: {', '.join(ID_COLUMNS)}")
        cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
        if field not in cols:
            raise ValueError(f"Table '{table}' has no field '{field}'")
        where = " OR ".join(f"{c} = ?" for c in ID_COLUMNS[table])
        ids = [p["id"]] * len(ID_COLUMNS[table])
        row = db.execute(f"SELECT {ID_COLUMNS[table][0]}, {field} FROM {table} WHERE {where}", ids).fetchone()
        if row is None:
            raise ValueError(f"No row '{p['id']}' in table '{table}'")
        db.execute(f"UPDATE {table} SET {field} = ? WHERE {where}", [p["text"], *ids])
        db.execute("INSERT INTO injections VALUES (?,?,?,?,?,?,?,?,?)",
                   (f"inj_{i:04d}", attack_id or "manual", table, row[0], field, row[1], p["text"],
                    p.get("goal"), now))
    db.commit()
    db.close()
    return db_path


def show_bank(db_path=DB_PATH):
    """Print a short summary of Alex's side of the bank."""
    db = sqlite3.connect(db_path)
    q = lambda sql: db.execute(sql, (CUSTOMER_ID,)).fetchall()
    print("\n== Alex Rivera's accounts ==")
    for r in q("SELECT account_id, account_type, current_balance FROM accounts WHERE customer_id = ?"):
        print("  ", r)
    print("\n== Payees ==")
    for r in q("SELECT payee_name, account_number FROM payees WHERE customer_id = ?"):
        print("  ", r)
    print("\n== 8 most recent transactions (checking) ==")
    for r in q("SELECT transaction_id, substr(authorized_at,1,10), direction, amount, "
               "COALESCE(merchant_descriptor, counterparty_name, description), memo FROM transactions "
               "WHERE account_id IN (SELECT account_id FROM accounts WHERE customer_id = ? "
               "AND account_type = 'checking') ORDER BY authorized_at DESC LIMIT 8"):
        print("  ", r)
    print("\n== Unpaid bills ==")
    for r in q("SELECT invoice_number, total_amount, due_date, status, notes FROM invoices "
               "WHERE customer_id = ? AND status IN ('open','overdue')"):
        print("  ", r)
    planted = db.execute("SELECT attack_id, table_name, row_id, column_name FROM injections").fetchall()
    print(f"\n== Planted attack text: {planted or 'none (clean bank)'}")
    db.close()


if __name__ == "__main__":
    path = build_bank()
    print(f"Created {path.name} from {CLEAN_DB.relative_to(HERE)}")
    if "--show" in sys.argv:
        show_bank(path)
