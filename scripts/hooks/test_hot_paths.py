"""PostToolUse hook: run targeted tests when load-bearing files change.

Watches a small set of "hot" files where a regression would silently break
core functionality (stat dispatch, regulation routing, Champions support).
When one of them is edited, runs a targeted pytest slice (~3s) and reports
failures via stderr.

Stays silent on success and only runs for in-scope edits, so the typical
cost is zero. Triggers only on the files that are actually load-bearing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Each entry: (hot_file_relative_to_project_root, [test_paths_to_run])
HOT_PATHS: dict[str, list[str]] = {
    "src/vgc_mcp_core/models/pokemon.py": [
        "tests/champions/test_stat_point_spread.py",
        "tests/champions/test_stat_calc.py",
    ],
    "src/vgc_mcp_core/calc/stats.py": [
        "tests/champions/test_stat_calc.py",
        "tests/test_stats.py",
    ],
    "src/vgc_mcp_core/calc/stats_champions.py": [
        "tests/champions/test_stat_calc.py",
        "tests/champions/test_damage_calc.py",
    ],
    "src/vgc_mcp_core/calc/champions_optimization.py": [
        "tests/champions/test_optimization.py",
    ],
    "src/vgc_mcp_core/calc/damage.py": [
        "tests/champions/test_damage_calc.py",
    ],
    "src/vgc_mcp_core/rules/regulation_loader.py": [
        "tests/champions/test_regulation.py",
        "tests/champions/test_alias_consistency.py",
    ],
    "src/vgc_mcp_core/rules/regulation_router.py": [
        "tests/champions/test_regulation_router.py",
        "tests/champions/test_alias_consistency.py",
    ],
    "src/vgc_mcp_core/data/regulations.json": [
        "tests/champions/test_regulation.py",
        "tests/champions/test_alias_consistency.py",
    ],
    "src/vgc_mcp_core/formats/showdown.py": [
        "tests/champions/test_paste_io.py",
    ],
}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        return 0

    edited = Path(file_path).resolve()
    targets: list[str] = []
    for hot_rel, tests in HOT_PATHS.items():
        if edited == (PROJECT_ROOT / hot_rel).resolve():
            targets = tests
            break
    if not targets:
        return 0

    sys.stderr.write(f"[hook:test_hot_paths] running targeted tests for {edited.name}\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *targets, "-q", "--tb=short", "--no-header"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        sys.stderr.write("[hook:test_hot_paths] TARGETED TESTS FAILED:\n")
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
    else:
        # Print just the summary line on success so the user sees it worked.
        last = (result.stdout or "").strip().splitlines()
        if last:
            sys.stderr.write(f"[hook:test_hot_paths] {last[-1]}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
