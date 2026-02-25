"""Tests for speed probability analysis tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.speed_probability_tools import register_speed_probability_tools
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
        ]
    })
    client.get_pokemon_usage = AsyncMock(return_value={
        "name": "landorus",
        "usage_percent": 15.0,
        "spreads": [
            {"nature": "Adamant", "evs": {"speed": 252}},
            {"nature": "Jolly", "evs": {"speed": 252}},
        ]
    })
    client.get_usage_stats = AsyncMock(return_value={
        "_meta": {"total_battles": 1000},
        "data": {
            "Landorus": {"usage": 15.0},
            "Incineroar": {"usage": 22.0},
        }
    })
    return client


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock()
    manager.size = 0
    manager.get_current_team = MagicMock(return_value=None)
    return manager


@pytest.fixture
def tools(mock_pokeapi, mock_smogon, mock_team_manager):
    """Register speed probability tools and return functions."""
    mcp = FastMCP("test")
    register_speed_probability_tools(mcp, mock_smogon, mock_pokeapi, mock_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestOutspeedProbability:
    """Tests for outspeed_probability."""

    async def test_basic_calc(self, tools):
        """Test basic outspeed probability."""
        fn = tools["outspeed_probability"].fn
        result = await fn(
            your_pokemon="entei",
            your_speed_evs=252,
            your_nature="jolly",
            target_pokemon="landorus"
        )
        assert "error" not in result

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["outspeed_probability"].fn
        result = await fn(
            your_pokemon="entei",
            your_speed_evs=252,
            your_nature="notanature",
            target_pokemon="landorus"
        )
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when your Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["outspeed_probability"].fn
        result = await fn(
            your_pokemon="fakemon",
            your_speed_evs=0,
            your_nature="jolly",
            target_pokemon="landorus"
        )
        assert "error" in result


class TestSpeedCreepCalculator:
    """Tests for speed_creep_calculator."""

    async def test_basic_creep(self, tools):
        """Test basic speed creep calculation."""
        fn = tools["speed_creep_calculator"].fn
        result = await fn(
            your_pokemon="entei",
            your_nature="adamant",
            target_pokemon="landorus",
            desired_outspeed_pct=90.0
        )
        assert "error" not in result

    async def test_invalid_pokemon(self, tools, mock_pokeapi):
        """Test with invalid Pokemon."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["speed_creep_calculator"].fn
        result = await fn(
            your_pokemon="fakemon",
            your_nature="jolly",
            target_pokemon="landorus"
        )
        assert "error" in result


class TestCompareSpeedInvestment:
    """Tests for compare_speed_investment."""

    async def test_basic_compare(self, tools):
        """Test comparing speed EVs."""
        fn = tools["compare_speed_investment"].fn
        result = await fn(
            pokemon_name="entei",
            target_pokemon="landorus",
            ev_options="0,132,252"
        )
        assert "error" not in result

    async def test_invalid_pokemon(self, tools, mock_pokeapi):
        """Test with invalid Pokemon."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["compare_speed_investment"].fn
        result = await fn(
            pokemon_name="fakemon",
            target_pokemon="landorus",
            ev_options="0,252"
        )
        assert "error" in result
