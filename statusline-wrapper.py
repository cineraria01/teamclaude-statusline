#!/usr/bin/env python3
"""Run a preserved Claude status line, then the TeamClaude status line."""

import json
import subprocess
import sys
from pathlib import Path


base = Path(__file__).resolve().parent
config_path = base / "teamclaude-statusline-config.json"
statusline_path = base / "statusline-teamclaude.py"
payload = sys.stdin.buffer.read()
outputs = []

try:
    with config_path.open() as f:
        previous = json.load(f).get("previousStatusLine")
except (OSError, ValueError):
    previous = None

command = previous.get("command") if isinstance(previous, dict) else None
if command and command not in (str(Path(__file__).resolve()), str(statusline_path)):
    result = subprocess.run(
        command,
        shell=True,
        executable="/bin/sh",
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.stdout.strip():
        outputs.append(result.stdout.rstrip(b"\r\n"))

result = subprocess.run(
    [sys.executable, str(statusline_path)],
    input=payload,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
)
if result.stdout.strip():
    outputs.append(result.stdout.rstrip(b"\r\n"))

if outputs:
    sys.stdout.buffer.write(b"\n".join(outputs) + b"\n")
