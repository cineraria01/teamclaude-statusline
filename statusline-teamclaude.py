#!/usr/bin/env python3
"""Claude Code status line for teamclaude multi-account proxy.

Reads the Claude Code session JSON from stdin, queries `teamclaude status
--json` (cached briefly to keep rendering fast), and prints compact lines
showing per-account quota usage:

    Fable 5
    1 alice@example.com [5h -- ↻-- · O -- ↻-- · F -- ↻--]
    >2 bob@example.com [5h 7% ↻2h · O 58% ↻1d16h · F 19% ↻2d18h]

For each usable account: 5h usage@time-left, overall 7d usage@time-left, and
model 7d usage@time-left (Fable, falling back to Sonnet when available).
Accounts whose Fable quota reached teamclaude's switch threshold collapse to
`O overall-usage · F stop reset-time`, because they remain usable for Opus.
">" marks the account currently serving requests. Rate-limited accounts show
a stop marker with the unblock time; disabled accounts show "off".

Configuration (environment variables):
    TC_SL_CACHE_TTL   seconds to cache `teamclaude status` output (default 15)
    TC_SL_CACHE_FILE  cache file path (default: $TMPDIR/tc-statusline-cache-$UID.json)
    NO_COLOR          disable ANSI colors when set (https://no-color.org)
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

CACHE = os.environ.get("TC_SL_CACHE_FILE") or os.path.join(
    tempfile.gettempdir(), f"tc-statusline-cache-{os.getuid()}.json"
)
try:
    CACHE_TTL = float(os.environ.get("TC_SL_CACHE_TTL", "15"))
except ValueError:
    CACHE_TTL = 15.0

if os.environ.get("NO_COLOR"):
    DIM = RESET = BOLD = GREEN = YELLOW = RED = CYAN = MAGENTA = ""
else:
    DIM = "\033[2m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"

def load_status():
    try:
        st = os.stat(CACHE)
        if time.time() - st.st_mtime < CACHE_TTL:
            with open(CACHE) as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    try:
        out = subprocess.run(
            ["teamclaude", "status", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout)
        tmp = CACHE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, CACHE)
        return data
    except FileNotFoundError:
        return "missing"
    except Exception:
        return None


def pct_color(frac):
    if frac is None:
        return DIM
    if frac >= 0.9:
        return RED
    if frac >= 0.7:
        return YELLOW
    return GREEN


def fmt_pct(frac):
    if frac is None:
        return f"{DIM}--{RESET}"
    return f"{pct_color(frac)}{round(frac * 100)}%{RESET}"


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
        return "--"
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
        return "--"


def fmt_window(label, usage, reset, now):
    return (
        f"{DIM}{label}{RESET} {fmt_pct(usage)} "
        f"{DIM}↻{fmt_remaining(reset, now)}{RESET}"
    )


def render_accounts(parts):
    """Render the model and every account on separate lines."""
    return "\n".join(parts)


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
    switch_threshold = data.get("switchThreshold") or 0.98
    now = time.time()
    for account_number, acct in enumerate(data.get("accounts", []), 1):
        name = acct.get("name", "?")
        numbered_name = f"{account_number} {name}"
        is_current = (
            account_number == pinned_number
            if pinned_number is not None
            else acct.get("name") == current
        )
        marker = f"{CYAN}▶{RESET}" if is_current else ""
        label = (
            f"{BOLD}{numbered_name}{RESET}"
            if is_current
            else f"{DIM}{numbered_name}{RESET}"
        )
        q = acct.get("quota") or {}
        five = q.get("unified5h")
        five_reset = q.get("unified5hReset")
        seven = q.get("unified7d")
        seven_reset = q.get("unified7dReset")
        # Prefer the model-specific 7d bucket when the proxy reports one.
        model_seven = q.get("unified7dFable")
        model_seven_reset = q.get("unified7dFableReset")
        model_label = "F"
        if model_seven is None:
            model_seven = q.get("unified7dSonnet")
            model_seven_reset = q.get("unified7dSonnetReset")
            model_label = "S"

        if acct.get("disabled"):
            parts.append(f"{marker}{label} {DIM}off{RESET}")
            continue

        badge = ""
        if acct.get("rateLimitedUntil"):
            until = fmt_reset(acct["rateLimitedUntil"])
            badge = f" {RED}⛔{until or ''}{RESET}"
        elif acct.get("status") not in (None, "active"):
            badge = f" {YELLOW}{acct['status']}{RESET}"

        if model_seven is not None and model_seven >= switch_threshold:
            opus = fmt_pct(seven)
            parts.append(
                f"{marker}{label} {DIM}O{RESET} {opus} · "
                f"{RED}{model_label}⛔{RESET} "
                f"{DIM}↻{fmt_remaining(model_seven_reset, now)}{RESET}{badge}"
            )
            continue
        parts.append(
            f"{marker}{label} {DIM}[{RESET}"
            f"{fmt_window('5h', five, five_reset, now)} · "
            f"{fmt_window('O', seven, seven_reset, now)} · "
            f"{fmt_window(model_label, model_seven, model_seven_reset, now)}"
            f"{DIM}]{RESET}{badge}"
        )

    print(render_accounts(parts))


if __name__ == "__main__":
    main()
