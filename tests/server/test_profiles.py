"""The core profile must cover every tool the server points users or models at."""

import asyncio
import re
from pathlib import Path

import pytest

from vgc_mcp.profiles import CORE_TOOLS, FULL_TOOL_COUNT, resolve_profile

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def registered() -> set[str]:
    from vgc_mcp.server import mcp

    return {t.name for t in asyncio.run(mcp.list_tools())}


def _named_tools(text: str, registered: set[str]) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9_]{3,}", text) if w in registered}


def test_core_is_a_subset_of_the_registry(registered):
    assert CORE_TOOLS <= registered
    assert 25 <= len(CORE_TOOLS) <= 40


def test_server_instructions_only_name_core_tools(registered):
    from vgc_mcp_core.presentation import PRESENTATION_INSTRUCTIONS

    extra = _named_tools(PRESENTATION_INSTRUCTIONS, registered) - CORE_TOOLS
    assert not extra, f"instructions name tools outside the core profile: {extra}"


def test_prompts_only_name_core_tools(registered):
    from vgc_mcp.server import mcp

    texts = [p.fn() for p in mcp._prompt_manager._prompts.values()]
    extra = set().union(*(_named_tools(t, registered) for t in texts)) - CORE_TOOLS
    assert not extra, f"prompts name tools outside the core profile: {extra}"


def test_onboarding_only_lists_core_tools():
    from vgc_mcp.tools.onboarding_tools import _CATEGORIES

    listed = {name for cat in _CATEGORIES.values() for name in cat["tools"]}
    assert listed <= CORE_TOOLS, listed - CORE_TOOLS


def test_production_verifier_only_calls_core_tools(registered):
    text = (ROOT / "scripts" / "verify_production.py").read_text(encoding="utf-8")
    called = set(re.findall(r'"name": "([a-z_]+)"', text))
    called |= set(re.findall(r'call\(\d+, "([a-z_]+)"', text))
    called &= registered
    assert called and called <= CORE_TOOLS, called - CORE_TOOLS


def test_core_server_shares_tool_objects_with_full_server():
    from vgc_mcp.server import mcp, mcp_core

    for name in CORE_TOOLS:
        assert mcp_core._tool_manager._tools[name] is mcp._tool_manager._tools[name]
    assert set(mcp_core._prompt_manager._prompts) == set(mcp._prompt_manager._prompts)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "core"), ("full", "full"), (" FULL ", "full"), ("core", "core"), ("typo", "core")],
)
def test_resolve_profile(value, expected, monkeypatch):
    monkeypatch.delenv("VGC_MCP_PROFILE", raising=False)
    assert resolve_profile(value) == expected


def test_profile_env_var(monkeypatch):
    monkeypatch.setenv("VGC_MCP_PROFILE", "full")
    assert resolve_profile() == "full"


@pytest.mark.parametrize("doc", ["README.md", "CLAUDE.md", "AGENTS.md", "WIKI.md"])
def test_docs_state_the_pinned_tool_count(doc):
    """Every 'N tools' claim in the top-level docs matches FULL_TOOL_COUNT or the core size."""
    text = (ROOT / doc).read_text(encoding="utf-8")
    counts = {int(n) for n in re.findall(r"\b(\d{2,3})(?:\+)?(?:-tool| tools| MCP tools)\b", text)}
    allowed = {FULL_TOOL_COUNT, len(CORE_TOOLS)}
    assert counts <= allowed, f"{doc} states tool counts {counts - allowed}"
