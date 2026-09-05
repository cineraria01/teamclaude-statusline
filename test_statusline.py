#!/usr/bin/env python3
import importlib.util
import io
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
# Deterministic, width-stable output: no ANSI, and a fixed timezone so the
# renewal-anniversary math (which uses local dates) is reproducible.
os.environ["NO_COLOR"] = "1"
os.environ["TZ"] = "UTC"
# Row indices below assume packed rows; the spacer row is exercised at the end.
os.environ["TC_SL_ROW_GAP"] = "0"
time.tzset()

spec = importlib.util.spec_from_file_location(
    "statusline", Path(__file__).with_name("statusline-teamclaude.py")
)
statusline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(statusline)

now = 1_000_000
assert statusline.fmt_remaining((now + 3661) * 1000, now) == "1h1m"
assert statusline.fmt_remaining((now + 4 * 3600) * 1000, now) == "4h"
assert statusline.fmt_remaining((now + 90061) * 1000, now) == "1d1h"
assert statusline.fmt_remaining(now * 1000, now) == "now"
assert statusline.fmt_remaining(None, now) is None

# Account rows are chronological by the Fable reset. Their original
# numbers stay attached so `claude N` keeps selecting the account shown as N.
ordered = statusline.accounts_by_fable_reset([
    {"quota": {"unified7dFableReset": (now + 300) * 1000}},
    {"quota": {"unified7dFableReset": (now + 100) * 1000}},
    {"quota": {"unified7dFableReset": (now - 1) * 1000}},
    {"quota": {"unified7dFableReset": (now + 200) * 1000}},
    {"quota": {}},
], now)
assert [number for number, _ in ordered] == [2, 4, 1, 3, 5]

# _normalize maps 1.3.x proxy-endpoint field names onto the expected ones and
# leaves already-normalized data untouched.
normalized = statusline._normalize({
    "accounts": [
        {
            "name": "legacy@example.com",
            "enabled": False,
            "quota": {"modelWeekly": {"7d_oi": {"utilization": 0.27, "reset": 123}}},
        },
        {
            "name": "modern@example.com",
            "disabled": False,
            "quota": {"unified7dFable": 0.5, "unified7dFableReset": 456},
        },
    ]
})
legacy, modern = normalized["accounts"]
assert legacy["disabled"] is True
assert legacy["quota"]["unified7dFable"] == 0.27
assert legacy["quota"]["unified7dFableReset"] == 123
assert modern["disabled"] is False
assert modern["quota"]["unified7dFable"] == 0.5

# Billing-plan column mirrors the TUI's tierLabel.
assert statusline.plan_label(
    {"profile": {"rateLimitTier": "default_claude_max_20x"}}
) == "Max 20x"
assert statusline.plan_label({"profile": {"hasClaudePro": True}}) == "Pro"
assert statusline.plan_label({"profile": {"hasClaudeMax": True}}) == "Max"
assert statusline.plan_label({}) is None

# Renewal estimate: monthly anniversary of the subscription's creation,
# clamped to shorter months; today counts as D-DAY; hidden for broken
# subscriptions and unknown creation dates.
assert statusline.fmt_renewal(
    {"profile": {"subscriptionCreatedAt": "2025-01-31T12:00:00Z"}},
    today=date(2026, 2, 10),
).strip() == "D-18"
assert statusline.fmt_renewal(
    {"profile": {"subscriptionCreatedAt": "2025-08-14T01:00:00Z"}},
    today=date(2026, 8, 14),
).strip() == "D-DAY"
assert statusline.fmt_renewal(
    {"profile": {"subscriptionStatus": "canceled",
                 "subscriptionCreatedAt": "2025-01-01T00:00:00Z"}}
) is None
assert statusline.fmt_renewal({"profile": {}}) is None

# Fleet pooling: disabled/errored accounts are excluded, unmeasured windows
# are skipped (not counted as zero), the reset is the soonest in the pool,
# and a pool of one is no pool at all.
accounts = [
    {"disabled": False, "quota": {
        "unified5h": 0.2, "unified5hReset": 2_000_000_000,
        "unified7d": 0.1, "unified7dFable": None,
    }},
    {"disabled": True, "quota": {"unified5h": 0.9}},
    {"disabled": False, "status": "error", "quota": {"unified5h": 0.9}},
    {"disabled": False, "quota": {
        "unified5h": 0.4, "unified5hReset": 1_999_999_000,
        "unified7d": None, "unified7dFable": 0.5,
    }},
]
pooled = statusline.pool_quota(accounts)
assert pooled["size"] == 2 and pooled["off"] == 2
assert round(pooled["five"][0], 6) == 0.3
assert pooled["five"][1] == 1_999_999_000
assert pooled["seven"] == (0.1, None)
assert pooled["fable"] == (0.5, None)
assert statusline.pool_quota(accounts[:2]) is None

# Bars degrade to a bracketed centered label without colors; the visible
# width is stable regardless of the data inside.
assert statusline.bar(None, None, now, width=8) == "[   -    ]"
assert statusline.bar(0.26, (now + 120) * 1000, now, width=10) == "[  26% 2m  ]"
assert statusline.bar(1.7, None, now, width=6) == "[ 100% ]"

assert statusline.status_cell({}).strip() == "active"
assert statusline.status_cell({"disabled": True}).strip() == "off"
assert statusline.status_cell({"rateLimitedUntil": now * 1000}).startswith("!")
assert statusline.status_cell(
    {"profile": {"subscriptionStatus": "canceled"}}
).strip() == "cancele"

statusline.load_status = lambda: {
    "currentAccount": "two@example.com",
    "accounts": [
        {"name": "one@example.com", "quota": {}},
        {"name": "two@example.com", "quota": {}},
    ],
}
statusline.time.time = lambda: now
os.environ["TEAMCLAUDE_STATUSLINE_INDEX"] = "1"
sys.stdin = io.StringIO('{"model":{"display_name":"Fable 5"}}')
output = io.StringIO()
sys.stdout = output
statusline.main()
sys.stdout = sys.__stdout__
lines = output.getvalue().splitlines()
assert lines[0] == "Fable 5"
assert lines[1].lstrip().startswith("FLEET")
assert lines[2].startswith("> 1. one@example.c")
assert lines[3].startswith("  2. two@example.c")
# Column alignment: every dashboard row places its gauges at the same offset.
assert len({line.index("Ses") for line in lines[1:]}) == 1

# Regression: an off account widens the FLEET size label ("x2 +1 off") past
# the fixed plan column ("Max 20x"), and ljust never truncates — the plan
# column must stretch to fit or the FLEET row shifts out of column.
statusline.load_status = lambda: {
    "currentAccount": "one@example.com",
    "accounts": [
        {"name": "one@example.com", "quota": {}},
        {"name": "two@example.com", "quota": {}},
        {"name": "off@example.com", "disabled": True, "quota": {}},
    ],
}
sys.stdin = io.StringIO("{}")
output = io.StringIO()
sys.stdout = output
statusline.main()
sys.stdout = sys.__stdout__
lines = output.getvalue().splitlines()
assert "+1 off" in lines[0]
assert len({line.index("Ses") for line in lines}) == 1

# Row gap: with TC_SL_ROW_GAP on (the default), a spacer row sits between
# every dashboard row. Claude Code discards empty/whitespace-only rows and
# trims leading spaces, so the spacer must be non-whitespace yet invisible —
# BRAILLE PATTERN BLANK — and must never shift the gauge columns.
os.environ["TC_SL_ROW_GAP"] = "1"
gapped = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gapped)
assert gapped.ROW_GAP is True
gapped.load_status = lambda: {
    "currentAccount": "one@example.com",
    "accounts": [
        {"name": "one@example.com", "quota": {}},
        {"name": "two@example.com", "quota": {}},
    ],
}
gapped.time.time = lambda: now
os.environ.pop("TEAMCLAUDE_STATUSLINE_INDEX", None)
sys.stdin = io.StringIO('{"model":{"display_name":"Fable 5"}}')
output = io.StringIO()
sys.stdout = output
gapped.main()
sys.stdout = sys.__stdout__
lines = output.getvalue().splitlines()
assert lines[0] == "Fable 5"
assert lines[1] == "\u2800" and lines[1].strip() != "" and "\u2800".strip() == "\u2800"
assert lines[2].lstrip().startswith("FLEET")
assert lines[3] == "\u2800"
assert lines[4].startswith("> 1. one@example.c")
assert lines[5] == "\u2800"
assert lines[6].startswith("  2. two@example.c")
assert len(lines) == 7
assert len({line.index("Ses") for line in lines[2::2]}) == 1
os.environ["TC_SL_ROW_GAP"] = "off"
packed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packed)
assert packed.ROW_GAP is False and packed.ROW_SEP == "\n"

print("ok")

# Row backgrounds: with colors on, every dashboard row (not the model header,
# not the spacers) is painted with a cycled background, every RESET inside
# the row re-arms it, and rows are padded to one visible width so the stripes
# form a clean rectangle. Header/spacer rows stay unpainted.
os.environ.pop("NO_COLOR")
os.environ["TC_SL_ROW_GAP"] = "1"
os.environ["TC_SL_ROW_BG"] = "48;5;236,-"
colored = importlib.util.module_from_spec(spec)
spec.loader.exec_module(colored)
assert colored.ROW_BGS == ["\033[48;5;236m", ""]
colored.load_status = lambda: {
    "currentAccount": "one@example.com",
    "accounts": [
        {"name": "one@example.com", "quota": {"unified5h": 0.5},
         "profile": {"subscriptionCreatedAt": "2025-01-01T00:00:00Z"}},
        {"name": "two@example.com", "quota": {}},
        {"name": "three@example.com", "quota": {}},
    ],
}
colored.time.time = lambda: now
sys.stdin = io.StringIO('{"model":{"display_name":"Fable 5"}}')
output = io.StringIO()
sys.stdout = output
colored.main()
sys.stdout = sys.__stdout__
lines = output.getvalue().splitlines()
BG = "\033[48;5;236m"
assert not lines[0].startswith(BG) and lines[1] == f"\033[2m\u2800\033[0m"
fleet, one, two, three = lines[2], lines[4], lines[6], lines[8]
assert fleet.startswith(BG) and fleet.endswith("\033[0m")
assert not one.startswith(BG)            # "-" slot: unpainted
assert two.startswith(BG) and not three.startswith(BG)
# every reset inside a painted row is immediately followed by the row bg
inner = fleet[len(BG):-len("\033[0m")]
assert "\033[0m" not in inner.replace("\033[0m" + BG, "")
assert len({colored.visible_len(r) for r in (fleet, one, two, three)}) == 1
os.environ["NO_COLOR"] = "1"
print("bg ok")

