#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT

TEST_HOME="$TEST_DIR/home"
TEST_BIN="$TEST_DIR/bin"
mkdir -p "$TEST_HOME/.claude" "$TEST_BIN"
printf '%s\n' "alias claude='teamclaude run --'" "export KEEP_ME=1" > "$TEST_HOME/.bashrc"
printf '%s\n' '{"keep": true}' > "$TEST_HOME/.claude/settings.json"

cat > "$TEST_BIN/teamclaude" <<'SH'
#!/usr/bin/env bash
if [ "${1:-}" = status ] && [ "${2:-}" = --json ]; then
  printf '%s\n' '{"accounts":[{"name":"one@example.com"},{"name":"two@example.com"}]}'
  exit
fi
printf 'PIN=%s ARGS=%s\n' "${TC_ACCT:-}" "$*"
SH
chmod +x "$TEST_BIN/teamclaude"

install_once() {
  HOME="$TEST_HOME" SHELL=/bin/bash CLAUDE_DIR="$TEST_HOME/.claude" \
    NO_PROBE=1 PATH="$TEST_BIN:$PATH" "$REPO_DIR/install.sh" >/dev/null
}

install_once
first_rc_checksum=$(cksum < "$TEST_HOME/.bashrc")
install_once
test "$first_rc_checksum" = "$(cksum < "$TEST_HOME/.bashrc")"

test -x "$TEST_HOME/.claude/statusline-teamclaude.py"
test -r "$TEST_HOME/.claude/teamclaude-selector.sh"
test "$(grep -c '^# >>> teamclaude-statusline selector >>>$' "$TEST_HOME/.bashrc")" -eq 1
grep -q '^export KEEP_ME=1$' "$TEST_HOME/.bashrc"
python3 - "$TEST_HOME/.claude/settings.json" <<'PY'
import json, sys

with open(sys.argv[1]) as f:
    settings = json.load(f)
assert settings["keep"] is True
assert settings["statusLine"]["command"].endswith("statusline-teamclaude.py")
PY

selected=$(HOME="$TEST_HOME" PATH="$TEST_BIN:$PATH" \
  bash --noprofile --rcfile "$TEST_HOME/.bashrc" -ic 'claude 2 --continue' 2>/dev/null)
grep -q 'TeamClaude #2: two@example.com' <<< "$selected"
grep -q 'PIN=two@example.com ARGS=run -- --continue' <<< "$selected"

HOME="$TEST_HOME" SHELL=/bin/zsh CLAUDE_DIR="$TEST_HOME/.claude" \
  PATH="$TEST_BIN:$PATH" \
  "$REPO_DIR/uninstall.sh" >/dev/null

test ! -e "$TEST_HOME/.claude/statusline-teamclaude.py"
test ! -e "$TEST_HOME/.claude/teamclaude-selector.sh"
! grep -q 'teamclaude-statusline selector' "$TEST_HOME/.bashrc"
grep -q "^alias claude='teamclaude run --'$" "$TEST_HOME/.bashrc"
grep -q '^export KEEP_ME=1$' "$TEST_HOME/.bashrc"
python3 - "$TEST_HOME/.claude/settings.json" <<'PY'
import json, sys

with open(sys.argv[1]) as f:
    settings = json.load(f)
assert settings == {"keep": True}
PY

printf '%s\n' '{"statusLine":{"type":"command","command":"keep-me"}}' \
  > "$TEST_HOME/.claude/settings.json"
! install_once 2>/dev/null
grep -q '"command":"keep-me"' "$TEST_HOME/.claude/settings.json"

WEIRD_CLAUDE="$TEST_HOME/.claude weird ' \$()"
WEIRD_RC="$TEST_HOME/.weirdrc"
HOME="$TEST_HOME" SHELL=/bin/bash CLAUDE_DIR="$WEIRD_CLAUDE" \
  TEAMCLAUDE_SHELL_RC="$WEIRD_RC" NO_PROBE=1 PATH="$TEST_BIN:$PATH" \
  "$REPO_DIR/install.sh" >/dev/null
bash -n "$WEIRD_RC"
HOME="$TEST_HOME" CLAUDE_DIR="$WEIRD_CLAUDE" TEAMCLAUDE_SHELL_RC="$WEIRD_RC" \
  "$REPO_DIR/uninstall.sh" >/dev/null
