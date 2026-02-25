"""Tests for Smogon-integrated speed analysis tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.speed_tools import register_speed_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=115, attack=115, defense=80,
        special_attack=90, special_defense=75, speed=100
    ))
    return client


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    client = AsyncMock()
    client.get_speed_distribution = AsyncMock(return_value={
        "base_speed": 101,
        "distribution": [
            {"speed": 168, "usage": 40},
            {"speed": 153, "usage": 35},
            {"speed": 101, "usage": 25},
        ],
        "stats": {"max_speed": 168, "min_speed": 101}
    })
    return client


@pytest.fixture
def tools(mock_pokeapi, mock_smogon):
    """Register speed tools and return functions."""
    mcp = FastMCP("test")
    register_speed_tools(mcp, mock_pokeapi, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestAnalyzeOutspeedProbability:
    """Tests for analyze_outspeed_probability."""

    async def test_basic_analysis(self, tools):
        """Test basic speed probability analysis."""
        fn = tools["analyze_outspeed_probability"].fn
        result = await fn(
            pokemon_name="entei",
            target_pokemon="landorus",
            nature="jolly",
            speed_evs=252
        )
        assert "error" not in result
        assert "your_speed" in result or "outspeed" in str(result).lower()

    async def test_with_speed_stat_override(self, tools):
        """Test providing a direct speed stat."""
        fn = tools["analyze_outspeed_probability"].fn
        result = await fn(
            pokemon_name="entei",
            target_pokemon="landorus",
            speed_stat=167
        )
        assert "error" not in result

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["analyze_outspeed_probability"].fn
        result = await fn(
            pokemon_name="entei",
            target_pokemon="landorus",
            nature="notanature",
            speed_evs=252
        )
        assert "error" in result

    async def test_no_smogon_fallback(self, mock_pokeapi):
        """Test fallback when no Smogon client is provided."""
        mcp = FastMCP("test")
        register_speed_tools(mcp, mock_pokeapi, smogon=None)
        tools = {t.name: t for t in mcp._tool_manager._tools.values()}

        fn = tools["analyze_outspeed_probability"].fn
        result = await fn(
            pokemon_name="entei",
            target_pokemon="incineroar",
            nature="jolly",
            speed_evs=252
        )
        # Should still work via META_SPEED_TIERS fallback
        assert "error" not in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["analyze_outspeed_probability"].fn
        result = await fn(
            pokemon_name="fakemon",
            target_pokemon="landorus",
            nature="jolly",
            speed_evs=0
        )
        assert "error" in result
