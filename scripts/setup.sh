#!/usr/bin/env bash
# Per-machine setup for macOS / Linux. Safe to re-run (e.g. after a new skill is added).
#   1. installs the MCP server into mcp/.venv (editable, with the dev group)
#   2. writes .mcp.json pointing at it -- only if .mcp.json doesn't exist yet
#   3. links every skill under skills/ into .claude/skills
# Usage: scripts/setup.sh ["League Name"]   (league defaults to "Forbidden Rites")
# It does not install Python: it checks for 3.10+ and tells you how if it's missing.
set -euo pipefail

LEAGUE="${1:-Forbidden Rites}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10+ not found. Install it (macOS: brew install python) and re-run." >&2
  exit 1
fi
echo "==> Using $("$PY" --version)"

echo "==> Installing the MCP server into mcp/.venv"
[ -x mcp/.venv/bin/python ] || "$PY" -m venv mcp/.venv
mcp/.venv/bin/python -m pip install --quiet --upgrade pip
# --group reads pyproject.toml from the current directory, so install from inside mcp/.
(cd mcp && .venv/bin/python -m pip install --quiet -e . --group dev)

if [ -e .mcp.json ]; then
  echo "==> .mcp.json already exists; leaving it as is"
else
  echo "==> Writing .mcp.json (league: $LEAGUE)"
  mcp/.venv/bin/python - "$ROOT/mcp/.venv/bin/poe2-mcp" "$LEAGUE" <<'PYEOF'
import json, sys
command, league = sys.argv[1], sys.argv[2]
config = {"mcpServers": {"poe2": {"command": command, "env": {"POE2_LEAGUE": league}}}}
with open(".mcp.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
PYEOF
fi

echo "==> Linking skills into .claude/skills"
mkdir -p .claude/skills
for dir in skills/*/; do
  name="$(basename "$dir")"
  ln -sfn "../../skills/$name" ".claude/skills/$name"
  echo "    $name"
done

echo "==> Checking the server imports"
mcp/.venv/bin/python -c "import poe2_mcp.server" && echo "    ok"

echo
echo "Done. Open this folder in Claude Code (or restart the session) and approve the 'poe2' server."
