# Numbered account selector for teamclaude-statusline.
# Sourced by Bash/Zsh; `claude` keeps automatic rotation and `claude N` pins
# the new session to account N in `teamclaude status --json` order.

unalias claude 2>/dev/null || true

claude() {
    if ! command -v teamclaude >/dev/null 2>&1; then
        printf 'TeamClaude is not installed. Run: npm install -g @karpeleslab/teamclaude\n' >&2
        return 127
    fi

    case "${1:-}" in
        ''|*[!0-9]*)
            command teamclaude run -- "$@"
            return
            ;;
    esac

    local number=$1 account
    shift
    account=$(command teamclaude status --json 2>/dev/null | python3 -c '
import json
import sys

accounts = json.load(sys.stdin).get("accounts", [])
index = int(sys.argv[1]) - 1
print(accounts[index].get("name", "") if 0 <= index < len(accounts) else "")
' "$number" 2>/dev/null)

    if [ -z "$account" ]; then
        printf 'TeamClaude account number not found: %s\n' "$number" >&2
        return 2
    fi

    printf 'TeamClaude #%s: %s\n' "$number" "$account"
    TEAMCLAUDE_STATUSLINE_INDEX="$number" TC_ACCT="$account" \
        command teamclaude run -- "$@"
}
