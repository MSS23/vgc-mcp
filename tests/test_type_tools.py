"""Tests for type effectiveness education tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.type_tools import register_type_tools
from vgc_mcp_core.calc.modifiers import TYPE_CHART


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    # Default: return Fire type for any Pokemon
    client.get_pokemon_types = AsyncMock(return_value=["Fire"])
    return client


@pytest.fixture
def explain_type_matchup(mock_pokeapi):
    """Create MCP server with type tools and return the tool function."""
    mcp = FastMCP("test")
    register_type_tools(mcp, mock_pokeapi)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools["explain_type_matchup"].fn


class TestExplainTypeMatchup:
    """Tests for the explain_type_matchup tool."""

    async def test_super_effective(self, explain_type_matchup):
        """Test super effective matchup (Fire vs Grass)."""
        result = await explain_type_matchup(
            attacking_type="Fire",
            defending_types=["Grass"]
        )
        assert result["effectiveness"] == 2.0
        assert "SUPER EFFECTIVE" in result["result"]

    async def test_not_very_effective(self, explain_type_matchup):
        """Test resisted matchup (Fire vs Water)."""
        result = await explain_type_matchup(
            attacking_type="Fire",
            defending_types=["Water"]
        )
        assert result["effectiveness"] == 0.5
        assert "RESISTED" in result["result"]

    async def test_no_effect(self, explain_type_matchup):
        """Test immune matchup (Normal vs Ghost)."""
        result = await explain_type_matchup(
            attacking_type="Normal",
            defending_types=["Ghost"]
        )
        assert result["effectiveness"] == 0
        assert "NO EFFECT" in result["result"]

    async def test_neutral(self, explain_type_matchup):
        """Test neutral matchup (Fire vs Normal)."""
        result = await explain_type_matchup(
            attacking_type="Fire",
            defending_types=["Normal"]
        )
        assert result["effectiveness"] == 1.0
        assert "NEUTRAL" in result["result"]

    async def test_4x_super_effective(self, explain_type_matchup):
        """Test 4x super effective (Ice vs Grass/Flying like Jumpluff)."""
        result = await explain_type_matchup(
            attacking_type="Ice",
            defending_types=["Grass", "Flying"]
        )
        assert result["effectiveness"] == 4.0
        assert "4x SUPER EFFECTIVE" in result["result"]

    async def test_4x_resisted(self, explain_type_matchup):
        """Test 4x resisted (Fighting vs Poison/Ghost - immune actually)."""
        result = await explain_type_matchup(
            attacking_type="Fighting",
            defending_types=["Ghost"]
        )
        assert result["effectiveness"] == 0

    async def test_dual_type_combined(self, explain_type_matchup):
        """Test dual-type combined effectiveness (Water vs Fire/Ground)."""
        result = await explain_type_matchup(
            attacking_type="Water",
            defending_types=["Fire", "Ground"]
        )
        assert result["effectiveness"] == 4.0

    async def test_pokemon_name_lookup(self, explain_type_matchup, mock_pokeapi):
        """Test using pokemon_name to auto-fetch types."""
        mock_pokeapi.get_pokemon_types.return_value = ["Grass"]
        result = await explain_type_matchup(
            attacking_type="Fire",
            pokemon_name="rillaboom"
        )
        assert result["effectiveness"] == 2.0
        mock_pokeapi.get_pokemon_types.assert_called_once_with("rillaboom")

    async def test_missing_params_returns_error(self, explain_type_matchup):
        """Test that missing both defending_types and pokemon_name returns error."""
        result = await explain_type_matchup(
            attacking_type=None,
            defending_types=None
        )
        assert "error" in result

    async def test_markdown_includes_cheat_sheet(self, explain_type_matchup):
        """Test that markdown includes type cheat sheet."""
        result = await explain_type_matchup(
            attacking_type="Fire",
            defending_types=["Grass"]
        )
        assert "markdown_summary" in result
        assert "Cheat Sheet" in result["markdown_summary"]

    async def test_fire_tips_included(self, explain_type_matchup):
        """Test Fire type-specific tips are included."""
        result = await explain_type_matchup(
            attacking_type="Fire",
            defending_types=["Grass"]
        )
        md = result["markdown_summary"]
        assert "Tips" in md
        assert "Steel" in md or "Rain" in md  # Fire tips mention Steel or Rain

    async def test_water_tips_included(self, explain_type_matchup):
        """Test Water type-specific tips are included."""
        result = await explain_type_matchup(
            attacking_type="Water",
            defending_types=["Fire"]
        )
        md = result["markdown_summary"]
        assert "Tips" in md

    async def test_electric_tips_included(self, explain_type_matchup):
        """Test Electric type-specific tips are included."""
        result = await explain_type_matchup(
            attacking_type="Electric",
            defending_types=["Water"]
        )
        md = result["markdown_summary"]
        assert "Tips" in md
        assert "Ground" in md  # Electric tips mention Ground immunity

    async def test_ground_immune_to_electric(self, explain_type_matchup):
        """Test Ground immunity to Electric."""
        result = await explain_type_matchup(
            attacking_type="Electric",
            defending_types=["Ground"]
        )
        assert result["effectiveness"] == 0
        assert "NO EFFECT" in result["result"]

    async def test_response_has_all_fields(self, explain_type_matchup):
        """Test response structure has all expected fields."""
        result = await explain_type_matchup(
            attacking_type="Fire",
            defending_types=["Grass"]
        )
        assert "attacking_type" in result
        assert "defending_types" in result
        assert "effectiveness" in result
        assert "result" in result
        assert "markdown_summary" in result
