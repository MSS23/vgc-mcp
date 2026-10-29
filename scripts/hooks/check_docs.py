"""Keep the docs from going stale. One check, four callers.

    python scripts/hooks/check_docs.py --staged         # git pre-commit, Claude before `git commit`
    python scripts/hooks/check_docs.py --base origin/main  # CI, on every PR
    python scripts/hooks/check_docs.py --stop           # Claude Code Stop hook (reads hook JSON)

Hard failures (block the commit / PR):
  1. Behaviour changed under src/ but CHANGELOG.md was not touched.
     Skip with DOCS_CHECK_SKIP_CHANGELOG=1 or "[no changelog]" in the PR title.
  2. A tool module changed and docs/tools-catalog.md is out of date.
  3. A Markdown link points at a file that does not exist.
  4. README / CLAUDE.md / AGENTS.md / WIKI.md state a tool count other than
     FULL_TOOL_COUNT or the core profile size.

Advisory (printed; the Stop hook asks Claude to act on it once per change set):
  docs that usually need an edit when a given area of the code changes (DOC_MAP).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Code area -> docs that describe it. Keep this the single map of "what documents what".
DOC_MAP: dict[str, list[str]] = {
    "src/vgc_mcp/tools/": ["docs/api-reference.md", "README.md (tool tables)"],
    "src/vgc_mcp/profiles.py": ["README.md", "CLAUDE.md", "smithery.yaml"],
    "src/vgc_mcp/server.py": ["docs/deploy.md", "CLAUDE.md (Architecture)"],
    "src/vgc_mcp_core/presentation.py": ["CLAUDE.md (Damage Calculation Output Format)"],
    "src/vgc_mcp_core/rules/": ["CLAUDE.md (Reg MA/MB/MC)", "docs/vgc-guide.md"],
    "src/vgc_mcp_core/data/regulations.json": ["CLAUDE.md (Reg MA/MB/MC)", "docs/user-guide.md"],
    "src/vgc_mcp_core/calc/": ["docs/technical-guide.md", "CLAUDE.md (mechanics notes)"],
    "src/vgc_mcp_core/tools/": ["docs/api-reference.md"],
    "Dockerfile": ["docs/deploy.md"],
    "render.yaml": ["docs/deploy.md", "CLAUDE.md (Deployment)"],
    ".github/workflows/": ["docs/ci-cd.md"],
    "pyproject.toml": ["README.md (install)", "docs/development.md"],
}
COUNT_DOCS = ["README.md", "CLAUDE.md", "AGENTS.md", "WIKI.md"]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def changed_files(mode: str, base: str | None) -> list[str]:
    if mode == "staged":
        out = git("diff", "--cached", "--name-only", "--diff-filter=ACMRD")
    elif mode == "base":
        out = git("diff", "--name-only", f"{base}...HEAD")
    else:  # stop: everything not yet committed, including new files
        out = git("diff", "HEAD", "--name-only") + git("ls-files", "--others", "--exclude-standard")
    return sorted({f.strip() for f in out.splitlines() if f.strip()})


def is_behaviour(path: str) -> bool:
    return path.startswith("src/") and not path.endswith(".md")


def check_changelog(files: list[str]) -> list[str]:
    if os.environ.get("DOCS_CHECK_SKIP_CHANGELOG") == "1":
        return []
    if "[no changelog]" in os.environ.get("PR_TITLE", "").lower():
        return []
    code = [f for f in files if is_behaviour(f)]
    if code and "CHANGELOG.md" not in files:
        return [
            "CHANGELOG.md not updated although behaviour changed in: "
            + ", ".join(code[:5]) + (" ..." if len(code) > 5 else "")
            + "\n    Add a line under [Unreleased] (or set DOCS_CHECK_SKIP_CHANGELOG=1 / "
            "put [no changelog] in the PR title for pure refactors)."
        ]
    return []


def check_catalog(files: list[str]) -> list[str]:
    if not any(f.startswith(("src/vgc_mcp/tools/", "src/vgc_mcp/profiles.py")) for f in files):
        return []
    catalog = ROOT / "docs" / "tools-catalog.md"
    before = catalog.read_bytes() if catalog.exists() else b""
    subprocess.run([sys.executable, "scripts/build_catalog.py"], cwd=ROOT, capture_output=True)
    if catalog.read_bytes() != before:
        return ["docs/tools-catalog.md was stale and has been regenerated: review and stage it."]
    return []


def check_links() -> list[str]:
    problems = []
    for md in git("ls-files", "*.md").split():
        path = ROOT / md
        if not path.exists():
            continue
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8", errors="ignore"), flags=re.S)
        for target in LINK.findall(text):
            if re.match(r"^(https?:|mailto:|#|<)", target):
                continue
            rel = target.split("#", 1)[0]
            if rel and not (path.parent / rel).exists() and not (ROOT / rel).exists():
                problems.append(f"{md}: broken link -> {target}")
    return problems


def check_counts() -> list[str]:
    sys.path.insert(0, str(ROOT / "src"))
    from vgc_mcp.profiles import CORE_TOOLS, FULL_TOOL_COUNT

    allowed = {FULL_TOOL_COUNT, len(CORE_TOOLS)}
    problems = []
    for doc in COUNT_DOCS:
        path = ROOT / doc
        if path.exists():
            text = path.read_text(encoding="utf-8")
            counts = {int(n) for n in re.findall(r"\b(\d{2,3})\+?(?:-tool| tools| MCP tools)\b", text)}
            if counts - allowed:
                problems.append(f"{doc}: states tool counts {sorted(counts - allowed)}, "
                                f"registry has {FULL_TOOL_COUNT} ({len(CORE_TOOLS)} core)")
    return problems


def advisory(files: list[str]) -> list[str]:
    touched = set(files)
    notes = []
    for prefix, docs in DOC_MAP.items():
        hits = [f for f in files if f.startswith(prefix)]
        if not hits:
            continue
        stale = [d for d in docs if d.split(" ", 1)[0] not in touched]
        if stale:
            notes.append(f"{prefix} changed -> check {', '.join(stale)}")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true")
    group.add_argument("--base")
    group.add_argument("--stop", action="store_true")
    args = parser.parse_args()

    payload = {}
    if args.stop:
        try:
            payload = json.load(sys.stdin)
        except ValueError:
            payload = {}
        if payload.get("stop_hook_active"):
            return 0  # Claude already responded to this hook once; never loop.

    mode = "staged" if args.staged else "base" if args.base else "stop"
    files = changed_files(mode, args.base)
    if not files:
        return 0

    changelog = check_changelog(files)
    problems = check_catalog(files) + check_links() + check_counts()
    notes = advisory(files)
    if args.stop:
        notes = changelog + notes  # enforced at commit time; mid-session it is a reminder
    else:
        problems = changelog + problems

    if args.stop:
        # Ask once per distinct change set, so long sessions are not nagged every turn.
        stamp = ROOT / ".git" / "claude-docs-check"
        digest = hashlib.sha256("\n".join(files + problems + notes).encode()).hexdigest()
        if not problems and (not notes or (stamp.exists() and stamp.read_text() == digest)):
            return 0
        stamp.write_text(digest)
        lines = ["Docs check before you finish (scripts/hooks/check_docs.py):"]
        lines += [f"  - FIX: {p}" for p in problems]
        lines += [f"  - REVIEW: {n}" for n in notes]
        lines.append("Update what is out of date. If a REVIEW doc needs no change, say so in one line.")
        print("\n".join(lines), file=sys.stderr)
        return 2

    for note in notes:
        print(f"docs: {note}")
    if problems:
        print("Docs are stale:\n" + "\n".join(f"  - {p}" for p in problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
