"""Tests for tournament readiness checking tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.readiness_tools import register_readiness_tools


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    # Return different types for different Pokemon
    type_map = {
        "flutter-mane": ["Ghost", "Fairy"],
        "incineroar": ["Fire", "Dark"],
        "rillaboom": ["Grass"],
        "urshifu-rapid-strike": ["Water", "Fighting"],
        "landorus": ["Ground", "Flying"],
        "tornadus": ["Flying"],
    }

    async def get_types(name):
        return type_map.get(name.lower(), ["Normal"])

    client.get_pokemon_types = AsyncMock(side_effect=get_types)
    return client


@pytest.fixture
def check_readiness(mock_pokeapi):
    """Register tools and return check_tournament_readiness function."""
    mcp = FastMCP("test")
    register_readiness_tools(mcp, mock_pokeapi)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools["check_tournament_readiness"].fn


class TestCheckTournamentReadiness:
    """Tests for the check_tournament_readiness tool."""

    async def test_valid_team(self, check_readiness):
        """Test readiness check with a valid 6-mon team."""
        team = [
            {"name": "flutter-mane", "moves": ["moonblast", "shadow-ball", "protect", "dazzling-gleam"]},
            {"name": "incineroar", "moves": ["fake-out", "flare-blitz", "knock-off", "protect"]},
            {"name": "rillaboom", "moves": ["grassy-glide", "wood-hammer", "fake-out", "protect"]},
            {"name": "urshifu-rapid-strike", "moves": ["surging-strikes", "close-combat", "aqua-jet", "protect"]},
            {"name": "landorus", "moves": ["earthquake", "rock-slide", "protect", "u-turn"]},
            {"name": "tornadus", "moves": ["tailwind", "bleakwind-storm", "protect", "taunt"]},
        ]
        result = await check_readiness(team_pokemon=team)
        assert "error" not in result
        assert "overall_score" in result
        assert "rating" in result
        assert "category_scores" in result

    async def test_wrong_team_size(self, check_readiness):
        """Test that non-6 team returns error."""
        team = [{"name": "flutter-mane", "moves": []}]
        result = await check_readiness(team_pokemon=team)
        assert "error" in result

    async def test_speed_control_with_tailwind(self, check_readiness):
        """Test that Tailwind presence boosts speed control score."""
        team = [
            {"name": "flutter-mane", "moves": []},
            {"name": "incineroar", "moves": []},
            {"name": "rillaboom", "moves": []},
            {"name": "urshifu-rapid-strike", "moves": []},
            {"name": "landorus", "moves": []},
            {"name": "tornadus", "moves": ["tailwind"]},
        ]
        result = await check_readiness(team_pokemon=team)
        assert result["category_scores"]["speed_control"] >= 80

    async def test_no_speed_control(self, check_readiness):
        """Test low speed control score without Tailwind or Trick Room."""
        team = [
            {"name": "flutter-mane", "moves": ["moonblast"]},
            {"name": "incineroar", "moves": ["flare-blitz"]},
            {"name": "rillaboom", "moves": ["wood-hammer"]},
            {"name": "urshifu-rapid-strike", "moves": ["surging-strikes"]},
            {"name": "landorus", "moves": ["earthquake"]},
            {"name": "tornadus", "moves": ["bleakwind-storm"]},
        ]
        result = await check_readiness(team_pokemon=team)
        assert result["category_scores"]["speed_control"] <= 60

    async def test_priority_moves_scored(self, check_readiness):
        """Test that priority moves give some speed control score."""
        team = [
            {"name": "flutter-mane", "moves": []},
            {"name": "incineroar", "moves": ["fake-out"]},
            {"name": "rillaboom", "moves": []},
            {"name": "urshifu-rapid-strike", "moves": ["extreme-speed"]},
            {"name": "landorus", "moves": []},
            {"name": "tornadus", "moves": []},
        ]
        result = await check_readiness(team_pokemon=team)
        assert result["category_scores"]["speed_control"] >= 60

    async def test_type_coverage_diverse(self, check_readiness):
        """Test good type coverage score with diverse types."""
        team = [
            {"name": "flutter-mane", "moves": []},  # Ghost/Fairy
            {"name": "incineroar", "moves": []},     # Fire/Dark
            {"name": "rillaboom", "moves": []},      # Grass
            {"name": "urshifu-rapid-strike", "moves": []},  # Water/Fighting
            {"name": "landorus", "moves": []},       # Ground/Flying
            {"name": "tornadus", "moves": []},       # Flying
        ]
        result = await check_readiness(team_pokemon=team)
        # 8+ unique types: Ghost, Fairy, Fire, Dark, Grass, Water, Fighting, Ground, Flying
        assert result["category_scores"]["type_coverage"] >= 85

    async def test_rating_letters(self, check_readiness):
        """Test that rating is a valid letter grade."""
        team = [
            {"name": "flutter-mane", "moves": ["tailwind"]},
            {"name": "incineroar", "moves": []},
            {"name": "rillaboom", "moves": []},
            {"name": "urshifu-rapid-strike", "moves": []},
            {"name": "landorus", "moves": []},
            {"name": "tornadus", "moves": []},
        ]
        result = await check_readiness(team_pokemon=team)
        assert result["rating"] in ["A", "B+", "B", "C+", "C"]

    async def test_markdown_summary(self, check_readiness):
        """Test markdown summary is included."""
        team = [
            {"name": "flutter-mane", "moves": []},
            {"name": "incineroar", "moves": []},
            {"name": "rillaboom", "moves": []},
            {"name": "urshifu-rapid-strike", "moves": []},
            {"name": "landorus", "moves": []},
            {"name": "tornadus", "moves": []},
        ]
        result = await check_readiness(team_pokemon=team)
        assert "markdown_summary" in result
        assert "Tournament Readiness" in result["markdown_summary"]
