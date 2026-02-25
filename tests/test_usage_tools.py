"""Tests for Smogon usage data tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.usage_tools import register_usage_tools


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    client = AsyncMock()
    client.get_pokemon_usage = AsyncMock(return_value={
        "name": "flutter-mane",
        "usage_percent": 25.5,
        "moves": {"moonblast": 85, "shadow-ball": 72},
        "items": {"Choice Specs": 45},
        "abilities": {"Protosynthesis": 99},
        "spreads": [{"nature": "Timid", "evs": {"spa": 252, "spe": 252}}],
        "_meta": {"format": "gen9vgc2024regh", "month": "2024-12"}
    })
    client.get_common_sets = AsyncMock(return_value={
        "pokemon": "flutter-mane",
        "items": [{"name": "Choice Specs", "usage": 45}],
        "abilities": [{"name": "Protosynthesis", "usage": 99}]
    })
    client.suggest_teammates = AsyncMock(return_value={
        "pokemon": "flutter-mane",
        "teammates": [{"name": "incineroar", "usage": 35}]
    })
    client.get_usage_stats = AsyncMock(return_value={
        "data": {
            "flutter-mane": {"usage": 0.255},
            "incineroar": {"usage": 0.22},
        },
        "_meta": {"format": "gen9vgc2024regh", "month": "2024-12"}
    })
    client.compare_pokemon_usage = AsyncMock(return_value={
        "pokemon": "flutter-mane",
        "current_usage": 25.5,
        "previous_usage": 23.0,
        "change": 2.5
    })
    client.current_format = "gen9vgc2024regh"
    client.current_month = "2024-12"
    client.current_regulation_from_data = "H"

    reg_config = MagicMock()
    reg_config.current_regulation = "reg_h"
    reg_config.current_regulation_name = "Regulation H"
    client.regulation_config = reg_config

    client.VGC_FORMATS = ["gen9vgc2024regh", "gen9vgc2024regg"]
    client.RATING_CUTOFFS = [0, 1500, 1630, 1760]
    client.check_data_freshness = MagicMock(return_value=None)
    return client


@pytest.fixture
def tools(mock_smogon):
    """Register usage tools and return functions."""
    mcp = FastMCP("test")
    register_usage_tools(mcp, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestGetUsageStats:
    """Tests for get_usage_stats."""

    async def test_valid_pokemon(self, tools):
        """Test getting usage stats for a valid Pokemon."""
        fn = tools["get_usage_stats"].fn
        result = await fn(pokemon_name="flutter-mane")
        assert result["name"] == "flutter-mane"
        assert result["usage_percent"] == 25.5

    async def test_no_data(self, tools, mock_smogon):
        """Test Pokemon with no usage data."""
        mock_smogon.get_pokemon_usage.return_value = None
        fn = tools["get_usage_stats"].fn
        result = await fn(pokemon_name="unknown-pokemon")
        assert "error" in result

    async def test_api_error(self, tools, mock_smogon):
        """Test API error handling."""
        mock_smogon.get_pokemon_usage.side_effect = Exception("API error")
        fn = tools["get_usage_stats"].fn
        result = await fn(pokemon_name="flutter-mane")
        assert "error" in result


class TestGetCommonSets:
    """Tests for get_common_sets."""

    async def test_valid_pokemon(self, tools):
        """Test getting common sets."""
        fn = tools["get_common_sets"].fn
        result = await fn(pokemon_name="flutter-mane")
        assert result["pokemon"] == "flutter-mane"

    async def test_no_data(self, tools, mock_smogon):
        """Test with no set data."""
        mock_smogon.get_common_sets.return_value = None
        fn = tools["get_common_sets"].fn
        result = await fn(pokemon_name="unknown")
        assert "error" in result


class TestSuggestTeammates:
    """Tests for suggest_teammates."""

    async def test_valid_pokemon(self, tools):
        """Test getting teammate suggestions."""
        fn = tools["suggest_teammates"].fn
        result = await fn(pokemon_name="flutter-mane")
        assert "teammates" in result

    async def test_no_data(self, tools, mock_smogon):
        """Test with no teammate data."""
        mock_smogon.suggest_teammates.return_value = None
        fn = tools["suggest_teammates"].fn
        result = await fn(pokemon_name="unknown")
        assert "error" in result


class TestGetCurrentFormatInfo:
    """Tests for get_current_format_info."""

    async def test_returns_format_info(self, tools):
        """Test that format info is returned."""
        fn = tools["get_current_format_info"].fn
        result = await fn()
        assert "current_format" in result
        assert "current_month" in result
        assert "available_formats" in result


class TestGetTopPokemon:
    """Tests for get_top_pokemon."""

    async def test_returns_top_pokemon(self, tools):
        """Test getting top Pokemon list."""
        fn = tools["get_top_pokemon"].fn
        result = await fn()
        assert "top_pokemon" in result
        assert len(result["top_pokemon"]) == 2

    async def test_sorted_by_usage(self, tools):
        """Test results are sorted by usage."""
        fn = tools["get_top_pokemon"].fn
        result = await fn()
        usages = [p["usage_percent"] for p in result["top_pokemon"]]
        assert usages == sorted(usages, reverse=True)


class TestComparePokemonMonthOverMonth:
    """Tests for compare_pokemon_month_over_month."""

    async def test_valid_comparison(self, tools):
        """Test valid month-over-month comparison."""
        fn = tools["compare_pokemon_month_over_month"].fn
        result = await fn(pokemon_name="flutter-mane")
        assert result["pokemon"] == "flutter-mane"
        assert result["change"] == 2.5

    async def test_no_comparison_data(self, tools, mock_smogon):
        """Test with no comparison data available."""
        mock_smogon.compare_pokemon_usage.return_value = None
        fn = tools["compare_pokemon_month_over_month"].fn
        result = await fn(pokemon_name="unknown")
        assert "error" in result
