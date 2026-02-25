"""Tests for Tera type optimization tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.tera_tools import register_tera_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=55, attack=55, defense=55,
        special_attack=135, special_defense=135, speed=135
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Ghost", "Fairy"])
    return client


@pytest.fixture
def optimize_tera(mock_pokeapi):
    """Register tools and return optimize_tera_type function."""
    mcp = FastMCP("test")
    register_tera_tools(mcp, mock_pokeapi)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools["optimize_tera_type"].fn


class TestOptimizeTera:
    """Tests for the optimize_tera_type tool."""

    async def test_basic_tera_optimization(self, optimize_tera):
        """Test basic Tera type optimization."""
        result = await optimize_tera(
            pokemon_name="flutter-mane",
            spread={"nature": "timid", "evs": {"special_attack": 252, "speed": 252}},
            role="attacker"
        )
        assert "error" not in result
        assert "tera_rankings" in result
        assert "recommended" in result
        assert len(result["tera_rankings"]) > 0

    async def test_attacker_role(self, optimize_tera):
        """Test attacker role scoring."""
        result = await optimize_tera(
            pokemon_name="flutter-mane",
            spread={"nature": "timid"},
            role="attacker"
        )
        rankings = result["tera_rankings"]
        # Original types (Ghost, Fairy) should score higher for STAB boost
        original_type_scores = [r for r in rankings if r["type"] in ["Ghost", "Fairy"]]
        other_type_scores = [r for r in rankings if r["type"] not in ["Ghost", "Fairy"]]
        if original_type_scores and other_type_scores:
            assert original_type_scores[0]["score"] >= other_type_scores[0]["score"]

    async def test_rankings_sorted_by_score(self, optimize_tera):
        """Test that rankings are sorted by score descending."""
        result = await optimize_tera(
            pokemon_name="flutter-mane",
            spread={"nature": "timid"},
        )
        rankings = result["tera_rankings"]
        scores = [r["score"] for r in rankings]
        assert scores == sorted(scores, reverse=True)

    async def test_top_10_returned(self, optimize_tera):
        """Test that up to 10 Tera types are returned."""
        result = await optimize_tera(
            pokemon_name="flutter-mane",
            spread={"nature": "timid"},
        )
        assert len(result["tera_rankings"]) <= 10

    async def test_with_meta_threats(self, optimize_tera, mock_pokeapi):
        """Test optimization with meta threats considered."""
        mock_pokeapi.get_pokemon_types.side_effect = [
            ["Ghost", "Fairy"],  # flutter-mane
            ["Water", "Fighting"],  # urshifu
        ]
        result = await optimize_tera(
            pokemon_name="flutter-mane",
            spread={"nature": "timid"},
            meta_threats=["urshifu-rapid-strike"]
        )
        assert "tera_rankings" in result

    async def test_with_team_pokemon(self, optimize_tera, mock_pokeapi):
        """Test optimization with team Pokemon context."""
        mock_pokeapi.get_pokemon_types.side_effect = [
            ["Ghost", "Fairy"],  # flutter-mane
            ["Fire", "Dark"],   # incineroar
        ]
        result = await optimize_tera(
            pokemon_name="flutter-mane",
            spread={"nature": "timid"},
            team_pokemon=["incineroar"]
        )
        assert "tera_rankings" in result

    async def test_markdown_summary(self, optimize_tera):
        """Test markdown summary is included."""
        result = await optimize_tera(
            pokemon_name="flutter-mane",
            spread={"nature": "timid"},
        )
        assert "markdown_summary" in result
        assert "Tera Type Analysis" in result["markdown_summary"]

    async def test_ranking_has_reasoning(self, optimize_tera):
        """Test each ranking has reasoning."""
        result = await optimize_tera(
            pokemon_name="flutter-mane",
            spread={"nature": "timid"},
        )
        for ranking in result["tera_rankings"]:
            assert "type" in ranking
            assert "score" in ranking
            assert "reasoning" in ranking
