"""Real MCP protocol check: spawn the FastMCP server as a subprocess and talk to it over stdio (JSON-RPC)."""
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
res = []


def ok(name, cond, detail=""):
    res.append((name, "PASS" if cond else "FAIL", str(detail)[:150]))


async def main():
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, "mcp_server_fixture.py")])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            ok("initialize handshake", init.serverInfo.name == "Finance Tracker MCP Server", f"{init.serverInfo.name} proto={init.protocolVersion}")
            tools = (await session.list_tools()).tools
            names = {t.name for t in tools}
            ok("tool discovery", names == {"add_transaction", "get_budget_status", "get_account_summary"}, sorted(names))
            by = {t.name: t for t in tools}
            sch = by["add_transaction"].inputSchema
            ok("schema: required/typed args", set(sch["required"]) == {"account_id", "amount", "transaction_type", "category", "description", "transaction_date"}
               and sch["properties"]["amount"]["type"] == "number" and sch["properties"]["account_id"]["type"] == "integer", json.dumps(sch["properties"])[:120])
            ok("schema: description from docstring", "transaction_type must be" in (by["add_transaction"].description or ""))
            ok("schema: no-arg tool", by["get_budget_status"].inputSchema.get("properties", {}) == {})
            r = await session.call_tool("add_transaction", {"account_id": 1, "amount": 500.0, "transaction_type": "debit",
                                                              "category": "food", "description": "Groceries", "transaction_date": "2026-11-11"})
            payload = json.loads(r.content[0].text)
            ok("invoke with typed args", not r.isError and payload["amount"] == 500.0 and payload["category"] == "food", payload)
            r2 = await session.call_tool("add_transaction", {"account_id": 1, "amount": 1.0, "transaction_type": "expense",
                                                               "category": "food", "description": "x", "transaction_date": "2026-11-11"})
            ok("business-error returned as error dict (spec MCP-08)", "error" in json.loads(r2.content[0].text), r2.content[0].text)
            r3 = await session.call_tool("get_account_summary", {"account_id": 404})
            ok("unhandled exception -> isError=True, server stays alive", r3.isError is True, r3.content[0].text)
            r4 = await session.call_tool("get_account_summary", {"account_id": "not-an-int"})
            ok("invalid argument type rejected (isError)", r4.isError is True, r4.content[0].text)
            r5 = await session.call_tool("get_account_summary", {})
            ok("missing required arg rejected (isError)", r5.isError is True)
            try:
                r6 = await session.call_tool("no_such_tool", {})
                ok("unknown tool -> error", r6.isError is True, r6.content[0].text)
            except Exception as e:  # noqa: BLE001
                ok("unknown tool -> error", True, type(e).__name__)
            outs = []
            for i in range(5):
                x = await session.call_tool("add_transaction", {"account_id": 1, "amount": float(i + 1), "transaction_type": "debit",
                                                                  "category": "food", "description": f"t{i}", "transaction_date": "2026-11-11"})
                outs.append(json.loads(x.content[0].text))
            ok("multiple sequential calls keep server state", [o["id"] for o in outs] == [2, 3, 4, 5, 6], [o["id"] for o in outs])
            conc = await asyncio.gather(*[session.call_tool("get_account_summary", {"account_id": i}) for i in range(1, 6)])
            ok("5 concurrent calls", all(not c.isError for c in conc) and sorted(json.loads(c.content[0].text)["account_id"] for c in conc) == [1, 2, 3, 4, 5])
            ok("server is a separate process (real transport)", outs[0]["pid"] != os.getpid(), outs[0]["pid"])
            after = await session.call_tool("get_budget_status", {})
            ok("still healthy after errors", not after.isError)


asyncio.run(main())
w = max(len(n) for n, _, _ in res)
for n, s, d in res:
    print(f"{s:5} {n:<{w}} {d}")
sys.exit(1 if any(s == "FAIL" for _, s, _ in res) else 0)
