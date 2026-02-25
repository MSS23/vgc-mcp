"""Tests for Pokemon context persistence tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.context_tools import register_context_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=115, attack=115, defense=85,
        special_attack=90, special_defense=75, speed=100
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Fire"])
    client.get_pokemon_abilities = AsyncMock(return_value=["Inner Focus"])
    client.get_pokemon = AsyncMock(return_value={
        "name": "entei",
        "types": ["Fire"],
    })
    return client


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager with context methods."""
    manager = MagicMock()
    _context_store = {}
    _active = [None]

    def set_context(name, build):
        _context_store[name.lower()] = build
        _active[0] = name.lower()
        return True, f"Stored {name}"

    def get_context(reference=None):
        if reference:
            ref = reference.lower().replace("my ", "")
            return _context_store.get(ref)
        if _active[0]:
            return _context_store.get(_active[0])
        return None

    def list_context():
        return [
            {"reference": k, "name": k.title(), "nature": v.nature.value.title(), "is_active": k == _active[0]}
            for k, v in _context_store.items()
        ]

    def clear_context(reference=None):
        if reference:
            ref = reference.lower().replace("my ", "")
            if ref in _context_store:
                del _context_store[ref]
                return True, f"Cleared {ref}"
            return False, f"Not found: {ref}"
        _context_store.clear()
        _active[0] = None
        return True, "Cleared all"

    manager.set_pokemon_context = MagicMock(side_effect=set_context)
    manager.get_pokemon_context = MagicMock(side_effect=get_context)
    manager.list_pokemon_context = MagicMock(side_effect=list_context)
    manager.clear_pokemon_context = MagicMock(side_effect=clear_context)
    manager.active_pokemon_name = property(lambda self: _active[0])
    manager.size = 0
    manager.get_current_team = MagicMock(return_value=None)
    manager.clear = MagicMock(return_value=(True, "Cleared", {}))
    return manager


@pytest.fixture
def tools(mock_pokeapi, mock_team_manager):
    """Register context tools and return functions."""
    mcp = FastMCP("test")
    register_context_tools(mcp, mock_pokeapi, mock_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestSetMyPokemon:
    """Tests for set_my_pokemon."""

    async def test_set_basic_pokemon(self, tools):
        """Test storing a basic Pokemon."""
        fn = tools["set_my_pokemon"].fn
        result = await fn(
            pokemon_name="entei",
            nature="Adamant",
            hp_evs=4, atk_evs=252, spe_evs=252
        )
        assert result["success"] is True
        assert "final_stats" in result
        assert result["evs"]["total"] == 508

    async def test_set_with_item_and_ability(self, tools):
        """Test storing Pokemon with item and ability."""
        fn = tools["set_my_pokemon"].fn
        result = await fn(
            pokemon_name="entei",
            nature="Adamant",
            atk_evs=252, spe_evs=252, hp_evs=4,
            ability="Inner Focus",
            item="Choice Band",
            tera_type="Fire"
        )
        assert result["success"] is True
        assert result["item"] == "Choice Band"
        assert result["tera_type"] == "Fire"

    async def test_exceeding_evs(self, tools):
        """Test that exceeding 508 EVs returns error."""
        fn = tools["set_my_pokemon"].fn
        result = await fn(
            pokemon_name="entei",
            nature="Adamant",
            hp_evs=252, atk_evs=252, spe_evs=252  # 756 total
        )
        assert result["success"] is False
        assert "508" in result["error"]

    async def test_invalid_nature(self, tools):
        """Test invalid nature returns error."""
        fn = tools["set_my_pokemon"].fn
        result = await fn(
            pokemon_name="entei",
            nature="InvalidNature"
        )
        assert result["success"] is False
        assert "nature" in result["error"].lower()


class TestGetMyPokemon:
    """Tests for get_my_pokemon."""

    async def test_get_after_set(self, tools):
        """Test retrieving a stored Pokemon."""
        set_fn = tools["set_my_pokemon"].fn
        get_fn = tools["get_my_pokemon"].fn

        await set_fn(pokemon_name="entei", nature="Adamant", atk_evs=252, spe_evs=252, hp_evs=4)
        result = await get_fn(reference="entei")
        assert result["found"] is True
        assert result["name"] == "entei"

    async def test_get_nonexistent(self, tools):
        """Test getting a Pokemon that wasn't stored."""
        fn = tools["get_my_pokemon"].fn
        result = await fn(reference="nonexistent")
        assert result["found"] is False


class TestListMyPokemon:
    """Tests for list_my_pokemon."""

    async def test_empty_list(self, tools):
        """Test listing when nothing is stored."""
        fn = tools["list_my_pokemon"].fn
        result = await fn()
        assert result["count"] == 0

    async def test_list_after_set(self, tools):
        """Test listing after storing a Pokemon."""
        set_fn = tools["set_my_pokemon"].fn
        list_fn = tools["list_my_pokemon"].fn

        await set_fn(pokemon_name="entei", nature="Adamant", atk_evs=252, spe_evs=252, hp_evs=4)
        result = await list_fn()
        assert result["count"] == 1


class TestClearMyPokemon:
    """Tests for clear_my_pokemon."""

    async def test_clear_specific(self, tools):
        """Test clearing a specific Pokemon."""
        set_fn = tools["set_my_pokemon"].fn
        clear_fn = tools["clear_my_pokemon"].fn

        await set_fn(pokemon_name="entei", nature="Adamant", atk_evs=252, spe_evs=252, hp_evs=4)
        result = await clear_fn(reference="entei")
        assert result["success"] is True

    async def test_clear_all(self, tools):
        """Test clearing all stored Pokemon."""
        set_fn = tools["set_my_pokemon"].fn
        clear_fn = tools["clear_my_pokemon"].fn

        await set_fn(pokemon_name="entei", nature="Adamant", atk_evs=252, spe_evs=252, hp_evs=4)
        result = await clear_fn(reference=None)
        assert result["success"] is True
        assert result["remaining"] == 0


class TestResetSession:
    """Tests for reset_session."""

    async def test_reset_empty_session(self, tools):
        """Test resetting an empty session."""
        fn = tools["reset_session"].fn
        result = await fn()
        assert result["success"] is True
        assert "cleared" in result

    async def test_reset_has_next_steps(self, tools):
        """Test reset provides next steps."""
        fn = tools["reset_session"].fn
        result = await fn()
        assert "next_steps" in result
        assert len(result["next_steps"]) > 0


class TestSessionStatus:
    """Tests for session_status."""

    async def test_empty_session_status(self, tools):
        """Test status of empty session."""
        fn = tools["session_status"].fn
        result = await fn()
        assert result["has_existing_data"] is False
        assert result["stored_pokemon"]["count"] == 0
        assert result["team"]["size"] == 0

    async def test_status_has_note(self, tools):
        """Test status includes a contextual note."""
        fn = tools["session_status"].fn
        result = await fn()
        assert "note" in result
