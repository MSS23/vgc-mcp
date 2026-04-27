"""One-shot codemod: replace raw `{"error": ...}` dict returns with error_response().

Run:  python scripts/codemod_errors.py

Strategy
--------
We use libcst-style AST traversal via the standard ast/tokenize modules so we
preserve formatting outside the rewritten dict literal. For each `Return` node
whose value is a `dict` literal that contains an "error" key (string value),
we synthesize an equivalent `error_response(code, message, **extras)` call.

Code mapping is heuristic:
  - "Pokemon ... not found" / "Could not find Pokemon" -> POKEMON_NOT_FOUND
  - "Move ... not found"                               -> MOVE_NOT_FOUND
  - "Item ..."                                         -> ITEM_NOT_FOUND
  - "Ability ..."                                      -> ABILITY_NOT_FOUND
  - "Invalid nature"                                   -> INVALID_NATURE
  - "Invalid EVs"                                      -> INVALID_EVS
  - team empty / no pokemon                            -> TEAM_EMPTY
  - team full                                          -> TEAM_FULL
  - "API" / "fetch" / "smogon"                         -> API_ERROR
  - "Maximum" / "Could not build"                      -> INVALID_PARAMETER
  - everything else                                    -> INTERNAL_ERROR

We never reorder or rewrite anything other than the targeted Return statements.
We also ensure each rewritten file imports error_response and ErrorCodes from
vgc_mcp_core.utils.errors.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET_DIRS = [
    REPO / "src" / "vgc_mcp" / "tools",
    REPO / "src" / "vgc_mcp_lite" / "tools",
    REPO / "src" / "vgc_mcp_micro" / "tools",
]


def classify(message: str, has_success_false: bool) -> str:
    m = message.lower()
    if "not found" in m or "could not find" in m or "no pokemon named" in m:
        if "move" in m:
            return "MOVE_NOT_FOUND"
        if "item" in m:
            return "ITEM_NOT_FOUND"
        if "ability" in m:
            return "ABILITY_NOT_FOUND"
        return "POKEMON_NOT_FOUND"
    if "invalid nature" in m or "unknown nature" in m:
        return "INVALID_NATURE"
    if "invalid ev" in m or "exceed 508" in m or "exceed 252" in m:
        return "INVALID_EVS"
    if "no pokemon on team" in m or "team is empty" in m or "team empty" in m:
        return "TEAM_EMPTY"
    if "team is full" in m or "team full" in m or "max 6" in m or "6 pokemon maximum" in m:
        return "TEAM_FULL"
    if "species clause" in m:
        return "SPECIES_CLAUSE"
    if "item clause" in m:
        return "ITEM_CLAUSE"
    if "restricted" in m and "limit" in m:
        return "RESTRICTED_LIMIT"
    if any(k in m for k in ("api ", "smogon", "pokeapi", "fetch", "http")):
        return "API_ERROR"
    if any(k in m for k in ("maximum ", "supported", "must be", "must have", "expected", "required")):
        return "INVALID_PARAMETER"
    if "parse" in m or "format" in m:
        return "PARSE_ERROR"
    return "INTERNAL_ERROR"


# Pattern for `return {"error": ...}` lines that fit on one line OR span lines
# Use regex on the source — it preserves indentation and trailing punctuation.
RE_RETURN_ERROR = re.compile(
    r"""
    (?P<indent>^[ \t]+)return[ \t]*\{
    (?P<body>(?:[^{}]|\{[^{}]*\})*?)   # nested-once dict body
    \}[ \t]*$
    """,
    re.MULTILINE | re.VERBOSE,
)


def parse_kv_pairs(body: str) -> list[tuple[str, str]] | None:
    """Best-effort parse of a flat dict literal body into [(key, value_expr)].

    Returns None if we can't safely parse — caller will skip the rewrite.
    """
    # Wrap in dict() and parse via ast for safety
    try:
        node = ast.parse("{" + body + "}", mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(node, ast.Dict):
        return None

    out: list[tuple[str, str]] = []
    for k, v in zip(node.keys, node.values):
        if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            return None
        out.append((k.value, ast.unparse(v)))
    return out


def rewrite_match(match: re.Match) -> str:
    indent = match.group("indent")
    body = match.group("body")

    pairs = parse_kv_pairs(body)
    if pairs is None:
        return match.group(0)  # leave untouched

    keys = {k for k, _ in pairs}
    if "error" not in keys:
        return match.group(0)

    error_value = next(v for k, v in pairs if k == "error")

    # Strip surrounding whitespace and common leading f-prefix to inspect content
    lit = error_value.strip()
    # Try to extract a readable message string for classification
    try:
        node = ast.parse(lit, mode="eval").body
    except SyntaxError:
        return match.group(0)

    msg_for_class = ""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        msg_for_class = node.value
    elif isinstance(node, ast.JoinedStr):
        msg_for_class = "".join(
            v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)
        )

    has_success_false = any(
        k == "success" and v.strip() in {"False", "false"} for k, v in pairs
    )

    code = classify(msg_for_class, has_success_false)

    # Build extras dict (everything except error/message/success)
    extras = []
    has_message = any(k == "message" for k, _ in pairs)
    message_value = error_value
    for k, v in pairs:
        if k in {"error", "success"}:
            continue
        if k == "message":
            message_value = v.strip()
            continue
        if k.isidentifier():
            extras.append(f"{k}={v.strip()}")
        else:
            extras.append(f'**{{"{k}": {v.strip()}}}')

    if has_message:
        # The original had {"error": "<code>", "message": "<msg>"} pattern
        # In that case, prefer the message and treat error_value as the code if it's a constant
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # If error value already looks like a snake_case code, keep it; else use classified code
            v = node.value
            if re.fullmatch(r"[a-z_]+", v):
                code = v.upper()
            args = [f"ErrorCodes.{code}", message_value]
        else:
            args = [f"ErrorCodes.{code}", message_value]
    else:
        args = [f"ErrorCodes.{code}", message_value]

    extras_str = ("," + " ".join("," in e for e in []) if False else "")  # noop
    args_joined = ", ".join(args + extras)
    new_line = f"{indent}return error_response({args_joined})"
    return new_line


def ensure_imports(src: str) -> str:
    """Make sure error_response and ErrorCodes are imported."""
    if "error_response" in src and "ErrorCodes" in src:
        # Already imported (probably) — verify import line exists
        if re.search(r"from vgc_mcp_core\.utils\.errors import [^\n]*error_response", src) and \
           re.search(r"from vgc_mcp_core\.utils\.errors import [^\n]*ErrorCodes", src):
            return src

    # Find existing errors import to extend, or insert after last `from vgc_mcp_core` import
    m = re.search(r"^from vgc_mcp_core\.utils\.errors import ([^\n]+)$", src, re.MULTILINE)
    if m:
        existing = [s.strip() for s in m.group(1).split(",")]
        for needed in ("error_response", "ErrorCodes"):
            if needed not in existing:
                existing.append(needed)
        new_line = f"from vgc_mcp_core.utils.errors import {', '.join(existing)}"
        return src[: m.start()] + new_line + src[m.end():]

    # No existing errors import — add one after the last vgc_mcp_core import line
    last_core = None
    for m in re.finditer(r"^from vgc_mcp_core[^\n]*$", src, re.MULTILINE):
        last_core = m
    if last_core:
        insert_at = last_core.end()
        return (
            src[:insert_at]
            + "\nfrom vgc_mcp_core.utils.errors import error_response, ErrorCodes"
            + src[insert_at:]
        )

    # Fallback: after first import block
    first_import = re.search(r"^(from |import )[^\n]+$", src, re.MULTILINE)
    if first_import:
        insert_at = first_import.end()
        return (
            src[:insert_at]
            + "\nfrom vgc_mcp_core.utils.errors import error_response, ErrorCodes"
            + src[insert_at:]
        )
    return src


def process(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    new_src, count = RE_RETURN_ERROR.subn(rewrite_match, src)
    if count == 0:
        return 0

    new_src = ensure_imports(new_src)

    # Sanity: make sure the file still parses
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"  [skip] {path}: rewrite produced invalid syntax ({e})", file=sys.stderr)
        return 0

    path.write_text(new_src, encoding="utf-8")
    return count


def main():
    total_files = 0
    total_changes = 0
    for d in TARGET_DIRS:
        for path in sorted(d.glob("*.py")):
            n = process(path)
            if n:
                total_files += 1
                total_changes += n
                print(f"  {path.relative_to(REPO)}: {n} replacements")
    print(f"\nTotal: {total_changes} replacements in {total_files} files.")


if __name__ == "__main__":
    main()
