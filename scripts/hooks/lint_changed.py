"""PostToolUse hook: ruff-check the file Claude just wrote/edited.

Reads the Claude Code hook payload from stdin, looks at `tool_input.file_path`,
and runs `ruff check` only on that single file. Stays silent on success and
prints findings to stderr so they show in the hook output without aborting
the tool. Exits 0 always — we want diagnostics, not a hard block.

Why: keeps the codebase clean without waiting for CI, and is fast (<1s) so it
doesn't slow Claude down between edits.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PREFIX = PROJECT_ROOT / "src"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # No payload — nothing to do

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        return 0

    p = Path(file_path)
    if p.suffix != ".py":
        return 0
    # Only lint files inside this project's src/ — avoid touching unrelated
    # files Claude might edit elsewhere on the user's filesystem.
    try:
        p.resolve().relative_to(SRC_PREFIX)
    except ValueError:
        return 0

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", str(p)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        sys.stderr.write(f"[hook:lint_changed] ruff findings in {p.name}:\n")
        sys.stderr.write(result.stdout or result.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
