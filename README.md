# RLS-Aware MCP Query Gateway

Agentic tool-use (MCP) safely scoped by database-level auth context, mirroring Supabase's own MCP server + RLS story.

**Live demo:** https://supabase.ashanpraba.com

The demo runs entirely in the browser against seeded data — no API keys,
no accounts, and no external services required.

## Stack

- Python
- PostgreSQL
- Row Level Security
- MCP
- LangChain or Bedrock agent
- Docker

## How it works

- Docker-compose up a single Postgres container; create table notes(id,user_id,body) with RLS policy restricting rows to current_setting('request.jwt.claim.sub').
- Write a small Python MCP server exposing a query_notes(jwt_sub, sql) tool that runs SET LOCAL before executing the query so RLS is enforced per-call.
- The tool into a minimal LangChain (or Bedrock) agent loop with two fake user identities.
- Demo: agent as user A retrieves only their notes; agent attempts cross-user query and gets empty result due to RLS.
- Screen-record a 60-90s terminal walkthrough showing both the allowed and blocked query, narrating the SET LOCAL/RLS mechanism.

## Running locally

```bash
cd src
bash run.sh
```

Then open the printed URL. A prebuilt static version of the UI lives in
`src/web/` and can be opened directly with no server.
