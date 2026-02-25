"""Tests for build state management tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.build_tools import register_build_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=95, attack=115, defense=90,
        special_attack=80, special_defense=90, speed=60
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Fire", "Dark"])
    client.get_abilities = AsyncMock(return_value=["Intimidate", "Blaze"])
    return client


@pytest.fixture
def mock_build_manager():
    """Create a mock build state manager."""
    manager = MagicMock()
    manager.create_build = MagicMock(return_value="build-001")
    manager.get_build = MagicMock(return_value={
        "build_id": "build-001",
        "pokemon": "incineroar",
        "nature": "Careful",
        "ability": "Intimidate",
        "item": "Safety Goggles",
        "tera_type": "Ghost",
        "evs": {"hp": 252, "attack": 4, "defense": 116, "special_attack": 0, "special_defense": 4, "speed": 132},
        "moves": ["Fake Out", "Flare Blitz"]
    })
    manager.get_build_by_name = MagicMock(return_value={
        "build_id": "build-001",
        "pokemon": "incineroar",
        "nature": "Careful",
        "ability": "Intimidate",
        "item": "Safety Goggles",
        "tera_type": "Ghost",
        "evs": {"hp": 252, "attack": 4, "defense": 116, "special_attack": 0, "special_defense": 4, "speed": 132},
        "moves": ["Fake Out", "Flare Blitz"]
    })
    manager.list_builds = MagicMock(return_value=[{
        "build_id": "build-001",
        "pokemon": "incineroar",
        "nature": "Careful"
    }])
    manager.update_build = MagicMock()
    return manager


@pytest.fixture
def tools(mock_pokeapi, mock_build_manager):
    """Register build tools and return functions."""
    mcp = FastMCP("test")
    register_build_tools(mcp, mock_build_manager, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestCreateBuild:
    """Tests for create_build."""

    async def test_basic_build(self, tools):
        """Test creating a basic Pokemon build."""
        fn = tools["create_build"].fn
        result = await fn(pokemon_name="incineroar", nature="Careful")
        assert result["success"] is True
        assert result["build_id"] == "build-001"
        assert result["build"]["pokemon"] == "incineroar"

    async def test_build_with_all_fields(self, tools):
        """Test creating a build with all optional fields."""
        fn = tools["create_build"].fn
        result = await fn(
            pokemon_name="incineroar",
            nature="Careful",
            ability="Intimidate",
            item="Safety Goggles",
            tera_type="Ghost",
            move1="Fake Out",
            move2="Flare Blitz",
            hp_evs=252, spe_evs=132
        )
        assert result["success"] is True
        assert result["build"]["ability"] == "Intimidate"
        assert result["build"]["item"] == "Safety Goggles"

    async def test_api_error(self, tools, mock_pokeapi):
        """Test build creation when API fails."""
        mock_pokeapi.get_base_stats.side_effect = Exception("API error")
        fn = tools["create_build"].fn
        result = await fn(pokemon_name="unknown-mon")
        assert result["success"] is False


class TestModifyBuild:
    """Tests for modify_build."""

    async def test_modify_nature(self, tools):
        """Test modifying an existing build's nature."""
        fn = tools["modify_build"].fn
        result = await fn(pokemon_name="incineroar", nature="Adamant")
        assert result["success"] is True
        assert "nature" in result.get("changes", [])

    async def test_modify_nonexistent(self, tools, mock_build_manager):
        """Test modifying a build that doesn't exist."""
        mock_build_manager.get_build_by_name.return_value = None
        fn = tools["modify_build"].fn
        result = await fn(pokemon_name="not-a-build")
        assert result["success"] is False


class TestListBuilds:
    """Tests for list_builds."""

    async def test_list_builds(self, tools):
        """Test listing existing builds."""
        fn = tools["list_builds"].fn
        result = await fn()
        assert "builds" in result or "count" in result


class TestGetBuildState:
    """Tests for get_build_state."""

    async def test_get_build(self, tools):
        """Test getting a build by name."""
        fn = tools["get_build_state"].fn
        result = await fn(pokemon_name="incineroar")
        assert result.get("success") is True or "build" in result
