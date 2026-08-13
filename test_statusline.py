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
