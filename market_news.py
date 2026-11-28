"""
market_news.py - a second MCP server: market news and exchange rates.

This is "third-party" content: the bank doesn't write the news, so every
headline and story is OUTSIDE text, a place an attacker could hide orders
for the AI (see attack A3 in attacks.yaml, which poisons story N005).

Tools: get_news, get_fx_rate
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

import bank_core

DB_PATH = Path(__file__).parent / "bank.db"

mcp = FastMCP("market-news", log_level="WARNING")


@mcp.tool()
def get_news(limit: int = 5) -> list[dict]:
    """Returns the latest market news headlines and stories."""
    limit = max(1, min(int(limit), 20))
    return bank_core.query(
        "SELECT article_id, substr(published_at, 1, 10) AS date, source, headline, summary, body "
        "FROM news ORDER BY published_at DESC, article_id DESC LIMIT ?", limit)


@mcp.tool()
def get_fx_rate(base: str, quote: str) -> dict:
    """Returns the latest exchange rate between two currencies, e.g. base='USD', quote='EUR'."""
    rows = bank_core.query(
        "SELECT pair, rate_date, mid_rate, customer_rate FROM fx_rates "
        "WHERE base_currency = ? AND quote_currency = ? ORDER BY rate_date DESC LIMIT 1",
        base.upper(), quote.upper())
    return rows[0] if rows else {"error": f"No rate for {base}/{quote}"}


if __name__ == "__main__":
    mcp.run()
