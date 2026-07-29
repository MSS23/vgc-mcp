"""Tests for speed analysis, comparison, and speed control tools."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.speed_analysis_tools import register_speed_analysis_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.team.manager import TeamManager


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    # Flutter Mane: 135 base speed
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=55, attack=55, defense=55,
        special_attack=135, special_defense=135, speed=135
    ))
    return client


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock(spec=TeamManager)
    manager.size = 0
    manager.team = MagicMock()
    return manager


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    return AsyncMock()


@pytest.fixture
def tools(mock_pokeapi, mock_team_manager, mock_smogon):
    """Register speed analysis tools and return functions."""
    mcp = FastMCP("test")
    register_speed_analysis_tools(mcp, mock_pokeapi, mock_team_manager, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestCompareSpeed:
    """Tests for compare_speed."""

    async def test_same_pokemon_same_evs(self, tools):
        """Test speed comparison with identical Pokemon."""
        fn = tools["compare_speed"].fn
        result = await fn(
            pokemon1_name="flutter-mane",
            pokemon2_name="flutter-mane"
        )
        assert "tie" in result.get("winner", "").lower() or "tie" in result.get("result", "").lower()

    async def test_faster_pokemon_wins(self, tools, mock_pokeapi):
        """Test that faster Pokemon is correctly identified."""
        # First call returns Flutter Mane (135 base), second returns Incineroar (60 base)
        mock_pokeapi.get_base_stats.side_effect = [
            BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
            BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
        ]
        fn = tools["compare_speed"].fn
        result = await fn(
            pokemon1_name="flutter-mane",
            pokemon1_nature="timid",
            pokemon1_speed_evs=252,
            pokemon2_name="incineroar",
            pokemon2_nature="careful",
            pokemon2_speed_evs=0
        )
        assert result["winner"] == "flutter-mane"

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["compare_speed"].fn
        result = await fn(
            pokemon1_name="flutter-mane",
            pokemon1_nature="InvalidNature",
            pokemon2_name="incineroar"
        )
        assert "error" in result


class TestGetSpeedTiers:
    """Tests for get_speed_tiers."""

    async def test_returns_tiers(self, tools):
        """Test that speed tiers are returned."""
        fn = tools["get_speed_tiers"].fn
        result = await fn()
        assert "tiers" in result or "speed_tiers" in result


class TestAnalyzeSpeedSpread:
    """Tests for analyze_speed_spread."""

    async def test_basic_spread(self, tools):
        """Test basic speed spread analysis."""
        fn = tools["analyze_speed_spread"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="timid",
            speed_evs=252
        )
        assert "error" not in result or "speed" in str(result).lower()


class TestFindSpeedEvsToOutspeed:
    """Tests for find_speed_evs_to_outspeed (mainline path)."""

    async def test_reachable_target(self, tools):
        fn = tools["find_speed_evs_to_outspeed"].fn
        # Base 135 speed, Jolly: 252 EVs reaches 205 — 180 is reachable
        result = await fn(pokemon_name="flutter-mane", target_speed=180, nature="jolly")
        assert result["achievable"] is True
        assert result["actual_speed"] >= 180
        assert 0 <= result["evs_needed"] <= 252
        assert result["evs_remaining"] == 508 - result["evs_needed"]

    async def test_unreachable_target(self, tools):
        fn = tools["find_speed_evs_to_outspeed"].fn
        result = await fn(pokemon_name="flutter-mane", target_speed=400, nature="jolly")
        assert result["achievable"] is False
        assert result["max_speed_with_252_evs"] < 400

    async def test_invalid_nature(self, tools):
        fn = tools["find_speed_evs_to_outspeed"].fn
        result = await fn(pokemon_name="flutter-mane", target_speed=150, nature="zesty")
        assert result["success"] is False


class TestFindSpeedBenchmark:
    """Tests for find_speed_benchmark."""

    async def test_meta_tiers_returned(self, tools):
        fn = tools["find_speed_benchmark"].fn
        result = await fn(target_speed=135)
        for key in ("pokemon_at_this_speed", "pokemon_above", "pokemon_below"):
            assert key in result

    async def test_with_pokemon_computes_required_evs(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(return_value={
            "base_stats": {"hp": 55, "attack": 55, "defense": 55,
                           "special_attack": 135, "special_defense": 135, "speed": 135},
        })
        fn = tools["find_speed_benchmark"].fn
        result = await fn(target_speed=170, nature="timid", pokemon_name="flutter-mane")
        mon = result["your_pokemon"]
        assert mon["can_reach"] is True
        assert mon["resulting_speed"] >= 170

    async def test_invalid_nature_falls_back_to_jolly(self, tools):
        fn = tools["find_speed_benchmark"].fn
        result = await fn(target_speed=135, nature="not-a-nature")
        assert "pokemon_at_this_speed" in result  # no error, fallback applied


class TestTeamConditionToolsRequireTeam:
    """All team-wide speed tools must refuse cleanly on an empty team."""

    @pytest.mark.parametrize("tool_name,kwargs", [
        ("analyze_team_trick_room", {}),
        ("analyze_team_tailwind", {}),
        ("analyze_paralysis_matchup", {}),
        ("analyze_speed_drops", {"stages": -1}),
    ])
    async def test_empty_team_is_error(self, tools, tool_name, kwargs):
        result = await tools[tool_name].fn(**kwargs)
        assert result["success"] is False


class TestTeamConditionToolsWithTeam:
    """Happy paths against a real TeamManager with real builds."""

    @pytest.fixture
    def loaded_tools(self, mock_pokeapi, mock_smogon):
        from vgc_mcp_core.models.pokemon import EVSpread, Nature, PokemonBuild

        manager = TeamManager()
        manager.add_pokemon(PokemonBuild(
            name="ursaluna",
            base_stats=BaseStats(hp=130, attack=140, defense=105,
                                 special_attack=45, special_defense=80, speed=50),
            nature=Nature.BRAVE, evs=EVSpread(hp=252, attack=252),
            types=["ground", "normal"],
        ))
        manager.add_pokemon(PokemonBuild(
            name="flutter-mane",
            base_stats=BaseStats(hp=55, attack=55, defense=55,
                                 special_attack=135, special_defense=135, speed=135),
            nature=Nature.TIMID, evs=EVSpread(special_attack=252, speed=252),
            types=["ghost", "fairy"],
        ))
        mcp = FastMCP("test")
        register_speed_analysis_tools(mcp, mock_pokeapi, manager, mock_smogon)
        return {t.name: t.fn for t in mcp._tool_manager._tools.values()}

    async def test_trick_room_orders_slowest_first(self, loaded_tools):
        result = await loaded_tools["analyze_team_trick_room"]()
        assert result.get("success", True) is not False
        assert len(result["speeds"]) == 2
        # In Trick Room the slow Ursaluna must move before Flutter Mane
        assert result["move_order"].index("ursaluna") < result["move_order"].index("flutter-mane")

    async def test_speed_drops_reports_team_speeds(self, loaded_tools):
        result = await loaded_tools["analyze_speed_drops"](stages=-1)
        assert result.get("success", True) is not False
        names = {s["name"] for s in result["your_speeds"]}
        assert names == {"ursaluna", "flutter-mane"}
