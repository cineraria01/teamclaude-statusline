#!/usr/bin/env bash
# Installer for teamclaude-statusline.
#
#   curl -fsSL https://raw.githubusercontent.com/cineraria01/teamclaude-statusline/main/install.sh | bash
#
# Options (env vars):
#   CLAUDE_DIR   Claude Code config dir (default: ~/.claude)
#   NO_PROBE=1   skip enabling `teamclaude probe 300`
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/cineraria01/teamclaude-statusline/main"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
SCRIPT_DEST="$CLAUDE_DIR/statusline-teamclaude.py"
SETTINGS="$CLAUDE_DIR/settings.json"

command -v python3 >/dev/null || { echo "error: python3 is required" >&2; exit 1; }

mkdir -p "$CLAUDE_DIR"

# Copy the script from a local checkout when run from the repo, otherwise download.
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-/dev/null}")" 2>/dev/null && pwd || true)"
if [ -n "$SRC_DIR" ] && [ -f "$SRC_DIR/statusline-teamclaude.py" ]; then
  cp "$SRC_DIR/statusline-teamclaude.py" "$SCRIPT_DEST"
else
  curl -fsSL "$REPO_RAW/statusline-teamclaude.py" -o "$SCRIPT_DEST"
fi
chmod +x "$SCRIPT_DEST"

# Merge statusLine into settings.json (backs up first; preserves everything else).
python3 - "$SETTINGS" "$SCRIPT_DEST" <<'PY'
import json, shutil, sys

settings_path, script_path = sys.argv[1], sys.argv[2]
try:
    with open(settings_path) as f:
        settings = json.load(f)
    shutil.copy2(settings_path, settings_path + ".bak")
    print(f"backed up settings to {settings_path}.bak")
except FileNotFoundError:
    settings = {}
except ValueError:
    sys.exit(f"error: {settings_path} is not valid JSON; fix it and re-run")

prev = settings.get("statusLine")
if prev and prev.get("command") != script_path:
    print(f"note: replacing existing statusLine command: {prev.get('command')}")

settings["statusLine"] = {
    "type": "command",
    "command": script_path,
    "refreshInterval": 30,
}
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"statusLine registered in {settings_path}")
PY

# Enable the background quota probe so idle accounts' usage stays fresh.
# It only reads the usage endpoint and does not spend quota.
if [ -z "${NO_PROBE:-}" ] && command -v teamclaude >/dev/null 2>&1; then
  teamclaude probe 300 || echo "warning: could not enable probe (is the proxy running?)" >&2
elif ! command -v teamclaude >/dev/null 2>&1; then
  echo "warning: teamclaude not found in PATH — the status line will show 'teamclaude not installed'" >&2
  echo "         install it first: npm install -g teamclaude" >&2
fi

echo
echo "Done. Restart Claude Code (or start a new session) to see the status line."
