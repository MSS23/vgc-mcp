"""Tests for speed tier visualization tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.speed_viz_tools import register_speed_viz_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=55, attack=55, defense=55,
        special_attack=135, special_defense=135, speed=135
    ))
    return client


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    return AsyncMock()


@pytest.fixture
def tools(mock_pokeapi, mock_smogon):
    """Register speed viz tools and return functions."""
    mcp = FastMCP("test")
    register_speed_viz_tools(mcp, mock_pokeapi, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestVisualizeTeamSpeedTiers:
    """Tests for visualize_team_speed_tiers."""

    async def test_with_team(self, tools):
        """Test visualizing speed tiers for a team."""
        fn = tools["visualize_team_speed_tiers"].fn
        result = await fn(
            team_pokemon=[
                {"name": "flutter-mane", "nature": "timid", "evs": {"speed": 252}},
            ]
        )
        assert "team_speeds" in result
        assert "meta_speeds" in result
        assert "markdown_summary" in result

    async def test_empty_team(self, tools):
        """Test with empty team."""
        fn = tools["visualize_team_speed_tiers"].fn
        result = await fn(team_pokemon=[])
        assert "meta_speeds" in result

    async def test_includes_tailwind(self, tools):
        """Test that Tailwind section is included."""
        fn = tools["visualize_team_speed_tiers"].fn
        result = await fn(
            team_pokemon=[{"name": "flutter-mane", "nature": "timid", "evs": {"speed": 252}}],
            include_tailwind=True
        )
        assert "Tailwind" in result["markdown_summary"]
