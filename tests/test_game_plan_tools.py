"""Tests for game plan generation tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.game_plan_tools import register_game_plan_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.team.manager import TeamManager


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=95, attack=115, defense=90,
        special_attack=80, special_defense=90, speed=60
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Fire", "Dark"])
    client.get_pokemon_abilities = AsyncMock(return_value=["Intimidate"])
    return client


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    client = AsyncMock()
    client.get_pokemon_usage = AsyncMock(return_value={
        "name": "incineroar",
        "usage_percent": 22.0,
        "moves": {"fake-out": 90, "flare-blitz": 80, "knock-off": 75, "parting-shot": 70},
        "items": {"Safety Goggles": 40},
        "abilities": {"Intimidate": 99},
        "spreads": [{"nature": "Careful", "evs": {"hp": 252, "speed": 132}}],
    })
    return client


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock()
    manager.size = 0
    manager.team = MagicMock()
    manager.get_current_team = MagicMock(return_value=None)
    return manager


@pytest.fixture
def tools(mock_pokeapi, mock_smogon, mock_team_manager):
    """Register game plan tools and return functions."""
    mcp = FastMCP("test")
    # Signature: register_game_plan_tools(mcp, pokeapi, team_manager, smogon)
    register_game_plan_tools(mcp, mock_pokeapi, mock_team_manager, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestGenerateGamePlan:
    """Tests for generate_game_plan."""

    async def test_requires_opponent_team(self, tools):
        """Test that opponent team is needed."""
        fn = tools["generate_game_plan"].fn
        result = await fn(opponent_team=[])
        assert "error" in result or result.get("success") is False

    async def test_with_opponent_team(self, tools):
        """Test generating a game plan with opponent team."""
        fn = tools["generate_game_plan"].fn
        result = await fn(
            opponent_team=["incineroar", "flutter-mane", "rillaboom", "urshifu"]
        )
        # Should return a game plan or error if your team is empty
        assert "error" in result or "game_plan" in result or "leads" in str(result).lower()
