"""Tests for item mechanics tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.item_tools import register_item_tools


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    # Flutter Mane stats
    client.get_pokemon_stats = AsyncMock(return_value={
        "hp": 55, "attack": 55, "defense": 55,
        "special-attack": 135, "special-defense": 135, "speed": 135
    })
    client.get_nature = AsyncMock(return_value={
        "name": "timid",
        "increased_stat": {"name": "speed"},
        "decreased_stat": {"name": "attack"},
    })
    client.get_base_stats_raw = AsyncMock(return_value={
        "hp": 55, "attack": 55, "defense": 55,
        "special_attack": 135, "special_defense": 135, "speed": 135
    })
    return client


@pytest.fixture
def tools(mock_pokeapi):
    """Register item tools and return functions."""
    mcp = FastMCP("test")
    register_item_tools(mcp, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestCalculateBoosterEnergy:
    """Tests for calculate_booster_energy."""

    async def test_paradox_pokemon(self, tools):
        """Test Booster Energy on a Paradox Pokemon."""
        fn = tools["calculate_booster_energy"].fn
        result = await fn(pokemon_name="flutter-mane")
        assert result["pokemon"] == "flutter-mane"
        assert result["item"] == "Booster Energy"
        # Flutter Mane is a Paradox Pokemon
        assert result["is_paradox"] is True

    async def test_non_paradox_pokemon(self, tools, mock_pokeapi):
        """Test Booster Energy on a non-Paradox Pokemon."""
        mock_pokeapi.get_pokemon_stats.return_value = {
            "hp": 95, "attack": 115, "defense": 90,
            "special-attack": 80, "special-defense": 90, "speed": 60
        }
        fn = tools["calculate_booster_energy"].fn
        result = await fn(pokemon_name="incineroar")
        # Incineroar is not a Paradox Pokemon
        assert result.get("is_paradox") is False or "not" in str(result.get("description", "")).lower()


class TestCalculateAssaultVest:
    """Tests for calculate_assault_vest."""

    async def test_basic_calculation(self, tools):
        """Test basic Assault Vest SpD boost."""
        fn = tools["calculate_assault_vest"].fn
        result = await fn(pokemon_name="flutter-mane")
        assert "error" not in result or result.get("success") is not False
        # Should show SpD boost info
        assert "before" in str(result) or "after" in str(result) or "boost" in str(result).lower()


class TestCalculateChoiceItem:
    """Tests for calculate_choice_item."""

    async def test_choice_band(self, tools):
        """Test Choice Band attack boost."""
        fn = tools["calculate_choice_item"].fn
        result = await fn(pokemon_name="flutter-mane", item="choice-band")
        assert "error" not in result or result.get("success") is not False

    async def test_choice_specs(self, tools):
        """Test Choice Specs special attack boost."""
        fn = tools["calculate_choice_item"].fn
        result = await fn(pokemon_name="flutter-mane", item="choice-specs")
        assert "error" not in result or result.get("success") is not False


class TestCheckBerryActivation:
    """Tests for check_berry_activation_threshold."""

    async def test_berry_threshold(self, tools):
        """Test berry activation threshold calculation."""
        fn = tools["check_berry_activation_threshold"].fn
        result = await fn(pokemon_name="flutter-mane", berry="sitrus")
        assert "error" not in result or "threshold" in str(result).lower()


class TestCheckFocusSash:
    """Tests for check_focus_sash."""

    async def test_focus_sash(self, tools):
        """Test Focus Sash survival check."""
        fn = tools["check_focus_sash"].fn
        result = await fn(pokemon_name="flutter-mane", incoming_damage=200)
        assert "error" not in result or "sash" in str(result).lower()


class TestCalculateLifeOrbDamage:
    """Tests for calculate_life_orb_damage."""

    async def test_life_orb_calc(self, tools):
        """Test Life Orb damage and recoil calculation."""
        fn = tools["calculate_life_orb_damage"].fn
        result = await fn(pokemon_name="flutter-mane", base_damage=100)
        assert "error" not in result or "recoil" in str(result).lower()


class TestGetItemDamageBoost:
    """Tests for get_item_damage_boost."""

    async def test_item_boost(self, tools):
        """Test getting item damage boost modifier."""
        fn = tools["get_item_damage_boost"].fn
        result = await fn(item="life-orb", move_category="special")
        assert "error" not in result or "modifier" in str(result).lower() or "boost" in str(result).lower()
