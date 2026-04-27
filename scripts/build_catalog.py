"""Regenerate docs/tools-catalog.md from the running full server.

Run:  PYTHONPATH=src python scripts/build_catalog.py

Walks every registered MCP tool, groups by source module, writes a markdown
catalog. Useful as a discovery aid for users / smaller LLMs that can't see
the full tool list at once.
"""

from __future__ import annotations

import io
import sys
from collections import defaultdict
from pathlib import Path


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    from vgc_mcp.server import mcp  # noqa: PLC0415  (must run after PYTHONPATH set)

    tools = mcp._tool_manager._tools
    out_path = Path("docs/tools-catalog.md")

    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for name, tool in tools.items():
        mod = getattr(tool.fn, "__module__", "unknown").replace("vgc_mcp.tools.", "")
        desc = (tool.description or "").strip().split("\n")[0][:140]
        groups[mod].append((name, desc))

    lines: list[str] = []
    lines.append("# Tool Catalog")
    lines.append("")
    lines.append(
        f"Auto-generated from the running server. **{len(tools)} tools** "
        "organized by module."
    )
    lines.append("")
    lines.append("To regenerate: `PYTHONPATH=src python scripts/build_catalog.py`")
    lines.append("")

    for mod in sorted(groups):
        lines.append(f"## {mod}  ({len(groups[mod])} tools)")
        lines.append("")
        for name, desc in sorted(groups[mod]):
            lines.append(f"- **`{name}`** — {desc}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path} — {len(tools)} tools across {len(groups)} modules.")


if __name__ == "__main__":
    main()
