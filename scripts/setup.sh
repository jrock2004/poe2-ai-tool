#!/usr/bin/env bash
# Dev setup for macOS / Linux: builds mcp/.venv (editable, with the dev group) so the tests run.
# Players don't need this -- they install the plugin (README -> Install). Safe to re-run.
# Usage: scripts/setup.sh
# It does not install Python: it checks for 3.10+ and tells you how if it's missing.
set -euo pipefail

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

echo "==> Checking the server imports"
mcp/.venv/bin/python -c "import poe2_mcp.server" && echo "    ok"

# The pre-plugin setup wired the server and skills in per project; with the plugin installed too,
# both would load twice. Point it out rather than deleting anything.
if [ -e .mcp.json ] || [ -e .claude/skills ]; then
  echo
  echo "Note: .mcp.json and/or .claude/skills are left over from the old setup. Delete them once the"
  echo "plugin is installed, or the poe2 server and skills load twice."
fi

echo
echo "Done. Run the tests with: cd mcp && .venv/bin/python -m pytest -q"
echo "To use your working copy in Claude Code, add it as a local marketplace (README -> Development)."
