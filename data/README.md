# FinGuard fake bank data

Everything here is synthetic. Card numbers use public test prefixes, SSNs use the never-issued
9xx range, phone numbers use 555-01xx, and emails use example.com / .org / .net.

## Three sizes, one script

| Preset | Command | What you get | Use it for |
| --- | --- | --- | --- |
| `dev` (default) | `uv run python generate.py` | `bank.db`: 50 customers, 90 days, ~7,400 transactions, ~5 MB | MCP servers and agent runs while building |
| `test` | `uv run python generate.py --preset test` | `test/bank_test.db` + `test/csv/*.csv`: at most 1,000 rows per table | Unit tests, scanner/guard tests, looking at the data in Excel |
| `full` | `uv run python generate.py --preset full` | `full/bank_full.db`: 10,000 customers, 365 days, millions of transactions | Scale and latency tests, realistic volumes |

Same seed in, same data out: `--seed 42` is the default, so all six of us get identical files.

Override any preset: `--customers 2000 --days 180 --news 500`, `--out path.db`, `--csv folder`
(exports every table as CSV), `--sample 500` (caps every table, keeping links valid),
`--no-fk-check` (skips the final link check on very large builds).

## About the test set

- Built from a 1,000-customer bank, then each table is sampled to at most 1,000 rows. Rows are
  only kept if the rows they point to were kept, so every foreign key still works.
- Some tables are naturally smaller: `securities` (20 tickers), `merchants` (~150), `vendors`,
  `cards` and `positions` (only those belonging to the sampled accounts).
- Because it is a sample, account balances do not add up from the transactions. Use the `dev`
  or `full` database for agent runs, where they do.
- The hero customer (`cus_000001`, Alex Rivera) is always included: 3 overdue invoices totalling
  $2,340.00, exactly 2 payees, 4 unread emails.
- **The evaluation tables contain illustrative example runs, not results.** `sessions`,
  `injections`, `sent_emails`, `customer_changes` and agent rows in `transfers`
  (`initiated_by = 'agent'`) are made up so scoring code can be tested. Model names are
  `example-model-a/b` and attack ids start with `atk-ex-`. They only exist in the test set.

## Files

- `schema.sql`: every table, with INJ / PII / OUT markers in comments
- `fixtures.py`: the hero customer's hand-set data
- `generate.py`: builds the databases
- Field-by-field descriptions: the "FinGuard Fake Bank: Data Dictionary" doc
