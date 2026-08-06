#!/usr/bin/env bash
# Installer for teamclaude-statusline.
#
#   curl -fsSL https://raw.githubusercontent.com/cineraria01/teamclaude-statusline/main/install.sh | bash
#
# Options (env vars):
#   CLAUDE_DIR               Claude Code config dir (default: ~/.claude)
#   TEAMCLAUDE_SHELL_RC      shell rc file override (default: ~/.bashrc or ~/.zshrc)
#   NO_PROBE=1               skip enabling `teamclaude probe 300`
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/cineraria01/teamclaude-statusline/main"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
SCRIPT_DEST="$CLAUDE_DIR/statusline-teamclaude.py"
SELECTOR_DEST="$CLAUDE_DIR/teamclaude-selector.sh"
SETTINGS="$CLAUDE_DIR/settings.json"

command -v python3 >/dev/null || { echo "error: python3 is required" >&2; exit 1; }

mkdir -p "$CLAUDE_DIR"

# Never replace another status line silently.
if [ -f "$SETTINGS" ]; then
  python3 - "$SETTINGS" "$SCRIPT_DEST" <<'PY'
import json, sys

settings_path, script_path = sys.argv[1], sys.argv[2]
try:
    with open(settings_path) as f:
        status_line = json.load(f).get("statusLine")
except ValueError:
    sys.exit(f"error: {settings_path} is not valid JSON; fix it and re-run")
if status_line and status_line.get("command") != script_path:
    sys.exit(
        "error: another statusLine is already configured: "
        f"{status_line.get('command')}\nremove it first, then re-run the installer"
    )
PY
fi

# Copy assets from a local checkout when run from the repo, otherwise download.
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-/dev/null}")" 2>/dev/null && pwd || true)"
install_asset() {
  local name=$1 destination=$2
  if [ -n "$SRC_DIR" ] && [ -f "$SRC_DIR/$name" ]; then
    cp "$SRC_DIR/$name" "$destination"
  else
    curl -fsSL "$REPO_RAW/$name" -o "$destination"
  fi
}

install_asset statusline-teamclaude.py "$SCRIPT_DEST"
install_asset teamclaude-selector.sh "$SELECTOR_DEST"
chmod +x "$SCRIPT_DEST"
chmod 644 "$SELECTOR_DEST"

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
    sys.exit(f"error: another statusLine is already configured: {prev.get('command')}")

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

# Source the numbered account selector after existing aliases/functions. The
# marked block is replaced idempotently and uninstall removes only this block.
SHELL_RC="${TEAMCLAUDE_SHELL_RC:-}"
if [ -z "$SHELL_RC" ]; then
  case "${SHELL##*/}" in
    bash) SHELL_RC="$HOME/.bashrc" ;;
    zsh) SHELL_RC="$HOME/.zshrc" ;;
  esac
fi

if [ -n "$SHELL_RC" ]; then
  python3 - "$SHELL_RC" "$SELECTOR_DEST" <<'PY'
import os, shlex, shutil, sys

rc_path, selector_path = sys.argv[1], sys.argv[2]
begin = "# >>> teamclaude-statusline selector >>>"
end = "# <<< teamclaude-statusline selector <<<"
quoted_selector = shlex.quote(selector_path)
block = f"{begin}\n[ -r {quoted_selector} ] && . {quoted_selector}\n{end}"

try:
    with open(rc_path) as f:
        content = f.read()
except FileNotFoundError:
    content = ""
original = content

start = content.find(begin)
if start >= 0:
    finish = content.find(end, start)
    if finish < 0:
        sys.exit(f"error: incomplete teamclaude-statusline selector block in {rc_path}")
    content = content[:start] + content[finish + len(end):]

base = content.rstrip()
updated = (base + "\n\n" if base else "") + block + "\n"
if updated != original:
    if os.path.exists(rc_path):
        shutil.copy2(rc_path, rc_path + ".bak")
    os.makedirs(os.path.dirname(rc_path) or ".", exist_ok=True)
    with open(rc_path, "w") as f:
        f.write(updated)
print(f"numbered account selector registered in {rc_path}")
PY
else
  echo "warning: numbered selector supports Bash/Zsh only; set TEAMCLAUDE_SHELL_RC to a Bash/Zsh rc file" >&2
fi

# Enable the background quota probe so idle accounts' usage stays fresh.
# It only reads the usage endpoint and does not spend quota.
if [ -z "${NO_PROBE:-}" ] && command -v teamclaude >/dev/null 2>&1; then
  teamclaude probe 300 || echo "warning: could not enable probe (is the proxy running?)" >&2
elif ! command -v teamclaude >/dev/null 2>&1; then
  echo "warning: teamclaude not found in PATH — the status line will show 'teamclaude not installed'" >&2
  echo "         install it first: npm install -g @karpeleslab/teamclaude" >&2
fi

echo
echo "Done. Restart Claude Code (or start a new session) to see the status line."
echo "Open a new shell, then use 'claude 1', 'claude 2', ... to pin an account."
