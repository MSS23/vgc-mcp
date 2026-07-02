"""Tests for EV spread optimization tools."""

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.spread_tools import register_spread_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()

    async def _get_base_stats(name):
        stats = {
            "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
            "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
        }
        return stats.get(name.lower(), BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80))

    async def _get_types(name):
        types_map = {
            "flutter-mane": ["Ghost", "Fairy"],
            "incineroar": ["Fire", "Dark"],
        }
        return types_map.get(name.lower(), ["Normal"])

    async def _get_abilities(name):
        return ["Protosynthesis"]

    client.get_base_stats = AsyncMock(side_effect=_get_base_stats)
    client.get_pokemon_types = AsyncMock(side_effect=_get_types)
    client.get_pokemon_abilities = AsyncMock(side_effect=_get_abilities)
    return client


@pytest.fixture
def tools(mock_pokeapi):
    """Register spread tools and return functions."""
    mcp = FastMCP("test")
    register_spread_tools(mcp, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestCheckSpreadEfficiency:
    """Tests for check_spread_efficiency."""

    async def test_basic_efficiency(self, tools):
        """Test basic spread efficiency check."""
        fn = tools["check_spread_efficiency"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="timid",
            spa_evs=252,
            spe_evs=252,
            hp_evs=4
        )
        assert isinstance(result, dict)
        assert "error" not in result

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["check_spread_efficiency"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="notanature"
        )
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["check_spread_efficiency"].fn
        result = await fn(
            pokemon_name="fakemon",
            nature="timid"
        )
        assert "error" in result


class TestSuggestNatureOptimization:
    """Tests for suggest_nature_optimization."""

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["suggest_nature_optimization"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            current_nature="notanature",
            hp_evs=4, atk_evs=0, def_evs=0,
            spa_evs=252, spd_evs=0, spe_evs=252
        )
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["suggest_nature_optimization"].fn
        result = await fn(
            pokemon_name="fakemon",
            current_nature="timid",
            hp_evs=4, atk_evs=0, def_evs=0,
            spa_evs=252, spd_evs=0, spe_evs=252
        )
        assert "error" in result


class TestOptimizeBulk:
    """Tests for optimize_bulk."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["optimize_bulk"].fn
        result = await fn(
            pokemon_name="fakemon",
            nature="bold",
            total_bulk_evs=252
        )
        assert "error" in result

    async def test_basic_optimization(self, tools):
        """Test basic bulk optimization."""
        fn = tools["optimize_bulk"].fn
        result = await fn(
            pokemon_name="incineroar",
            nature="careful",
            total_bulk_evs=252
        )
        assert isinstance(result, dict)
        assert "error" not in result


class TestSuggestSpread:
    """Tests for suggest_spread."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["suggest_spread"].fn
        result = await fn(pokemon_name="fakemon")
        assert "error" in result

    async def test_basic_suggestion(self, tools):
        """Test basic spread suggestion."""
        fn = tools["suggest_spread"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            role="offensive"
        )
        assert isinstance(result, dict)


class TestAnalyzeBulkDiminishingReturns:
    """Tests for analyze_bulk_diminishing_returns."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["analyze_bulk_diminishing_returns"].fn
        result = await fn(
            pokemon_name="fakemon",
            nature="bold"
        )
        assert "error" in result


class TestAnalyzeHpNumber:
    """Tests for analyze_hp_number."""

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["analyze_hp_number"].fn
        result = await fn(pokemon_name="fakemon", item="life-orb")
        assert "error" in result

    async def test_basic_analysis(self, tools):
        """Test basic HP number analysis."""
        fn = tools["analyze_hp_number"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            item="life-orb",
            current_hp_evs=4
        )
        assert isinstance(result, dict)


class TestOptimizeDualSurvivalHpItemPath:
    """Regression tests for the HP-item-optimization branch of
    optimize_dual_survival_spread, which previously crashed with
    NameError (undefined `mods1`/`mods2`) whenever a defender item
    triggered an HP EV adjustment."""

    @pytest.fixture
    def dual_tools(self, mock_pokeapi, monkeypatch):
        """Spread tools with move support and Smogon lookups silenced."""
        from vgc_mcp_core.models.move import Move, MoveCategory

        moves = {
            "moonblast": Move(name="moonblast", type="fairy", category=MoveCategory.SPECIAL, power=95),
            "flare-blitz": Move(name="flare-blitz", type="fire", category=MoveCategory.PHYSICAL, power=120),
        }

        async def _get_move(name, user_name=None):
            return moves[name.lower()]

        mock_pokeapi.get_move = AsyncMock(side_effect=_get_move)

        import vgc_mcp.tools.spread_tools as st

        async def _no_spread(name):
            return None

        monkeypatch.setattr(st, "_get_common_spread", _no_spread)

        mcp = FastMCP("test")
        register_spread_tools(mcp, mock_pokeapi)
        return {t.name: t for t in mcp._tool_manager._tools.values()}

    async def test_item_hp_adjustment_does_not_crash(self, dual_tools, monkeypatch):
        """Force the HP adjustment branch and verify no NameError/error response."""
        import vgc_mcp_core.calc.hp_optimization as hp_opt

        def _force_adjust(base_hp, current_evs, item, max_adjustment=12):
            # Always propose a different HP EV count so the re-verify
            # branch (the previously broken code path) executes.
            adjusted = current_evs - 8 if current_evs >= 8 else current_evs + 8
            return {"adjusted_evs": adjusted, "reason": "forced for regression test"}

        monkeypatch.setattr(hp_opt, "adjust_hp_evs_for_item", _force_adjust)

        fn = dual_tools["optimize_dual_survival_spread"].fn
        result = await fn(
            pokemon_name="incineroar",
            survive_hit1_attacker="flutter-mane",
            survive_hit1_move="moonblast",
            survive_hit1_nature="timid",
            survive_hit1_evs=252,
            survive_hit2_attacker="incineroar",
            survive_hit2_move="flare-blitz",
            survive_hit2_nature="adamant",
            survive_hit2_evs=252,
            nature="careful",
            item="leftovers",
        )
        assert isinstance(result, dict)
        # Before the fix this returned {"error": ..., "message": "name 'mods1' is not defined"}
        assert "error" not in result, f"unexpected error: {result.get('message')}"

    async def test_item_no_adjustment_still_works(self, dual_tools):
        """Sanity: the tool works end-to-end with an item and real adjuster."""
        fn = dual_tools["optimize_dual_survival_spread"].fn
        result = await fn(
            pokemon_name="incineroar",
            survive_hit1_attacker="flutter-mane",
            survive_hit1_move="moonblast",
            survive_hit1_nature="timid",
            survive_hit1_evs=252,
            survive_hit2_attacker="incineroar",
            survive_hit2_move="flare-blitz",
            survive_hit2_nature="adamant",
            survive_hit2_evs=252,
            nature="careful",
            item="leftovers",
        )
        assert isinstance(result, dict)
        assert "error" not in result, f"unexpected error: {result.get('message')}"
