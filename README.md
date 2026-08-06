# teamclaude-statusline

Live per-account quota usage for the [teamclaude](https://www.npmjs.com/package/@karpeleslab/teamclaude) multi-account Claude proxy, right in your Claude Code status line.

```
Fable 5
1 cindy O 64% · F⛔ ↻8h30m
2 ciner O 59% · F⛔ ↻1d16h
3 nextp [5h 4% ↻4h · O 32% ↻1d21h · F 46% ↻1d21h]
▶4 lucy [5h 7% ↻2h · O 58% ↻1d16h · F 19% ↻2d18h]
```

Each account shows `[5h usage ↻reset countdown · Opus/overall 7d usage ↻reset countdown · model 7d usage ↻reset countdown]` (`O` for Opus/overall, `F` for Fable, falling back to `S` for Sonnet when available):

`-- ↻--` means teamclaude did not report that usage window or its reset time.
When the Fable quota reaches teamclaude's switch threshold, the account remains usable for Opus and collapses to `O overall-usage · F⛔ ↻reset countdown`.
The model and each numbered account are rendered on separate lines so every metric group stays visible and uncluttered.

- `▶` — the account currently serving your requests
- `⛔HH:MM` — the account is rate-limited until that time
- `off` — the account is excluded from rotation
- colors: green < 70% < yellow < 90% < red
- `TC down` — the proxy isn't running; `teamclaude not installed` — the CLI is missing

## Requirements

- [teamclaude](https://www.npmjs.com/package/@karpeleslab/teamclaude) installed and running (`npm install -g @karpeleslab/teamclaude`)
- Claude Code
- `python3` (stdlib only, 3.8+)

Add at least one account before installing the status line:

```sh
teamclaude login       # browser OAuth
# or: teamclaude import
# or: teamclaude login --api
```

The installer stops without changing Claude settings when TeamClaude is missing or has no accounts. If accounts exist but the proxy is stopped, installation succeeds and prints the command needed to start it.

## Install

```sh
curl -fsSL "https://raw.githubusercontent.com/cineraria01/teamclaude-statusline/main/install.sh?$(date +%s)" | bash
```

Or from a clone:

```sh
git clone https://github.com/cineraria01/teamclaude-statusline
cd teamclaude-statusline && ./install.sh
```

The installer:

1. copies the TeamClaude status line and its small compatibility wrapper to `~/.claude/`
2. registers the wrapper as `statusLine` in `~/.claude/settings.json` (backing the file up to `settings.json.bak` first); an existing status line such as Orca is preserved and rendered before TeamClaude
3. installs the numbered account selector and sources it from `~/.bashrc` or `~/.zshrc` without removing existing aliases/settings
4. enables `teamclaude probe 300` so idle accounts' quota stays fresh — the probe only reads the usage endpoint and **does not spend quota** (skip with `NO_PROBE=1`)

Restart Claude Code (or start a new session) and the status line appears.

## Numbered account selection

Account numbers follow the top-to-bottom order shown in the status line and `teamclaude status`:

```sh
claude       # automatic rotation
claude 1     # pin a new session to account 1
claude 2 -c  # continue the latest session pinned to account 2
```

The selector resolves the live account list at launch time, so it contains no hardcoded emails. `▶` follows the number pinned for that Claude session instead of TeamClaude's global automatic-route pointer. A running Claude session cannot change accounts in place; start or resume a session with the desired number.

## Configuration

Environment variables read by the script:

| Variable | Default | Meaning |
|---|---|---|
| `TC_SL_CACHE_TTL` | `15` | seconds to cache `teamclaude status --json` output |
| `TC_SL_CACHE_FILE` | `$TMPDIR/tc-statusline-cache-$UID.json` | cache file path |
| `NO_COLOR` | unset | disable ANSI colors ([no-color.org](https://no-color.org)) |

Installer-only environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `CLAUDE_DIR` | `~/.claude` | Claude Code config directory |
| `TEAMCLAUDE_SHELL_RC` | detected Bash/Zsh rc | shell rc file to update |
| `NO_PROBE` | unset | set to `1` to skip `teamclaude probe 300` |

The refresh interval (default 30s even when idle) lives in the `statusLine.refreshInterval` field of `~/.claude/settings.json`.

## Uninstall

```sh
curl -fsSL "https://raw.githubusercontent.com/cineraria01/teamclaude-statusline/main/uninstall.sh?$(date +%s)" | bash
```

Removes the scripts, selector source block, and the `statusLine` entry it registered (only if it still points at this script). A previously configured status line is restored, and existing shell aliases/settings are preserved. The quota probe is left as-is; `teamclaude probe off` disables it.

## 한국어 안내

teamclaude 다계정 프록시의 계정별 사용량과 갱신까지 남은 시간(5시간·전체 7일·모델별 7일 쿼터)을 Claude Code 상태줄에 상시 표시합니다. 위의 원라인 설치 명령을 실행한 뒤 Claude Code를 재시작하면 됩니다. `▶`는 현재 라우팅 중인 계정, `⛔`는 레이트리밋 해제 시각입니다. `claude 1`, `claude 2`처럼 상태줄 순서의 계정을 선택할 수 있고, 번호는 실행 시점의 실제 계정 목록에서 읽습니다. 설치 스크립트는 기존 Claude·셸 설정을 백업하고 자신이 추가한 항목만 관리합니다.

## License

MIT
