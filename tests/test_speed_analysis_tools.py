"""Tests for speed analysis, comparison, and speed control tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.speed_analysis_tools import register_speed_analysis_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.team.manager import TeamManager


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    # Flutter Mane: 135 base speed
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=55, attack=55, defense=55,
        special_attack=135, special_defense=135, speed=135
    ))
    return client


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock(spec=TeamManager)
    manager.size = 0
    manager.team = MagicMock()
    return manager


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    return AsyncMock()


@pytest.fixture
def tools(mock_pokeapi, mock_team_manager, mock_smogon):
    """Register speed analysis tools and return functions."""
    mcp = FastMCP("test")
    register_speed_analysis_tools(mcp, mock_pokeapi, mock_team_manager, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestCompareSpeed:
    """Tests for compare_speed."""

    async def test_same_pokemon_same_evs(self, tools):
        """Test speed comparison with identical Pokemon."""
        fn = tools["compare_speed"].fn
        result = await fn(
            pokemon1_name="flutter-mane",
            pokemon2_name="flutter-mane"
        )
        assert "tie" in result.get("winner", "").lower() or "tie" in result.get("result", "").lower()

    async def test_faster_pokemon_wins(self, tools, mock_pokeapi):
        """Test that faster Pokemon is correctly identified."""
        # First call returns Flutter Mane (135 base), second returns Incineroar (60 base)
        mock_pokeapi.get_base_stats.side_effect = [
            BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
            BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
        ]
        fn = tools["compare_speed"].fn
        result = await fn(
            pokemon1_name="flutter-mane",
            pokemon1_nature="timid",
            pokemon1_speed_evs=252,
            pokemon2_name="incineroar",
            pokemon2_nature="careful",
            pokemon2_speed_evs=0
        )
        assert result["winner"] == "flutter-mane"

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["compare_speed"].fn
        result = await fn(
            pokemon1_name="flutter-mane",
            pokemon1_nature="InvalidNature",
            pokemon2_name="incineroar"
        )
        assert "error" in result


class TestGetSpeedTiers:
    """Tests for get_speed_tiers."""

    async def test_returns_tiers(self, tools):
        """Test that speed tiers are returned."""
        fn = tools["get_speed_tiers"].fn
        result = await fn()
        assert "tiers" in result or "speed_tiers" in result


class TestAnalyzeSpeedSpread:
    """Tests for analyze_speed_spread."""

    async def test_basic_spread(self, tools):
        """Test basic speed spread analysis."""
        fn = tools["analyze_speed_spread"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="timid",
            speed_evs=252
        )
        assert "error" not in result or "speed" in str(result).lower()
