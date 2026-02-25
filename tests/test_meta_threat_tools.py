"""Tests for meta threat analysis tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.meta_threat_tools import register_meta_threat_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=80, attack=120, defense=84,
        special_attack=60, special_defense=96, speed=110
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Grass", "Fire"])
    # Return a MagicMock that supports both dict-style .get() and attribute access
    move_mock = MagicMock()
    move_mock.power = 25
    move_mock.type = "water"
    move_mock.category = MagicMock()
    move_mock.category.value = "physical"
    move_mock.get = lambda key, default=None: {"power": 25, "type": "water", "category": "physical", "name": "surging-strikes"}.get(key, default)
    client.get_move = AsyncMock(return_value=move_mock)
    return client


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    client = AsyncMock()
    client.get_pokemon_usage = AsyncMock(return_value={
        "name": "ogerpon-hearthflame",
        "usage_percent": 15.0,
        "moves": {"ivy-cudgel": 90, "follow-me": 80, "spiky-shield": 70, "horn-leech": 40},
        "items": {"Hearthflame Mask": 99},
        "abilities": {"Mold Breaker": 99},
        "spreads": [{"nature": "Jolly", "evs": {"hp": 252, "speed": 252}}],
    })
    client.get_usage_stats = AsyncMock(return_value={
        "_meta": {"total_battles": 1000},
        "data": {
            "Incineroar": {"usage": 22.0},
            "Flutter Mane": {"usage": 18.0},
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
    """Register meta threat tools and return functions."""
    mcp = FastMCP("test")
    register_meta_threat_tools(mcp, mock_smogon, mock_pokeapi, mock_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestAnalyzeSpreadVsThreats:
    """Tests for analyze_spread_vs_threats."""

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["analyze_spread_vs_threats"].fn
        result = await fn(pokemon_name="ogerpon-hearthflame", nature="notanature")
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["analyze_spread_vs_threats"].fn
        result = await fn(pokemon_name="fakemon", nature="jolly")
        assert "error" in result


class TestCheckSurvivalBenchmark:
    """Tests for check_survival_benchmark."""

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["check_survival_benchmark"].fn
        result = await fn(
            pokemon_name="ogerpon-hearthflame",
            nature="notanature",
            hp_evs=252,
            def_evs=4,
            spd_evs=0,
            threat_pokemon="urshifu-rapid-strike",
            threat_move="surging-strikes"
        )
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["check_survival_benchmark"].fn
        result = await fn(
            pokemon_name="fakemon",
            nature="bold",
            hp_evs=252,
            def_evs=4,
            spd_evs=0,
            threat_pokemon="urshifu",
            threat_move="surging-strikes"
        )
        assert "error" in result
