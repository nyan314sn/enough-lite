"""A real MCP client session over stdio: starts mcp_server.py, lists the tools, calls plan_check and search_rules.

Run from the project root:  python docs/mcp/demo_client.py
The output of one run is saved in docs/mcp/demo_transcript.md. No AI model is involved on either side.
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]


def show(title: str, data) -> None:
    print(f"\n### {title}\n")
    print("```json")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("```")


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("## Tools offered by the `enough` server\n")
            for t in tools.tools:
                print(f"- `{t.name}`: {(t.description or '').strip().splitlines()[0]}")

            print("\n## Call 1: plan_check for \"a 58-year-old in Ohio, $400k saved, $70k pay, retire at 65, spend $55k\"")
            args = {"household": {"age": 58, "state": "OH", "savings_total": 400000, "pay_per_year": 70000,
                                  "retire_age": 65, "spending_per_year": 55000}}
            print("\nArguments:\n\n```json\n" + json.dumps(args, indent=2) + "\n```")
            r = await session.call_tool("plan_check", args)
            out = r.structured_content
            keep = ["status", "headline", "count_on_per_year", "count_on_confidence", "basics_per_year", "basics_paid_of_100",
                    "verdict", "verdict_words", "spending_goal_per_year", "goal_line", "short_of_goal_per_year", "retire_age",
                    "planning_age", "social_security_per_year", "social_security_claim_age", "notes", "engine", "not_financial_advice"]
            show("Result (key fields)", {k: out[k] for k in keep})
            show("Inputs the server had to assume", out["assumed_inputs"])
            print("\nMain assumptions (first 4 of %d):\n" % len(out["assumptions"]))
            for a in out["assumptions"][:4]:
                print(f"- {a}")

            print("\n## Call 2: search_rules(\"When can I sign up for Medicare?\")")
            r = await session.call_tool("search_rules", {"question": "When can I sign up for Medicare?"})
            out = r.structured_content
            show("Result", {"status": out["status"], "source": out["source"],
                            "passages": [{"title": p["title"], "url": p["url"], "text": p["text"][:300]} for p in out["passages"]]})

            print("\n## Call 3: a refused request")
            r = await session.call_tool("search_rules", {"question": "How can I give away my savings to qualify for Medicaid?"})
            show("Result", r.structured_content)


if __name__ == "__main__":
    asyncio.run(main())
