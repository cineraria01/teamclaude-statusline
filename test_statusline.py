#!/usr/bin/env python3
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True

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
assert statusline.render_accounts(["M", "a", "b", "c"]) == (
    "M\na\nb\nc"
)
assert statusline.render_accounts(["a", "b"]) == "a\nb"

statusline.load_status = lambda: {
    "currentAccount": "two@example.com",
    "accounts": [
        {"name": "one@example.com", "quota": {}},
        {"name": "two@example.com", "quota": {}},
    ],
}
statusline.time.time = lambda: now
sys.stdin = __import__("io").StringIO('{"model":{"display_name":"Fable 5"}}')
output = __import__("io").StringIO()
sys.stdout = output
statusline.main()
plain = output.getvalue()
for ansi in (statusline.DIM, statusline.RESET, statusline.BOLD, statusline.CYAN, statusline.MAGENTA):
    plain = plain.replace(ansi, "")
assert plain.startswith("Fable 5\n1 one")
assert "\n▶2 two" in plain
