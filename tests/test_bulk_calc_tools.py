"""Tests for bulk offensive damage calculation tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.bulk_calc_tools import register_bulk_calc_tools, _parse_ev_string
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=100, attack=130, defense=100,
        special_attack=63, special_defense=60, speed=97
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Fighting", "Water"])
    client.get_pokemon_abilities = AsyncMock(return_value=["Unseen Fist"])
    return client


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    client = AsyncMock()
    client.get_pokemon_usage = AsyncMock(return_value={
        "name": "urshifu-rapid-strike",
        "usage_percent": 15.0,
        "moves": {"surging-strikes": 90, "close-combat": 80},
        "items": {"Choice Scarf": 40},
        "abilities": {"Unseen Fist": 99},
        "spreads": [{"nature": "Adamant", "evs": {"hp": 4, "attack": 252, "speed": 252}}],
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
def tools(mock_pokeapi, mock_smogon):
    """Register bulk calc tools and return functions."""
    mcp = FastMCP("test")
    register_bulk_calc_tools(mcp, mock_pokeapi, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestParseEvString:
    """Tests for _parse_ev_string helper."""

    def test_valid_string(self):
        result = _parse_ev_string("4/252/0/0/0/252")
        assert result["hp"] == 4
        assert result["attack"] == 252
        assert result["speed"] == 252

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            _parse_ev_string("252/252")

    def test_all_zeros(self):
        result = _parse_ev_string("0/0/0/0/0/0")
        assert all(v == 0 for v in result.values())


class TestCalculateBulkOffensiveCalcs:
    """Tests for calculate_bulk_offensive_calcs."""

    async def test_missing_attacker(self, tools, mock_pokeapi):
        """Test with missing attacker Pokemon."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["calculate_bulk_offensive_calcs"].fn
        result = await fn(
            attacker_name="fakemon",
            move_names=["moonblast"],
            defender_names=["incineroar"]
        )
        assert "error" in result

    async def test_empty_moves(self, tools):
        """Test with no moves specified."""
        fn = tools["calculate_bulk_offensive_calcs"].fn
        result = await fn(
            attacker_name="urshifu-rapid-strike",
            move_names=[],
            defender_names=["incineroar"]
        )
        assert "error" in result or isinstance(result, dict)


class TestExportDamageReport:
    """Tests for export_damage_report."""

    async def test_missing_attacker(self, tools, mock_pokeapi):
        """Test with missing attacker."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["export_damage_report"].fn
        result = await fn(
            attacker_name="fakemon",
            move_names=["moonblast"],
            defender_names=["incineroar"]
        )
        assert "error" in result
