#!/usr/bin/env python3
"""Claude Code status line for teamclaude multi-account proxy.

Reads the Claude Code session JSON from stdin, queries `teamclaude status
--json` (cached briefly to keep rendering fast), and renders a compact
TUI-style dashboard mirroring the teamclaude TUI: a pooled FLEET row on top,
then one aligned row per account with plan / status columns, background-bar
gauges for the 5h session, 7d overall and 7d model windows (usage% and reset
countdown inside the bar), and the ESTIMATED next-billing countdown (D-8,
D-DAY) on the right:

    Fable 5
       FLEET         x4      pooled Ses ██ 7% 6m ██ Wk ...
    > 1. cindyholic10  Max 20x active Ses ██ 26% 6m ██ ...  D-25

Every cell sticks to ASCII (marker '>', 'x4', '!HH:MM' for rate limits)
because ambiguous-width glyphs (▶ × ⛔) render 2 cells wide in CJK
terminals and would break the column alignment. When the installed
teamclaude build lacks `status --json`, the running proxy's
`/teamclaude/status` endpoint is read directly instead.

The billing estimate is the monthly anniversary of the subscription's
creation (clamped to shorter months), exactly as the teamclaude TUI computes
it; it is hidden when the subscription is not healthy — the red status
column already says billing is broken. The FLEET row pools enabled accounts
the way the TUI does: average utilization per window, soonest reset.

Configuration (environment variables):
    TC_SL_CACHE_TTL   seconds to cache `teamclaude status` output (default 15)
    TC_SL_CACHE_FILE  cache file path (default: $TMPDIR/tc-statusline-cache-$UID.json)
    TC_SL_BAR_WIDTH   width of each quota bar in characters (default 12)
    TC_SL_ROW_COLORS  per-account-row accent colors as comma-separated ANSI
                      SGR codes, cycled (default "36,32,33,35,34,91"; empty
                      restores single-tone rows)
    NO_COLOR          disable ANSI colors when set (https://no-color.org)
"""

import calendar
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone

CACHE = os.environ.get("TC_SL_CACHE_FILE") or os.path.join(
    tempfile.gettempdir(), f"tc-statusline-cache-{os.getuid()}.json"
)
try:
    CACHE_TTL = float(os.environ.get("TC_SL_CACHE_TTL", "15"))
except ValueError:
    CACHE_TTL = 15.0
try:
    BAR_W = max(6, int(os.environ.get("TC_SL_BAR_WIDTH", "12")))
except ValueError:
    BAR_W = 12

COLOR = not os.environ.get("NO_COLOR")
if COLOR:
    DIM = "\033[2m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
else:
    DIM = RESET = BOLD = GREEN = YELLOW = RED = CYAN = MAGENTA = ""

NAME_W = 13
PLAN_W = 7   # "Max 20x"
STATUS_W = 7

# Per-row accent colors: account rows cycle through this palette so each
# line reads in a distinct color. Override with TC_SL_ROW_COLORS
# (comma-separated ANSI SGR codes, e.g. "36,32,33,35,34,31"); set it empty
# to fall back to the old single-tone (DIM) rows. Semantic colors (gauge
# green/yellow/red, status, D-day) are untouched.
if COLOR:
    _row_codes = os.environ.get("TC_SL_ROW_COLORS", "36,32,33,35,34,91")
    ROW_COLORS = [
        f"\033[{c.strip()}m" for c in _row_codes.split(",") if c.strip()
    ]
else:
    ROW_COLORS = []


def row_color(account_number):
    if not ROW_COLORS:
        return DIM
    return ROW_COLORS[(account_number - 1) % len(ROW_COLORS)]


def _normalize(data):
    """Map fields from teamclaude builds whose status JSON predates the
    unified7dFable/disabled naming (e.g. the 1.3.x proxy endpoint)."""
    for acct in data.get("accounts", []):
        if "disabled" not in acct and "enabled" in acct:
            acct["disabled"] = not acct["enabled"]
        q = acct.get("quota") or {}
        if "unified7dFable" not in q:
            model_weekly = (q.get("modelWeekly") or {}).get("7d_oi") or {}
            if "utilization" in model_weekly:
                q["unified7dFable"] = model_weekly.get("utilization")
                q["unified7dFableReset"] = model_weekly.get("reset")
                acct["quota"] = q
    return data


def _http_status():
    """Fallback for teamclaude builds without `status --json`: read the
    running proxy's /teamclaude/status endpoint directly."""
    import urllib.request

    port = 3456
    try:
        with open(os.path.expanduser("~/.config/teamclaude.json")) as f:
            port = (json.load(f).get("proxy") or {}).get("port") or 3456
    except (OSError, ValueError):
        pass
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/teamclaude/status", timeout=3
    ) as res:
        return json.load(res)


def load_status():
    try:
        st = os.stat(CACHE)
        if time.time() - st.st_mtime < CACHE_TTL:
            with open(CACHE) as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    data = None
    try:
        out = subprocess.run(
            ["teamclaude", "status", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            data = json.loads(out.stdout)
    except FileNotFoundError:
        return "missing"
    except Exception:
        data = None
    if data is None:
        try:
            data = _http_status()
        except Exception:
            return None
    try:
        data = _normalize(data)
        tmp = CACHE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, CACHE)
    except Exception:
        pass
    return data


def plan_label(acct):
    """Billing-plan column ('Max 20x', 'Max 5x', 'Pro'), mirroring the TUI's
    tierLabel: the rate_limit_tier multiplier first, then the plan flags."""
    profile = acct.get("profile") or {}
    tier = profile.get("rateLimitTier") or ""
    multiplier = tier.rsplit("_", 1)[-1]
    if multiplier.endswith("x") and multiplier[:-1].isdigit():
        return f"Max {multiplier}"
    if profile.get("hasClaudeMax") or profile.get("orgType") == "claude_max":
        return "Max"
    if profile.get("hasClaudePro") or profile.get("orgType") == "claude_pro":
        return "Pro"
    return tier.removeprefix("default_") or None


def fmt_renewal(acct, today=None):
    """ESTIMATED next-billing countdown (D-8, D-DAY), mirroring the teamclaude
    TUI: monthly billing renews on the subscription-creation day-of-month
    (clamped to shorter months). Hidden when the subscription is not healthy —
    the red status column already says billing is broken."""
    profile = acct.get("profile") or {}
    if profile.get("subscriptionStatus") not in (None, "active", "trialing"):
        return None
    created_iso = profile.get("subscriptionCreatedAt")
    if not created_iso:
        return None
    try:
        created = datetime.fromisoformat(str(created_iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if today is None:
        today = date.today()
    day = created.astimezone().day
    year, month = today.year, today.month
    clamp = lambda y, m: min(day, calendar.monthrange(y, m)[1])
    candidate = date(year, month, clamp(year, month))
    if candidate < today:
        month += 1
        if month > 12:
            month, year = 1, year + 1
        candidate = date(year, month, clamp(year, month))
    days = (candidate - today).days
    color = RED if days <= 3 else YELLOW if days <= 7 else GREEN
    label = "D-DAY" if days <= 0 else f"D-{days}"
    return f"{color}{label.rjust(5)}{RESET}"


def _reset_ts(value):
    """Reset value (epoch millis or ISO string) → epoch millis, else None."""
    try:
        if isinstance(value, (int, float)):
            return value
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).timestamp() * 1000
    except (TypeError, ValueError):
        return None


def pool_quota(accounts):
    """Pool the fleet's quota the way the teamclaude TUI does: average
    utilization over enabled, non-errored accounts (unmeasured windows are
    skipped, not counted as zero), soonest reset per window. None for fewer
    than two poolable accounts — the single row already is the total."""
    pool = [
        a for a in accounts
        if not a.get("disabled") and a.get("status") != "error"
    ]
    if len(pool) < 2:
        return None

    def agg(value_key, reset_key):
        vals, resets = [], []
        for acct in pool:
            q = acct.get("quota") or {}
            v = q.get(value_key)
            if v is None:
                continue
            vals.append(v)
            ts = _reset_ts(q.get(reset_key))
            if ts:
                resets.append(ts)
        if not vals:
            return None, None
        return sum(vals) / len(vals), (min(resets) if resets else None)

    return {
        "size": len(pool),
        "off": len(accounts) - len(pool),
        "five": agg("unified5h", "unified5hReset"),
        "seven": agg("unified7d", "unified7dReset"),
        "fable": agg("unified7dFable", "unified7dFableReset"),
    }


def fmt_reset(value):
    """Accepts epoch millis (int) or an ISO-8601 string; returns local HH:MM."""
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M")
    except (ValueError, OSError):
        return None


def fmt_remaining(value, now=None):
    """Return a compact reset countdown such as 1d16h or 2h3m."""
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            reset_at = value / 1000
        else:
            reset_at = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            ).timestamp()
        seconds = reset_at - (time.time() if now is None else now)
        if seconds <= 0:
            return "now"
        minutes = int(seconds // 60)
        if minutes == 0:
            return "<1m"
        days, minutes = divmod(minutes, 24 * 60)
        hours, minutes = divmod(minutes, 60)
        if days:
            return f"{days}d{hours}h" if hours else f"{days}d"
        if hours:
            return f"{hours}h{minutes}m" if minutes else f"{hours}h"
        return f"{minutes}m"
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def bar(ratio, reset, now, width=None):
    """TUI-style quota gauge: `width` background-colored cells, filled
    proportionally to usage (green <70%, yellow <90%, red beyond) over a gray
    remainder, with 'usage% countdown' centered inside. No-data windows render
    an all-gray bar. Without colors, degrades to the bracketed label."""
    if width is None:
        width = BAR_W
    remaining = fmt_remaining(reset, now)

    if ratio is None:
        text = (remaining or "-")[:width].center(width)
        return f"\033[100;37m{text}{RESET}" if COLOR else f"[{text}]"

    ratio = max(0.0, min(1.0, ratio))
    pct = f"{round(ratio * 100)}%"
    label = (
        f"{pct} {remaining}"
        if remaining and len(pct) + 1 + len(remaining) <= width
        else pct
    )
    text = label[:width].center(width)
    if not COLOR:
        return f"[{text}]"
    filled = round(ratio * width)
    bg = 42 if ratio < 0.7 else 43 if ratio < 0.9 else 41
    out = ""
    if filled:
        out += f"\033[{bg};97m{text[:filled]}"
    if filled < width:
        out += f"\033[100;37m{text[filled:]}"
    return out + RESET


def bars_cell(q, now, label_color=None):
    """The three aligned gauges of a row: 5h session, 7d overall, 7d model
    (Fable, falling back to the Sonnet window when that is all there is)."""
    lc = DIM if label_color is None else label_color
    model_seven = q.get("unified7dFable")
    model_seven_reset = q.get("unified7dFableReset")
    if model_seven is None and q.get("unified7dSonnet") is not None:
        model_seven = q.get("unified7dSonnet")
        model_seven_reset = q.get("unified7dSonnetReset")
    return (
        f"{lc}Ses{RESET} {bar(q.get('unified5h'), q.get('unified5hReset'), now)} "
        f"{lc}Wk{RESET} {bar(q.get('unified7d'), q.get('unified7dReset'), now)} "
        f"{lc}Fbl{RESET} {bar(model_seven, model_seven_reset, now)}"
    )


def status_cell(acct):
    """Fixed-width status column: rate-limited stop marker first, then
    disabled, then a non-active account state, then the subscription status
    (red when billing is broken, green when active)."""
    if acct.get("rateLimitedUntil"):
        until = fmt_reset(acct["rateLimitedUntil"]) or ""
        return f"{RED}{f'!{until}'[:STATUS_W].ljust(STATUS_W)}{RESET}"
    if acct.get("disabled"):
        return f"{DIM}{'off'.ljust(STATUS_W)}{RESET}"
    if acct.get("status") not in (None, "active"):
        return f"{YELLOW}{str(acct['status'])[:STATUS_W].ljust(STATUS_W)}{RESET}"
    sub = (acct.get("profile") or {}).get("subscriptionStatus")
    if sub and sub not in ("active", "trialing"):
        return f"{RED}{sub[:STATUS_W].ljust(STATUS_W)}{RESET}"
    return f"{GREEN}{'active'.ljust(STATUS_W)}{RESET}"


def main():
    try:
        session = json.load(sys.stdin)
    except Exception:
        session = {}
    model = (session.get("model") or {}).get("display_name") or ""

    parts = []
    if model:
        parts.append(f"{MAGENTA}{model}{RESET}")

    data = load_status()
    if data == "missing":
        parts.append(f"{DIM}teamclaude not installed{RESET}")
        print(" │ ".join(parts))
        return
    if not data:
        parts.append(f"{RED}TC down{RESET}")
        print(" │ ".join(parts))
        return

    current = data.get("currentAccount")
    try:
        pinned_number = int(os.environ.get("TEAMCLAUDE_STATUSLINE_INDEX", ""))
        if pinned_number < 1:
            pinned_number = None
    except ValueError:
        pinned_number = None
    now = time.time()
    accounts = data.get("accounts", [])

    pooled = pool_quota(accounts)
    # The plan column must fit the FLEET size label ("x3 +1 off" is wider
    # than "Max 20x") — ljust never truncates, so a fixed width would shift
    # the FLEET row out of column whenever an account is off.
    plan_w = PLAN_W
    if pooled:
        size = f"x{pooled['size']}" + (
            f" +{pooled['off']} off" if pooled["off"] else ""
        )
        plan_w = max(plan_w, len(size))
        # The gutter is wrapped in ANSI codes so the raw line does not begin
        # with whitespace — Claude Code trims leading spaces off status-line
        # rows, which would shift the FLEET row out of column.
        parts.append(
            f"{DIM}     {RESET}{BOLD}{'FLEET'.ljust(NAME_W)}{RESET} "
            f"{DIM}{size.ljust(plan_w)}{RESET} "
            f"{DIM}{'pooled'.ljust(STATUS_W)}{RESET} "
            f"{DIM}Ses{RESET} {bar(*pooled['five'], now)} "
            f"{DIM}Wk{RESET} {bar(*pooled['seven'], now)} "
            f"{DIM}Fbl{RESET} {bar(*pooled['fable'], now)}"
        )

    for account_number, acct in enumerate(accounts, 1):
        name = (acct.get("name") or "?")[:NAME_W]
        is_current = (
            account_number == pinned_number
            if pinned_number is not None
            else acct.get("name") == current
        )
        accent = row_color(account_number)
        # Same trim guard as the FLEET gutter for the blank marker cell.
        marker = f"{accent}>{RESET}" if is_current else f"{DIM} {RESET}"
        name_cell = (
            f"{BOLD}{accent}{name.ljust(NAME_W)}{RESET}"
            if is_current
            else f"{accent}{name.ljust(NAME_W)}{RESET}"
        )
        plan = (plan_label(acct) or "")[:plan_w]
        row = (
            f"{marker}{accent}{account_number:>2}.{RESET} {name_cell} "
            f"{accent}{plan.ljust(plan_w)}{RESET} {status_cell(acct)} "
            f"{bars_cell(acct.get('quota') or {}, now, accent)}"
        )
        renewal = fmt_renewal(acct)
        if renewal:
            row += f" {renewal}"
        parts.append(row)

    print("\n".join(parts))


if __name__ == "__main__":
    main()
