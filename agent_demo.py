"""Minimal LangChain agent loop over the MCP query_notes tool.

No cloud LLM: turns are scripted so the one-command demo is reliable on camera.
Each turn still goes LangChain tool → MCP stdio → SET LOCAL → Postgres RLS.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

# Two fake identities; seed data lives in init.sql.
USER_A = "user-a"
USER_B = "user-b"

TURNS = [
    {
        "as": USER_A,
        "goal": "List my notes",
        "sql": "SELECT id, user_id, body FROM notes ORDER BY id",
        "expect": "only user-a rows",
    },
    {
        "as": USER_A,
        "goal": "Cross-user read: filter WHERE user_id = 'user-b'",
        "sql": "SELECT id, user_id, body FROM notes WHERE user_id = 'user-b'",
        "expect": "empty — RLS drops Bob's rows before the WHERE helps",
    },
    {
        "as": USER_B,
        "goal": "List my notes (prove Bob's data is still there)",
        "sql": "SELECT id, user_id, body FROM notes ORDER BY id",
        "expect": "only user-b rows",
    },
]


def _text_from_tool_result(result) -> str:
    parts = []
    for block in result.content or []:
        if isinstance(block, TextContent):
            parts.append(block.text)
        else:
            parts.append(str(block))
    return "\n".join(parts) if parts else str(result)


async def run() -> None:
    params = StdioServerParameters(
        command=PYTHON,
        args=[str(ROOT / "mcp_server.py")],
        cwd=str(ROOT),
        env=None,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def query_notes(jwt_sub: str, sql: str) -> str:
                """Query notes under Postgres RLS for the given JWT sub."""
                result = await session.call_tool(
                    "query_notes",
                    {"jwt_sub": jwt_sub, "sql": sql},
                )
                if result.is_error:
                    raise RuntimeError(_text_from_tool_result(result))
                return _text_from_tool_result(result)

            tool = StructuredTool.from_function(
                name="query_notes",
                description=(
                    "Run a SELECT on notes with Row Level Security scoped to jwt_sub. "
                    "Pass the authenticated user's id as jwt_sub."
                ),
                coroutine=query_notes,
            )

            print("RLS-Aware MCP Query Gateway")
            print("LangChain tool → MCP query_notes → SET LOCAL request.jwt.claim.sub → RLS\n")

            for i, turn in enumerate(TURNS, start=1):
                print(f"--- turn {i}: agent as {turn['as']} ---")
                print(f"goal:  {turn['goal']}")
                print(f"expect: {turn['expect']}")
                print(f"tool:  query_notes(jwt_sub={turn['as']!r}, sql={turn['sql']!r})")
                out = await tool.ainvoke({"jwt_sub": turn["as"], "sql": turn["sql"]})
                print(out)
                print()


if __name__ == "__main__":
    asyncio.run(run())
