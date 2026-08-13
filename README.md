# teamclaude-statusline

Live per-account quota usage for the [teamclaude](https://github.com/jung-wan-kim/teamclaude) multi-account Claude proxy, right in your Claude Code status line.

```
Fable 5
     FLEET         x4      pooled  Ses [   7% 6m    ] Wk [ 11% 6h10m  ] Fbl [ 37% 6h10m  ]
  1. alice@exampl  Max 20x active  Ses [  0% 1h30m  ] Wk [ 14% 1d14h  ] Fbl [ 27% 1d14h  ]   D-8
> 2. bob@example.  Max 20x active  Ses [  27% 5m    ] Wk [  8% 6h10m  ] Fbl [ 15% 6h10m  ]  D-25
  3. carol@exampl  Max 20x active  Ses [  0% 3h40m  ] Wk [     -      ] Fbl [ 97% 2d16h  ]   D-9
```

A TUI-style dashboard mirroring the teamclaude TUI. The `FLEET` row pools the
enabled accounts the way the TUI does (average utilization per window, soonest
reset, `+N off` when disabled accounts were excluded). Each account row shows
its billing plan (`Max 20x` / `Pro`), a status column, three quota gauges —
`Ses` 5h session, `Wk` overall 7d, `Fbl` model 7d (Sonnet window when that is
all there is) — with `usage% reset-countdown` inside, and the ESTIMATED next
billing date as a `D-N` countdown (the monthly anniversary of the
subscription's creation, as the TUI computes it; red ≤ 3 days, yellow ≤ 7;
hidden when the subscription is broken — the status column turns red instead).
In a color terminal the gauges are background-filled bars proportional to
usage (the brackets above are the `NO_COLOR` fallback); a gray `-` bar means
teamclaude did not report that window. Every glyph is ASCII so the columns
stay aligned in CJK terminals where ambiguous-width characters (`▶ × ⛔`)
occupy two cells.

- `>` — the account currently serving your requests
- `!HH:MM` in the status column — the account is rate-limited until that time
- `off` — the account is excluded from rotation
- bar colors: green < 70% < yellow < 90% < red
- `TC down` — the proxy isn't running; `teamclaude not installed` — the CLI is missing

## Requirements

- [teamclaude](https://github.com/jung-wan-kim/teamclaude) installed and running — recommended: the [jung-wan-kim/teamclaude](https://github.com/jung-wan-kim/teamclaude) fork with active warm-up and `restart` (`npm install -g github:jung-wan-kim/teamclaude`); the npm original [@karpeleslab/teamclaude](https://www.npmjs.com/package/@karpeleslab/teamclaude) (`npm install -g @karpeleslab/teamclaude`) also works
- Claude Code
- `python3` (stdlib only, 3.8+)

Add at least one account before installing the status line:

```sh
teamclaude login       # browser OAuth
# or: teamclaude import
# or: teamclaude login --api
```

The installer stops without changing Claude settings when TeamClaude is missing or has no accounts. If accounts exist but the proxy is stopped, installation succeeds and prints the command needed to start it.

teamclaude builds without `status --json` (e.g. the [jung-wan-kim/teamclaude](https://github.com/jung-wan-kim/teamclaude) fork) also work: the status line and the numbered selector fall back to the running proxy's `/teamclaude/status` HTTP endpoint and normalize its field names (`modelWeekly` → model 7d bucket, `enabled` → `disabled`). Only the optional quota probe requires a build with the `probe` command.

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

The selector resolves the live account list at launch time, so it contains no hardcoded emails. `>` follows the number pinned for that Claude session instead of TeamClaude's global automatic-route pointer. A running Claude session cannot change accounts in place; start or resume a session with the desired number.

## Configuration

Environment variables read by the script:

| Variable | Default | Meaning |
|---|---|---|
| `TC_SL_CACHE_TTL` | `15` | seconds to cache `teamclaude status --json` output |
| `TC_SL_CACHE_FILE` | `$TMPDIR/tc-statusline-cache-$UID.json` | cache file path |
| `TC_SL_BAR_WIDTH` | `12` | width of each quota gauge in characters (min 6) |
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

teamclaude는 [jung-wan-kim/teamclaude](https://github.com/jung-wan-kim/teamclaude) 포크 설치를 권장합니다(`npm install -g github:jung-wan-kim/teamclaude` — active warm-up과 `restart` 명령 포함). 이 상태줄은 그 다계정 프록시의 계정별 사용량과 갱신까지 남은 시간(5시간·전체 7일·모델별 7일 쿼터), 요금제, 예상 결제일 D-day를 teamclaude TUI와 같은 막대 대시보드 형태로 Claude Code 상태줄에 상시 표시합니다. 최상단 `FLEET` 줄은 활성 계정 전체의 평균 사용률과 가장 빠른 리셋 시각입니다. 위의 원라인 설치 명령을 실행한 뒤 Claude Code를 재시작하면 됩니다. `>`는 현재 라우팅 중인 계정, 상태 칸의 `!시각`은 레이트리밋 해제 시각입니다(CJK 터미널에서 칸이 밀리지 않도록 모든 표시는 ASCII만 사용합니다). `claude 1`, `claude 2`처럼 상태줄 순서의 계정을 선택할 수 있고, 번호는 실행 시점의 실제 계정 목록에서 읽습니다. 설치 스크립트는 기존 Claude·셸 설정을 백업하고 자신이 추가한 항목만 관리합니다.

## License

MIT
