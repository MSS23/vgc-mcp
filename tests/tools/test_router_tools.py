"""Tests for the tool router (`what_tool_should_i_use`).

Pure keyword/regex routing — no deps, so no mocks. These lock in the
routing contract: known question shapes map to the expected tools, the
fallback fires for unmatched questions, and dedup/limits hold.
"""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.router_tools import ROUTING_RULES, register_router_tools


@pytest.fixture
def route():
    mcp = FastMCP("test")
    register_router_tools(mcp)
    return {t.name: t for t in mcp._tool_manager._tools.values()}["what_tool_should_i_use"].fn


class TestRouting:
    async def test_ohko_question_routes_to_damage(self, route):
        result = await route(question="Does Flutter Mane OHKO Incineroar?")
        assert result["success"] is True
        tools = [s["tool"] for s in result["suggestions"]]
        assert tools[0] == "calculate_damage_output"

    async def test_survival_question_routes_to_survival_evs(self, route):
        result = await route(question="What EVs do I need to survive Urshifu?")
        tools = [s["tool"] for s in result["suggestions"]]
        assert "find_survival_evs" in tools

    async def test_outspeed_question(self, route):
        result = await route(question="Can my Entei outspeed Chien-Pao?")
        tools = [s["tool"] for s in result["suggestions"]]
        assert "find_speed_evs_to_outspeed" in tools

    async def test_archetype_question(self, route):
        result = await route(question="What kind of team is this? What archetype?")
        tools = [s["tool"] for s in result["suggestions"]]
        assert "classify_team_archetype" in tools

    async def test_live_battle_question(self, route):
        result = await route(question="I'm in a live battle, what should I do next turn?")
        tools = [s["tool"] for s in result["suggestions"]]
        assert "suggest_next_move" in tools or "start_battle" in tools

    async def test_priorities_are_sequential(self, route):
        result = await route(question="optimize my spread to survive both threats")
        priorities = [s["priority"] for s in result["suggestions"]]
        assert priorities == list(range(1, len(priorities) + 1))


class TestLimitsAndDedup:
    async def test_max_suggestions_respected(self, route):
        # A question matching many rules must still cap at max_suggestions
        result = await route(
            question="optimize EVs to survive damage and outspeed the meta",
            max_suggestions=3,
        )
        assert len(result["suggestions"]) == 3

    async def test_no_duplicate_tools(self, route):
        # "damage" rules overlap; the same tool must not appear twice
        result = await route(
            question="damage vs Incineroar — does it OHKO?", max_suggestions=10
        )
        tools = [s["tool"] for s in result["suggestions"]]
        assert len(tools) == len(set(tools))


class TestFallbackAndErrors:
    async def test_unmatched_question_gets_fallback(self, route):
        result = await route(question="zzzz qwerty nonsense")
        assert result["success"] is True
        assert result["suggestions"][0]["tool"] == "get_starter_prompts"

    async def test_empty_question_is_error(self, route):
        result = await route(question="   ")
        assert result["success"] is False
        assert "error" in result


def test_routing_rules_are_well_formed():
    """Every rule: compiled regex, non-empty tool list, non-empty rationale."""
    for pattern, tool_list, rationale in ROUTING_RULES:
        assert pattern.search is not None
        assert tool_list, f"empty tool list for {pattern.pattern}"
        assert rationale.strip(), f"empty rationale for {pattern.pattern}"
