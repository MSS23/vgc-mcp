"""Tests for stat calculation tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.stats_tools import register_stats_tools
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
def tools(mock_pokeapi):
    """Register stats tools and return functions."""
    mcp = FastMCP("test")
    register_stats_tools(mcp, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestGetPokemonStats:
    """Tests for get_pokemon_stats."""

    async def test_basic_stat_calc(self, tools):
        """Test basic stat calculation."""
        fn = tools["get_pokemon_stats"].fn
        result = await fn(pokemon_name="flutter-mane", nature="timid")
        assert result["pokemon"] == "flutter-mane"
        assert "final_stats" in result or "stats" in result
        assert result["level"] == 50

    async def test_with_evs(self, tools):
        """Test stat calculation with EVs."""
        fn = tools["get_pokemon_stats"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="timid",
            spa_evs=252,
            spe_evs=252,
            hp_evs=4
        )
        assert result["pokemon"] == "flutter-mane"

    async def test_exceeding_evs(self, tools):
        """Test that exceeding 508 total EVs returns error."""
        fn = tools["get_pokemon_stats"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="timid",
            hp_evs=252, atk_evs=252, spe_evs=252  # 756 total
        )
        assert "error" in result

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["get_pokemon_stats"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="InvalidNature"
        )
        assert "error" in result

    async def test_has_summary_table(self, tools):
        """Test that result includes a summary table."""
        fn = tools["get_pokemon_stats"].fn
        result = await fn(pokemon_name="flutter-mane", nature="timid")
        assert "summary_table" in result or "analysis" in result
