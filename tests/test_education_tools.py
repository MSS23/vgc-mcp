"""Tests for Pokemon education tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.education_tools import register_education_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    # Flutter Mane stats
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=55, attack=55, defense=55,
        special_attack=135, special_defense=135, speed=135
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Ghost", "Fairy"])
    client.get_pokemon_abilities = AsyncMock(return_value=["Protosynthesis"])
    return client


@pytest.fixture
def explain_pokemon(mock_pokeapi):
    """Register tools and return explain_pokemon function."""
    mcp = FastMCP("test")
    register_education_tools(mcp, mock_pokeapi)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools["explain_pokemon"].fn


class TestExplainPokemon:
    """Tests for the explain_pokemon tool."""

    async def test_basic_explanation(self, explain_pokemon):
        """Test basic Pokemon explanation."""
        result = await explain_pokemon(pokemon_name="flutter-mane")
        assert "error" not in result
        assert "markdown_summary" in result
        assert "role" in result
        assert "base_stats" in result

    async def test_sweeper_role_detection(self, explain_pokemon):
        """Test that fast + high SpA Pokemon is classified as sweeper."""
        result = await explain_pokemon(pokemon_name="flutter-mane")
        assert result["role"] == "Sweeper"

    async def test_tank_role_detection(self, explain_pokemon, mock_pokeapi):
        """Test that bulky Pokemon is classified as tank."""
        mock_pokeapi.get_base_stats.return_value = BaseStats(
            hp=114, attack=85, defense=70,
            special_attack=85, special_defense=80, speed=30
        )
        mock_pokeapi.get_pokemon_types.return_value = ["Grass", "Poison"]
        result = await explain_pokemon(pokemon_name="amoonguss")
        assert result["role"] in ["Tank", "Utility"]

    async def test_types_in_response(self, explain_pokemon):
        """Test that types are included in the response."""
        result = await explain_pokemon(pokemon_name="flutter-mane")
        assert "types" in result
        assert "Ghost" in result["types"]
        assert "Fairy" in result["types"]

    async def test_weaknesses_identified(self, explain_pokemon):
        """Test that weaknesses are identified."""
        result = await explain_pokemon(pokemon_name="flutter-mane")
        # Ghost/Fairy has weaknesses to Ghost and Steel
        assert "weaknesses" in result
        assert len(result["weaknesses"]) > 0

    async def test_markdown_has_stats_table(self, explain_pokemon):
        """Test markdown includes stats table."""
        result = await explain_pokemon(pokemon_name="flutter-mane")
        md = result["markdown_summary"]
        assert "Base Stats" in md
        assert "HP" in md or "hp" in md.lower()

    async def test_beginner_detail_level(self, explain_pokemon):
        """Test beginner detail level."""
        result = await explain_pokemon(
            pokemon_name="flutter-mane",
            detail_level="beginner"
        )
        assert "error" not in result

    async def test_advanced_detail_level(self, explain_pokemon):
        """Test advanced detail level."""
        result = await explain_pokemon(
            pokemon_name="flutter-mane",
            detail_level="advanced"
        )
        assert "error" not in result

    async def test_abilities_in_response(self, explain_pokemon):
        """Test that abilities are in the response."""
        result = await explain_pokemon(pokemon_name="flutter-mane")
        assert "abilities" in result
        assert "Protosynthesis" in result["abilities"]
