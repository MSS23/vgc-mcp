"""Tests for item optimization and comparison tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.item_optimization_tools import register_item_optimization_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=55, attack=55, defense=55,
        special_attack=135, special_defense=135, speed=135
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Ghost", "Fairy"])
    client.get_pokemon_abilities = AsyncMock(return_value=["Protosynthesis"])
    client.get_move = AsyncMock(return_value=Move(
        name="moonblast", power=95, type="fairy",
        category=MoveCategory.SPECIAL, accuracy=100, pp=15, priority=0
    ))
    return client


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    client = AsyncMock()
    client.get_pokemon_usage = AsyncMock(return_value={
        "name": "flutter-mane",
        "usage_percent": 18.0,
        "moves": {"moonblast": 90},
        "items": {"Choice Specs": 40, "Booster Energy": 35},
        "abilities": {"Protosynthesis": 99},
        "spreads": [{"nature": "Timid", "evs": {"special_attack": 252, "speed": 252, "hp": 4}}],
    })
    return client


@pytest.fixture
def tools(mock_pokeapi, mock_smogon):
    """Register item optimization tools and return functions."""
    mcp = FastMCP("test")
    register_item_optimization_tools(mcp, mock_pokeapi, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestCompareItemDamageOutput:
    """Tests for compare_item_damage_output."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test with invalid attacker."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["compare_item_damage_output"].fn
        result = await fn(
            pokemon_name="fakemon",
            move_name="moonblast",
            target_name="incineroar"
        )
        assert "error" in result

    async def test_basic_compare(self, tools):
        """Test basic item comparison."""
        fn = tools["compare_item_damage_output"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            move_name="moonblast",
            target_name="incineroar",
            items_to_compare=["life-orb", "choice-specs"]
        )
        assert isinstance(result, dict)


class TestOptimizeLifeOrbSustainability:
    """Tests for optimize_life_orb_sustainability."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test with invalid Pokemon."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["optimize_life_orb_sustainability"].fn
        result = await fn(pokemon_name="fakemon")
        assert "error" in result

    async def test_basic_analysis(self, tools):
        """Test basic Life Orb sustainability analysis."""
        fn = tools["optimize_life_orb_sustainability"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            hp_investment=4
        )
        assert isinstance(result, dict)


class TestAnalyzeItemEvTradeoff:
    """Tests for analyze_item_ev_tradeoff."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test with invalid Pokemon."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["analyze_item_ev_tradeoff"].fn
        result = await fn(
            pokemon_name="fakemon",
            offensive_stat="special_attack",
            target_benchmark=200
        )
        assert "error" in result

    async def test_basic_tradeoff(self, tools):
        """Test basic item EV tradeoff analysis."""
        fn = tools["analyze_item_ev_tradeoff"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            offensive_stat="special_attack",
            target_benchmark=200
        )
        assert isinstance(result, dict)
