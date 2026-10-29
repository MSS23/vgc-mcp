"""User-facing text must only tell people to use tools that exist."""

import ast
import asyncio
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

# "Use 'name'", "use `name`", "Try name to ..." etc.
_REFERENCE = re.compile(
    r"""\b(?:[Uu]se|[Cc]all|[Tt]ry|[Rr]un)\s+"""
    r"""(?:[`'"]([a-z]+(?:_[a-z0-9]+)+)[`'"]|([a-z]+(?:_[a-z0-9]+)+)\s+(?:to|with)\b)"""
)


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _user_strings(path: Path):
    """String literals that are not docstrings (messages, hints, markdown)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstring_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            yield node.lineno, node.value


def test_every_tool_named_in_user_text_is_registered():
    from vgc_mcp.server import mcp

    registered = {t.name for t in asyncio.run(mcp.list_tools())}
    missing = []
    for path in SRC.rglob("*.py"):
        for lineno, text in _user_strings(path):
            for match in _REFERENCE.finditer(text):
                name = match.group(1) or match.group(2)
                if name not in registered:
                    missing.append(f"{path.relative_to(SRC)}:{lineno} -> {name}")
    assert not missing, "text names tools that do not exist:\n" + "\n".join(missing)


def test_user_text_never_points_at_a_deprecated_alias():
    """Hints and markdown should name the canonical tool, not an alias."""
    from vgc_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    aliases = {
        t.name for t in tools if (t.description or "").lstrip().startswith("Deprecated alias")
    }
    offenders = []
    for path in SRC.rglob("*.py"):
        for lineno, value in _user_strings(path):
            for match in _REFERENCE.finditer(value):
                name = match.group(1) or match.group(2)
                if name in aliases:
                    offenders.append(f"{path.relative_to(SRC)}:{lineno} -> {name}")
    assert not offenders, "text points at deprecated aliases:\n" + "\n".join(offenders)
