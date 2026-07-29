"""Guard the structured-error contract.

Tools must return errors via `error_response(...)` (from
`vgc_mcp_core.utils.errors`) so clients can branch on `success`/`error`/`code`,
never a raw ``return {"error": "..."}``. This test greps the tool layer and
fails if a new top-level raw error return sneaks in.

Per-item sub-results inside aggregation loops (e.g. ``results[key] = {"error":
str(e)}``) are allowed — they're nested values, not the tool's return — so we
only flag literal ``return {"error"`` statements.
"""

import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "src" / "vgc_mcp" / "tools"

# Matches a `return {"error"` / `return {'error'` possibly across the newline
# that Black/ruff may put after the brace.
RAW_RETURN = re.compile(r"return\s*\{\s*[\"']error[\"']", re.MULTILINE)


def test_no_raw_error_returns_in_tools():
    offenders = []
    for path in TOOLS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for m in RAW_RETURN.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            offenders.append(f"{path.name}:{line}")
    assert not offenders, (
        "Raw `return {\"error\": ...}` found — use error_response() instead: "
        + ", ".join(offenders)
    )
