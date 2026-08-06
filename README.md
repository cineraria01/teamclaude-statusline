# teamclaude-statusline

Live per-account quota usage for the [teamclaude](https://www.npmjs.com/package/teamclaude) multi-account Claude proxy, right in your Claude Code status line.

```
Fable 5 │ ciner --·-- │ cindy 0%·100% │ ▶lucy 7%·19% │ nextp 3%·46% │ ↻06:30
```

Each account shows `5h-usage · 7d-usage` (the 7d figure prefers the model-specific bucket, e.g. Fable/Sonnet weekly quota, when the proxy reports one):

- `▶` — the account currently serving your requests
- `↻HH:MM` — when the current account's 5h window resets (local time)
- `⛔HH:MM` — the account is rate-limited until that time
- `off` — the account is excluded from rotation
- colors: green < 70% < yellow < 90% < red
- `TC down` — the proxy isn't running; `teamclaude not installed` — the CLI is missing

## Requirements

- [teamclaude](https://www.npmjs.com/package/teamclaude) installed and running (`npm install -g teamclaude`)
- Claude Code
- `python3` (stdlib only, 3.8+)

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/cineraria01/teamclaude-statusline/main/install.sh | bash
```

Or from a clone:

```sh
git clone https://github.com/cineraria01/teamclaude-statusline
cd teamclaude-statusline && ./install.sh
```

The installer:

1. copies `statusline-teamclaude.py` to `~/.claude/`
2. registers it as `statusLine` in `~/.claude/settings.json` (backing the file up to `settings.json.bak` first; every other setting is preserved)
3. enables `teamclaude probe 300` so idle accounts' quota stays fresh — the probe only reads the usage endpoint and **does not spend quota** (skip with `NO_PROBE=1`)

Restart Claude Code (or start a new session) and the status line appears.

## Configuration

Environment variables read by the script:

| Variable | Default | Meaning |
|---|---|---|
| `TC_SL_CACHE_TTL` | `15` | seconds to cache `teamclaude status --json` output |
| `TC_SL_CACHE_FILE` | `$TMPDIR/tc-statusline-cache-$UID.json` | cache file path |
| `NO_COLOR` | unset | disable ANSI colors ([no-color.org](https://no-color.org)) |

The refresh interval (default 30s even when idle) lives in the `statusLine.refreshInterval` field of `~/.claude/settings.json`.

## Uninstall

```sh
curl -fsSL https://raw.githubusercontent.com/cineraria01/teamclaude-statusline/main/uninstall.sh | bash
```

Removes the script and the `statusLine` entry it registered (only if it still points at this script). The quota probe is left as-is; `teamclaude probe off` disables it.

## 한국어 안내

teamclaude 다계정 프록시의 계정별 사용량(5시간·7일 쿼터)을 Claude Code 상태줄에 상시 표시합니다. 위의 원라인 설치 명령을 실행한 뒤 Claude Code를 재시작하면 됩니다. `▶`는 현재 라우팅 중인 계정, `↻`는 현재 계정의 5시간 윈도 리셋 시각, `⛔`는 레이트리밋 해제 시각입니다. 설치 스크립트는 `~/.claude/settings.json`을 백업 후 `statusLine` 항목만 추가하며, 다른 설정은 건드리지 않습니다.

## License

MIT
