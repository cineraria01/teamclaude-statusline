#!/usr/bin/env python3
"""Claude Code status line for teamclaude multi-account proxy.

Reads the Claude Code session JSON from stdin, queries `teamclaude status
--json` (cached briefly to keep rendering fast), and prints a single line
showing per-account quota usage:

    Fable 5 | ciner --.-- | cindy 0%.100% | >lucy 7%.19% | nextp 3%.46% | @06:30

For each account: <5h usage>%.<7d usage>% (the 7d figure prefers the
model-specific bucket of the current route when available). ">" marks the
account currently serving requests, "@HH:MM" is the current account's 5h
window reset time. Rate-limited accounts show a stop marker with the
unblock time; disabled accounts show "off".

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


def short_name(email):
    local = email.split("@")[0]
    return local[:5].rstrip("._-")


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
    for acct in data.get("accounts", []):
        name = short_name(acct.get("name", "?"))
        q = acct.get("quota") or {}
        five = q.get("unified5h")
        # Prefer the model-specific 7d bucket when the proxy reports one.
        seven = q.get("unified7dFable")
        if seven is None:
            seven = q.get("unified7dSonnet")
        if seven is None:
            seven = q.get("unified7d")

        if acct.get("disabled"):
            parts.append(f"{DIM}{name} off{RESET}")
            continue

        marker = ""
        if acct.get("name") == current:
            marker = f"{CYAN}▶{RESET}"
        badge = ""
        if acct.get("rateLimitedUntil"):
            until = fmt_reset(acct["rateLimitedUntil"])
            badge = f" {RED}⛔{until or ''}{RESET}"
        elif acct.get("status") not in (None, "active"):
            badge = f" {YELLOW}{acct['status']}{RESET}"

        label = f"{BOLD}{name}{RESET}" if acct.get("name") == current else f"{DIM}{name}{RESET}"
        parts.append(f"{marker}{label} {fmt_pct(five)}·{fmt_pct(seven)}{badge}")

    for acct in data.get("accounts", []):
        if acct.get("name") == current:
            reset = fmt_reset((acct.get("quota") or {}).get("unified5hReset"))
            if reset:
                parts.append(f"{DIM}↻{reset}{RESET}")
            break

    print(" │ ".join(parts))


if __name__ == "__main__":
    main()
