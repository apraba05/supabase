#!/usr/bin/env bash
# One-command demo: Postgres + RLS → MCP query_notes → LangChain agent turns.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
BIN="${ROOT}/.bin"
VENV="${ROOT}/.venv"
mkdir -p "$BIN"
export PATH="$BIN:$PATH"

need_docker() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  if sg docker -c 'docker info' >/dev/null 2>&1; then
    exec sg docker -c "\"$0\" $*"
  fi
  echo "Docker is required (and your user must reach the docker socket)." >&2
  exit 1
}

ensure_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
    return
  fi
  local dest="${BIN}/docker-compose"
  if [[ ! -x "$dest" ]]; then
    echo "==> installing docker-compose into .bin/"
    curl -fsSL \
      "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64" \
      -o "$dest"
    chmod +x "$dest"
  fi
  COMPOSE=("$dest")
}

ensure_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON=python3.11
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
  else
    echo "Python 3.11+ is required (mcp package)." >&2
    exit 1
  fi
  local major minor
  major="$("$PYTHON" -c 'import sys; print(sys.version_info[0])')"
  minor="$("$PYTHON" -c 'import sys; print(sys.version_info[1])')"
  if (( major < 3 || (major == 3 && minor < 10) )); then
    echo "Python 3.10+ required; found $($PYTHON --version)." >&2
    exit 1
  fi
}

need_docker "$@"
ensure_compose
ensure_python

if [[ ! -d "$VENV" ]]; then
  echo "==> creating venv"
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
pip install -q -r requirements.txt

echo "==> starting Postgres"
"${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
"${COMPOSE[@]}" up -d

echo "==> waiting for Postgres"
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T db pg_isready -U postgres -d notes >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! "${COMPOSE[@]}" exec -T db pg_isready -U postgres -d notes >/dev/null 2>&1; then
  echo "Postgres did not become ready." >&2
  exit 1
fi
# init.sql runs only on first volume create; give it a beat.
sleep 1

export DATABASE_URL="${DATABASE_URL:-postgresql://notes_app:notes_app@127.0.0.1:54329/notes}"

echo "==> agent demo (LangChain → MCP → RLS)"
python agent_demo.py

echo
echo "Done. Tear down with: ${COMPOSE[*]} down -v"
