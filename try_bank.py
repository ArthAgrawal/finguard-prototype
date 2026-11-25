"""
try_bank.py - a tiny MCP client to test bank_core.py by hand (no AI yet).

It does what an AI agent would do, but with the calls hard-coded:
  1. start bank_core.py as a separate process
  2. ask it for its tools (tools/list)
  3. call a few tools and print the results

Run it:
    python seed.py        (fresh bank first)
    python try_bank.py
"""

import asyncio
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = StdioServerParameters(
    command=sys.executable,                                  # the Python in your .venv
    args=[str(Path(__file__).parent / "bank_core.py")],
)


def text_of(result):
    """Pull the plain text out of an MCP tool result."""
    return "\n".join(c.text for c in result.content if hasattr(c, "text"))


async def main():
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. What tools does the bank offer? (this is exactly what the AI will see)
            tools = await session.list_tools()
            print("=== Tools offered by bank-core ===")
            for t in tools.tools:
                print(f"- {t.name}: {t.description}")

            # 2. Read some data
            print("\n=== get_balance ===")
            print(text_of(await session.call_tool("get_balance", {"account_id": "ACC-1001"})))

            print("\n=== list_transactions (first 3) ===")
            print(text_of(await session.call_tool("list_transactions",
                                                  {"account_id": "ACC-1001", "limit": 3})))

            # 3. Try paying a stranger directly -> should be refused
            print("\n=== transfer to a stranger (should fail) ===")
            print(text_of(await session.call_tool("transfer_funds",
                  {"from_account": "ACC-1001", "to_account": "7731-0092", "amount": 1.0})))

            # 4. Pay the sister (a saved payee) -> should work
            print("\n=== transfer $20 to sister (should work) ===")
            print(text_of(await session.call_tool("transfer_funds",
                  {"from_account": "ACC-1001", "to_account": "6602-1188", "amount": 20.0})))

            print("\n=== balance after ===")
            print(text_of(await session.call_tool("get_balance", {"account_id": "ACC-1001"})))


if __name__ == "__main__":
    asyncio.run(main())
