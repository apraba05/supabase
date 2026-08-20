"""MCP server: query_notes sets JWT sub via SET LOCAL, then runs SQL under RLS.

Connects as notes_app (not a superuser) so Postgres actually enforces the policy.
"""

from __future__ import annotations

import json
import os
import re

import psycopg2
from psycopg2 import sql as psql
from mcp.server import MCPServer

DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://notes_app:notes_app@127.0.0.1:54329/notes",
)

# Demo hygiene: one SELECT, no stacked statements.
_SELECT_ONLY = re.compile(r"(?is)^\s*select\b")

app = MCPServer("rls-notes")


def _run_as(jwt_sub: str, sql: str) -> list[dict]:
    if not _SELECT_ONLY.match(sql) or ";" in sql.strip().rstrip(";"):
        raise ValueError("query_notes only accepts a single SELECT statement")

    conn = psycopg2.connect(DSN)
    try:
        with conn:
            with conn.cursor() as cur:
                # SET LOCAL = request-scoped claim (PostgREST / Supabase pattern).
                cur.execute(
                    psql.SQL("SET LOCAL request.jwt.claim.sub TO {}").format(
                        psql.Literal(jwt_sub)
                    )
                )
                cur.execute(sql)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


@app.tool()
def query_notes(jwt_sub: str, sql: str) -> str:
    """Run a SELECT on notes with RLS scoped to jwt_sub (JWT claim `sub`).

    Args:
        jwt_sub: Authenticated user id — becomes request.jwt.claim.sub for this call.
        sql: A single SELECT against the notes table.
    """
    rows = _run_as(jwt_sub, sql)
    return json.dumps({"jwt_sub": jwt_sub, "row_count": len(rows), "rows": rows}, indent=2)


if __name__ == "__main__":
    app.run()
