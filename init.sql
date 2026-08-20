-- Seed Postgres the way Supabase PostgREST does: claims land in
-- request.jwt.claim.*, and RLS policies read them. Superusers bypass RLS,
-- so the app connects as notes_app, not postgres.

CREATE ROLE notes_app LOGIN PASSWORD 'notes_app';

CREATE TABLE notes (
    id      SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    body    TEXT NOT NULL
);

ALTER TABLE notes ENABLE ROW LEVEL SECURITY;

-- Mirrors Supabase: auth context is the JWT `sub` claim, not app-layer filters.
CREATE POLICY notes_owner ON notes
    FOR SELECT
    TO notes_app
    USING (user_id = current_setting('request.jwt.claim.sub', true));

GRANT SELECT ON notes TO notes_app;
GRANT USAGE, SELECT ON SEQUENCE notes_id_seq TO notes_app;

INSERT INTO notes (user_id, body) VALUES
    ('user-a', 'Alice: draft RLS-aware MCP gateway'),
    ('user-a', 'Alice: re-read auth.uid() / JWT sub docs'),
    ('user-b', 'Bob: private product roadmap'),
    ('user-b', 'Bob: secret rotation checklist');
