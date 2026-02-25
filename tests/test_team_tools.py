"""Tests for team management tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.team_tools import register_team_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.team.manager import TeamManager


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=95, attack=115, defense=90,
        special_attack=80, special_defense=90, speed=60
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Fire", "Dark"])
    client.get_pokemon_abilities = AsyncMock(return_value=["Intimidate", "Blaze"])
    return client


@pytest.fixture
def real_team_manager():
    """Create a real TeamManager for integration-style tests."""
    return TeamManager()


@pytest.fixture
def mock_analyzer():
    """Create a mock team analyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MagicMock(
        strengths=["Good coverage"],
        weaknesses=["Weak to Ground"],
        overall_grade="B"
    )
    return analyzer


@pytest.fixture
def tools(mock_pokeapi, real_team_manager, mock_analyzer):
    """Register team tools and return functions."""
    mcp = FastMCP("test")
    register_team_tools(mcp, mock_pokeapi, real_team_manager, mock_analyzer)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestAddToTeam:
    """Tests for add_to_team."""

    async def test_add_pokemon(self, tools):
        """Test adding a Pokemon to team."""
        fn = tools["add_to_team"].fn
        result = await fn(
            pokemon_name="incineroar",
            nature="careful",
            ability="Intimidate",
            item="Safety Goggles"
        )
        assert result.get("success") is True or "added" in str(result).lower()

    async def test_add_with_evs(self, tools):
        """Test adding Pokemon with EVs."""
        fn = tools["add_to_team"].fn
        result = await fn(
            pokemon_name="incineroar",
            nature="careful",
            hp_evs=252, spe_evs=132, def_evs=116, spd_evs=4, atk_evs=4
        )
        assert result.get("success") is True or "added" in str(result).lower()


class TestViewTeam:
    """Tests for view_team."""

    async def test_empty_team(self, tools):
        """Test viewing empty team."""
        fn = tools["view_team"].fn
        result = await fn()
        assert result.get("size") == 0 or result.get("team_size") == 0


class TestRemoveFromTeam:
    """Tests for remove_from_team."""

    async def test_remove_from_empty(self, tools):
        """Test removing from empty team."""
        fn = tools["remove_from_team"].fn
        result = await fn(slot=1)
        assert result.get("success") is False or "error" in result


class TestClearTeam:
    """Tests for clear_team."""

    async def test_clear_empty_team(self, tools):
        """Test clearing an already empty team."""
        fn = tools["clear_team"].fn
        result = await fn()
        assert result.get("success") is True or "cleared" in str(result).lower()
