#!/usr/bin/env bash
# Uninstaller for teamclaude-statusline: removes the statusLine entry it
# registered and deletes the script. Leaves everything else untouched.
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
SCRIPT_DEST="$CLAUDE_DIR/statusline-teamclaude.py"
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

rm -f "$SCRIPT_DEST"
echo "Removed $SCRIPT_DEST"
echo "Note: 'teamclaude probe' was left as-is; run 'teamclaude probe off' if you want it off."
