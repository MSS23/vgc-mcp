"""Tests for move legality and learnset validation tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.move_tools import register_move_tools


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock()
    manager.get_current_team.return_value = None
    return manager


@pytest.fixture
def tools(mock_pokeapi, mock_smogon, mock_team_manager):
    """Register move tools and return functions."""
    mcp = FastMCP("test")
    register_move_tools(mcp, mock_pokeapi, mock_smogon, mock_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestValidatePokemonMoveset:
    """Tests for validate_pokemon_moveset."""

    async def test_all_legal_moves(self, tools, mock_pokeapi):
        """Test validation with all legal moves."""
        from unittest.mock import MagicMock as MM
        result_mock = MM()
        result_mock.pokemon = "incineroar"
        result_mock.all_legal = True
        result_mock.moves = []
        result_mock.illegal_moves = []

        # We need to mock the validate_moveset function
        import vgc_mcp.tools.move_tools as mod
        original = mod.validate_moveset
        async def mock_validate(name, moves, api):
            return result_mock
        mod.validate_moveset = mock_validate

        try:
            fn = tools["validate_pokemon_moveset"].fn
            result = await fn(pokemon_name="incineroar", moves=["Fake Out", "Flare Blitz"])
            assert result["all_legal"] is True
            assert result["pokemon"] == "incineroar"
        finally:
            mod.validate_moveset = original


class TestGetPokemonLearnableMoves:
    """Tests for get_pokemon_learnable_moves."""

    async def test_learnable_moves(self, tools):
        """Test getting learnable moves."""
        import vgc_mcp.tools.move_tools as mod
        original = mod.get_learnable_moves
        async def mock_get(name, api, method=None):
            return {
                "pokemon": name,
                "move_count": 2,
                "moves": {
                    "flare-blitz": ["level-up"],
                    "fake-out": ["egg"]
                }
            }
        mod.get_learnable_moves = mock_get

        try:
            fn = tools["get_pokemon_learnable_moves"].fn
            result = await fn(pokemon_name="incineroar")
            assert result["pokemon"] == "incineroar"
            assert result["total_moves"] == 2
            assert "moves_by_method" in result
        finally:
            mod.get_learnable_moves = original

    async def test_error_result(self, tools):
        """Test error returned for invalid Pokemon."""
        import vgc_mcp.tools.move_tools as mod
        original = mod.get_learnable_moves
        async def mock_get(name, api, method=None):
            return {"error": "Pokemon not found"}
        mod.get_learnable_moves = mock_get

        try:
            fn = tools["get_pokemon_learnable_moves"].fn
            result = await fn(pokemon_name="fakemon")
            assert "error" in result
        finally:
            mod.get_learnable_moves = original


class TestCheckTeamMovesets:
    """Tests for check_team_movesets."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["check_team_movesets"].fn
        result = await fn()
        assert result["valid"] is True
        assert "No Pokemon" in result["message"]


class TestCheckEggMoves:
    """Tests for check_egg_moves."""

    async def test_egg_moves(self, tools):
        """Test getting egg moves."""
        import vgc_mcp.tools.move_tools as mod
        original = mod.get_learnable_moves
        async def mock_get(name, api, method=None):
            return {
                "pokemon": name,
                "moves": {"fake-out": ["egg"]}
            }
        mod.get_learnable_moves = mock_get

        try:
            fn = tools["check_egg_moves"].fn
            result = await fn(pokemon_name="incineroar")
            assert result["pokemon"] == "incineroar"
            assert result["egg_move_count"] == 1
        finally:
            mod.get_learnable_moves = original


class TestCheckTmMoves:
    """Tests for check_tm_moves."""

    async def test_tm_moves(self, tools):
        """Test getting TM moves."""
        import vgc_mcp.tools.move_tools as mod
        original = mod.get_learnable_moves
        async def mock_get(name, api, method=None):
            return {
                "pokemon": name,
                "moves": {"flare-blitz": ["machine"], "earthquake": ["machine"]}
            }
        mod.get_learnable_moves = mock_get

        try:
            fn = tools["check_tm_moves"].fn
            result = await fn(pokemon_name="incineroar")
            assert result["pokemon"] == "incineroar"
            assert result["tm_move_count"] == 2
        finally:
            mod.get_learnable_moves = original


class TestFindMoveLearners:
    """Tests for find_move_learners."""

    async def test_no_team_only(self, tools):
        """Test without team_only returns guidance."""
        fn = tools["find_move_learners"].fn
        result = await fn(move_name="fake-out", team_only=False)
        assert "suggestion" in result

    async def test_team_only_empty(self, tools):
        """Test team_only with empty team."""
        fn = tools["find_move_learners"].fn
        result = await fn(move_name="fake-out", team_only=True)
        assert result["learners"] == []
