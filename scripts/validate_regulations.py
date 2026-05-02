"""Strict validator for regulations.json — used by CI.

Unlike the PostToolUse hook, this exits non-zero on any failure. Run it
directly (`python scripts/validate_regulations.py`) or wire it into the CI
pipeline.

Validates:
1. JSON parses
2. Schema (regulations.schema.json) — only if `jsonschema` is importable;
   we skip silently if it isn't, so dev environments without the optional
   dep don't block.
3. Per-regulation invariants (champions vs mainline shapes)
4. Router alias consistency: every key declared in regulations.json must
   resolve via `resolve_regulation`, and every alias in the router must
   point at a known reg code (this is the drift guard).
5. current_regulation is a defined regulation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REG_PATH = PROJECT_ROOT / "src" / "vgc_mcp_core" / "data" / "regulations.json"
SCHEMA_PATH = PROJECT_ROOT / "src" / "vgc_mcp_core" / "data" / "regulations.schema.json"


def _try_jsonschema_validate(data: dict, errors: list[str]) -> None:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return
    if not SCHEMA_PATH.exists():
        return
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(data), key=lambda e: e.path):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"schema: {loc}: {err.message}")


def _validate_invariants(data: dict, errors: list[str]) -> None:
    regs = data.get("regulations") or {}
    if not regs:
        errors.append("regulations.json has no `regulations` block.")
        return

    current = data.get("current_regulation")
    if current and current not in regs:
        errors.append(f"current_regulation={current!r} is not defined in regulations.")

    for code, reg in regs.items():
        fmt = reg.get("format_system", "mainline")
        if fmt not in {"mainline", "champions"}:
            errors.append(f"{code}: unknown format_system={fmt!r}")
            continue

        if fmt == "champions":
            if not reg.get("legal_pokemon"):
                errors.append(f"{code}: champions reg must declare non-empty `legal_pokemon`.")
            if reg.get("legality_mode") != "allowlist":
                errors.append(f"{code}: champions reg must set legality_mode='allowlist'.")
            for cap in ("sp_per_stat_max", "sp_total_max"):
                if cap not in reg:
                    errors.append(f"{code}: champions reg missing {cap}.")
        else:  # mainline
            for key in ("restricted_pokemon", "banned_pokemon", "restricted_limit"):
                if key not in reg:
                    errors.append(f"{code}: mainline reg missing `{key}`.")


def _validate_router_consistency(data: dict, errors: list[str]) -> None:
    """Make sure every reg in JSON resolves via the router, and vice-versa."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from vgc_mcp_core.rules.regulation_router import (
            _ALIASES,
            resolve_regulation,
        )
    except Exception as e:
        errors.append(f"router: cannot import regulation_router: {e}")
        return

    regs = set((data.get("regulations") or {}).keys())

    for code in regs:
        # Self-resolution: code must resolve to itself.
        resolved = resolve_regulation(code, None)
        if resolved != code:
            errors.append(
                f"router: regulation {code!r} does not self-resolve "
                f"(got {resolved!r})."
            )

    for alias, target in _ALIASES.items():
        if target not in regs:
            errors.append(
                f"router: alias {alias!r} -> {target!r} but {target!r} is not "
                "in regulations.json."
            )


def main() -> int:
    if not REG_PATH.exists():
        sys.stderr.write(f"validate_regulations: {REG_PATH} not found.\n")
        return 1

    try:
        data = json.loads(REG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.stderr.write(f"validate_regulations: JSON parse failed: {e}\n")
        return 2

    errors: list[str] = []
    _try_jsonschema_validate(data, errors)
    _validate_invariants(data, errors)
    _validate_router_consistency(data, errors)

    if errors:
        sys.stderr.write("validate_regulations: regulations.json has issues:\n")
        for err in errors:
            sys.stderr.write(f"  - {err}\n")
        return 3

    print(f"validate_regulations: OK ({len(data.get('regulations') or {})} regulations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
