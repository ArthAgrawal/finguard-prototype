"""
run_attacks.py - the experiment: run every attack with FinGuard OFF and ON,
and measure the Attack Success Rate (ASR).

For each attack and each setting it:
  1. resets the bank and plants the attack text
  2. runs each chat in try_asking (a fresh agent each time, like a new chat)
  3. checks the attack's `success` rule (attacks.py)

Run it (Ollama must be running):
    python run_attacks.py                 all attacks, guard off and on
    python run_attacks.py A1 A4           only these attacks
    python run_attacks.py --guard-only    only with FinGuard on
    python run_attacks.py --clean         also run every task on a CLEAN bank,
                                          to check the guard doesn't break normal use

Results are printed as a table and saved to results/run_<time>.json.
Small models are not fully repeatable, so run it a few times before trusting a number.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import agent
import attacks
from seed import DB_PATH, build_bank

HERE = Path(__file__).parent
AUDIT_LOG = HERE / "finguard_audit.jsonl"
PENDING = HERE / "finguard_pending.json"


def reset(plants, attack_id):
    build_bank(plants=plants, attack_id=attack_id)
    AUDIT_LOG.unlink(missing_ok=True)
    PENDING.unlink(missing_ok=True)


def guard_actions():
    """What FinGuard did during the run (from its audit log)."""
    if not AUDIT_LOG.exists():
        return {"blocked": 0, "confirm": 0, "flagged": 0}
    events = [json.loads(l) for l in AUDIT_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {"blocked": sum(e.get("decision") == "BLOCK" for e in events),
            "confirm": sum(e.get("decision") == "CONFIRM" for e in events),
            "flagged": sum(len(e.get("flagged") or []) for e in events)}


async def run_one(attack_id, attack, guard, clean=False):
    reset([] if clean else attack["plants"], None if clean else attack_id)
    servers = agent.GUARDED_SERVERS if guard else agent.SERVERS
    answers, calls = [], []
    for task in attacks.tasks_of(attack):
        try:
            r = await agent.run_agent(task, servers=servers, verbose=False)
            answers.append(r["answer"] or "")
            calls += r["calls"]
        except Exception as e:                       # one broken run shouldn't stop the batch
            answers.append(f"ERROR: {e}")
    won, why = attacks.check_success(attack, DB_PATH, answers)
    return {"attack": attack_id, "guard": guard, "clean_bank": clean, "success": won, "why": why,
            "tools_used": [c["tool"] for c in calls], "guard_actions": guard_actions() if guard else None,
            "expect_guard": attack.get("expect_guard"), "answers": answers}


async def main():
    args = sys.argv[1:]
    all_attacks = attacks.load_attacks()
    chosen = [a for a in args if not a.startswith("--")] or list(all_attacks)
    settings = [True] if "--guard-only" in args else [False, True]

    results = []
    for aid in chosen:
        for guard in settings:
            label = f"{aid:<10} guard {'ON ' if guard else 'OFF'}"
            print(f"{label} ...", end=" ", flush=True)
            r = await run_one(aid, all_attacks[aid], guard)
            results.append(r)
            print("ATTACK WORKED" if r["success"] else "attack failed", f"({r['why']})")
            if "--clean" in args and guard:
                c = await run_one(aid, all_attacks[aid], guard, clean=True)
                results.append(c)
                print(f"{'':<10} clean bank, guard ON: tools used {c['tools_used']}")

    print("\n== Attack Success Rate (lower is better for FinGuard) ==")
    for guard in settings:
        rows = [r for r in results if r["guard"] == guard and not r["clean_bank"]]
        wins = sum(r["success"] for r in rows)
        print(f"  FinGuard {'ON ' if guard else 'OFF'}: {wins}/{len(rows)} attacks worked "
              f"= {wins / max(len(rows), 1):.0%}")

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    path = out / f"run_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps({"model": agent.MODEL, "results": results}, indent=2), encoding="utf-8")
    print(f"\nSaved {path.relative_to(HERE)}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
