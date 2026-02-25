"""Tests for EV spread optimization tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.spread_tools import register_spread_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()

    async def _get_base_stats(name):
        stats = {
            "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
            "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
        }
        return stats.get(name.lower(), BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80))

    async def _get_types(name):
        types_map = {
            "flutter-mane": ["Ghost", "Fairy"],
            "incineroar": ["Fire", "Dark"],
        }
        return types_map.get(name.lower(), ["Normal"])

    async def _get_abilities(name):
        return ["Protosynthesis"]

    client.get_base_stats = AsyncMock(side_effect=_get_base_stats)
    client.get_pokemon_types = AsyncMock(side_effect=_get_types)
    client.get_pokemon_abilities = AsyncMock(side_effect=_get_abilities)
    return client


@pytest.fixture
def tools(mock_pokeapi):
    """Register spread tools and return functions."""
    mcp = FastMCP("test")
    register_spread_tools(mcp, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestCheckSpreadEfficiency:
    """Tests for check_spread_efficiency."""

    async def test_basic_efficiency(self, tools):
        """Test basic spread efficiency check."""
        fn = tools["check_spread_efficiency"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="timid",
            spa_evs=252,
            spe_evs=252,
            hp_evs=4
        )
        assert isinstance(result, dict)
        assert "error" not in result

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["check_spread_efficiency"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="notanature"
        )
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["check_spread_efficiency"].fn
        result = await fn(
            pokemon_name="fakemon",
            nature="timid"
        )
        assert "error" in result


class TestSuggestNatureOptimization:
    """Tests for suggest_nature_optimization."""

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["suggest_nature_optimization"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            current_nature="notanature",
            hp_evs=4, atk_evs=0, def_evs=0,
            spa_evs=252, spd_evs=0, spe_evs=252
        )
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["suggest_nature_optimization"].fn
        result = await fn(
            pokemon_name="fakemon",
            current_nature="timid",
            hp_evs=4, atk_evs=0, def_evs=0,
            spa_evs=252, spd_evs=0, spe_evs=252
        )
        assert "error" in result


class TestOptimizeBulk:
    """Tests for optimize_bulk."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["optimize_bulk"].fn
        result = await fn(
            pokemon_name="fakemon",
            nature="bold",
            total_bulk_evs=252
        )
        assert "error" in result

    async def test_basic_optimization(self, tools):
        """Test basic bulk optimization."""
        fn = tools["optimize_bulk"].fn
        result = await fn(
            pokemon_name="incineroar",
            nature="careful",
            total_bulk_evs=252
        )
        assert isinstance(result, dict)
        assert "error" not in result


class TestSuggestSpread:
    """Tests for suggest_spread."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["suggest_spread"].fn
        result = await fn(pokemon_name="fakemon")
        assert "error" in result

    async def test_basic_suggestion(self, tools):
        """Test basic spread suggestion."""
        fn = tools["suggest_spread"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            role="offensive"
        )
        assert isinstance(result, dict)


class TestAnalyzeBulkDiminishingReturns:
    """Tests for analyze_bulk_diminishing_returns."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["analyze_bulk_diminishing_returns"].fn
        result = await fn(
            pokemon_name="fakemon",
            nature="bold"
        )
        assert "error" in result


class TestAnalyzeHpNumber:
    """Tests for analyze_hp_number."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["analyze_hp_number"].fn
        result = await fn(pokemon_name="fakemon", item="life-orb")
        assert "error" in result

    async def test_basic_analysis(self, tools):
        """Test basic HP number analysis."""
        fn = tools["analyze_hp_number"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            item="life-orb",
            current_hp_evs=4
        )
        assert isinstance(result, dict)
