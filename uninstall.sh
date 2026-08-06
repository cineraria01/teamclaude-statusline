#!/usr/bin/env bash
# Uninstaller for teamclaude-statusline: removes the statusLine entry it
# registered and deletes the script. Leaves everything else untouched.
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
SCRIPT_DEST="$CLAUDE_DIR/statusline-teamclaude.py"
SELECTOR_DEST="$CLAUDE_DIR/teamclaude-selector.sh"
SETTINGS="$CLAUDE_DIR/settings.json"

if [ -f "$SETTINGS" ]; then
  python3 - "$SETTINGS" "$SCRIPT_DEST" <<'PY'
import json, shutil, sys

settings_path, script_path = sys.argv[1], sys.argv[2]
with open(settings_path) as f:
    settings = json.load(f)
sl = settings.get("statusLine")
if sl and sl.get("command") == script_path:
    shutil.copy2(settings_path, settings_path + ".bak")
    del settings["statusLine"]
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"statusLine removed from {settings_path} (backup: .bak)")
else:
    print("statusLine in settings.json is not ours; leaving it as-is")
PY
fi

if [ -n "${TEAMCLAUDE_SHELL_RC:-}" ]; then
  SHELL_RCS=("$TEAMCLAUDE_SHELL_RC")
else
  SHELL_RCS=("$HOME/.bashrc" "$HOME/.zshrc")
fi

for SHELL_RC in "${SHELL_RCS[@]}"; do
  [ -f "$SHELL_RC" ] || continue
  python3 - "$SHELL_RC" <<'PY'
import shutil, sys

rc_path = sys.argv[1]
begin = "# >>> teamclaude-statusline selector >>>"
end = "# <<< teamclaude-statusline selector <<<"
with open(rc_path) as f:
    content = f.read()
start = content.find(begin)
finish = content.find(end, start) if start >= 0 else -1
if start >= 0 and finish >= 0:
    updated = (content[:start] + content[finish + len(end):]).rstrip() + "\n"
    shutil.copy2(rc_path, rc_path + ".bak")
    with open(rc_path, "w") as f:
        f.write(updated)
    print(f"numbered account selector removed from {rc_path}")
PY
done

rm -f "$SCRIPT_DEST" "$SELECTOR_DEST"
echo "Removed $SCRIPT_DEST and $SELECTOR_DEST"
echo "Note: 'teamclaude probe' was left as-is; run 'teamclaude probe off' if you want it off."
