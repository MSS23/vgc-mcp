"""PostToolUse hook: validate regulations.json when it changes.

A trailing comma or duplicated key in regulations.json silently demotes the
loader to its hardcoded fallback — the server still runs, but Reg G/H/MA
disappear from the user's view. This hook parses the file the moment it's
edited so the failure mode is loud instead of silent.

Also enforces invariants:
- Every regulation declares a known `format_system` (or omits it -> mainline)
- `champions` regs declare `legal_pokemon` and SP caps
- `mainline` regs declare `restricted_pokemon` and `banned_pokemon`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REG_PATH = PROJECT_ROOT / "src" / "vgc_mcp_core" / "data" / "regulations.json"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    edited = Path(file_path).resolve()
    if edited != REG_PATH.resolve():
        return 0

    try:
        with REG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[hook:validate_regulations] JSON PARSE FAILED: {e}\n")
        sys.stderr.write("Server will fall back to its built-in default regs!\n")
        return 0

    errors: list[str] = []
    regs = data.get("regulations") or {}
    if not regs:
        errors.append("regulations.json has no `regulations` block.")

    for code, reg in regs.items():
        fmt = reg.get("format_system", "mainline")
        if fmt not in {"mainline", "champions"}:
            errors.append(f"{code}: unknown format_system={fmt!r}")
        if fmt == "champions":
            if "legal_pokemon" not in reg:
                errors.append(f"{code}: champions reg must declare `legal_pokemon`.")
            if reg.get("legality_mode") != "allowlist":
                errors.append(f"{code}: champions reg should set legality_mode='allowlist'.")
            if "sp_per_stat_max" not in reg or "sp_total_max" not in reg:
                errors.append(f"{code}: champions reg must declare SP caps.")
        else:
            for key in ("restricted_pokemon", "banned_pokemon"):
                if key not in reg:
                    errors.append(f"{code}: mainline reg missing `{key}` list.")

    if errors:
        sys.stderr.write("[hook:validate_regulations] regulations.json issues:\n")
        for err in errors:
            sys.stderr.write(f"  - {err}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
