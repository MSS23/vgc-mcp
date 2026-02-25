"""Tests for EV spread preset tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.preset_tools import register_preset_tools


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    client = AsyncMock()
    client.get_pokemon_usage = AsyncMock(return_value={
        "name": "incineroar",
        "usage_percent": 22.0,
        "moves": {"fake-out": 90, "flare-blitz": 80},
        "items": {"Safety Goggles": 40},
        "abilities": {"Intimidate": 99},
        "spreads": [{"nature": "Careful", "evs": {"hp": 252, "speed": 132}, "spread_string": "Careful:252/0/0/0/0/132", "usage": 15}],
        "tera_types": {"Ghost": 40},
        "_meta": {"format": "gen9vgc2024regh", "month": "2024-12", "rating": 1760}
    })
    return client


@pytest.fixture
def tools(mock_smogon):
    """Register preset tools and return functions."""
    mcp = FastMCP("test")
    register_preset_tools(mcp, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestGetSmogonSpreads:
    """Tests for get_smogon_spreads."""

    async def test_valid_pokemon(self, tools):
        """Test getting Smogon spreads for a valid Pokemon."""
        fn = tools["get_smogon_spreads"].fn
        result = await fn(pokemon_name="incineroar")
        assert result["pokemon"] == "incineroar"
        assert result["spread_count"] >= 1
        assert "spreads" in result

    async def test_no_data(self, tools, mock_smogon):
        """Test with no usage data."""
        mock_smogon.get_pokemon_usage.return_value = None
        fn = tools["get_smogon_spreads"].fn
        result = await fn(pokemon_name="unknown")
        assert "error" in result

    async def test_no_smogon_client(self):
        """Test when Smogon client is None."""
        mcp = FastMCP("test")
        register_preset_tools(mcp, smogon=None)
        tools = {t.name: t for t in mcp._tool_manager._tools.values()}
        fn = tools["get_smogon_spreads"].fn
        result = await fn(pokemon_name="incineroar")
        assert "error" in result


class TestGetSpreadPresets:
    """Tests for get_spread_presets."""

    async def test_no_presets(self, tools):
        """Test Pokemon with no curated presets."""
        fn = tools["get_spread_presets"].fn
        result = await fn(pokemon_name="magikarp")
        assert "error" in result
        assert "suggestion" in result

    async def test_specific_preset_not_found(self, tools):
        """Test requesting a specific preset that doesn't exist."""
        fn = tools["get_spread_presets"].fn
        result = await fn(pokemon_name="magikarp", preset_name="Nonexistent")
        assert "error" in result


class TestListPokemonWithPresets:
    """Tests for list_pokemon_with_presets."""

    async def test_returns_list(self, tools):
        """Test that it returns a list of Pokemon."""
        fn = tools["list_pokemon_with_presets"].fn
        result = await fn()
        assert "count" in result
        assert "pokemon" in result
        assert isinstance(result["pokemon"], list)


class TestSuggestSpreadForRole:
    """Tests for suggest_spread_for_role."""

    async def test_no_presets(self, tools):
        """Test with Pokemon that has no presets."""
        fn = tools["suggest_spread_for_role"].fn
        result = await fn(pokemon_name="magikarp", role="sweeper")
        assert "error" in result
