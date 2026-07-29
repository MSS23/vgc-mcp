"""Tests for the live-battle copilot tools.

Uses a real BattleStateManager (pure in-memory state, no I/O) so these
exercise the genuine state machine: leads, HP/status updates, reveals,
Tera accounting, field timers, and the full start → record → suggest →
end lifecycle.
"""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.battle_tools import register_battle_tools
from vgc_mcp_core.state import BattleStateManager

MY_TEAM = ["flutter-mane", "urshifu-rapid-strike", "incineroar", "rillaboom"]
OPP_TEAM = ["tornadus", "amoonguss", "chi-yu", "landorus"]


@pytest.fixture
def tools():
    mcp = FastMCP("test")
    register_battle_tools(mcp, BattleStateManager())
    return {t.name: t.fn for t in mcp._tool_manager._tools.values()}


async def _started(tools):
    result = await tools["start_battle"](
        my_team=MY_TEAM,
        opp_team=OPP_TEAM,
        my_lead=["flutter-mane", "urshifu-rapid-strike"],
        opp_lead=["tornadus", "amoonguss"],
    )
    assert result["success"] is True
    return result


class TestStartBattle:
    async def test_start_returns_initial_state(self, tools):
        result = await _started(tools)
        assert result["turn"] == 1
        assert result["my_team"] == MY_TEAM
        assert result["my_lead"] == ["flutter-mane", "urshifu-rapid-strike"]

    async def test_team_size_is_validated(self, tools):
        result = await tools["start_battle"](my_team=["a", "b"], opp_team=OPP_TEAM)
        assert result["success"] is False

    async def test_new_battle_replaces_old(self, tools):
        await _started(tools)
        result = await tools["start_battle"](my_team=OPP_TEAM, opp_team=MY_TEAM)
        assert result["success"] is True
        state = await tools["get_battle_state"]()
        assert state["turn"] == 1


class TestNoActiveBattle:
    """Every stateful tool must refuse cleanly when no battle exists."""

    @pytest.mark.parametrize("tool_name", [
        "record_turn", "suggest_next_move", "get_battle_state", "end_battle",
    ])
    async def test_requires_active_battle(self, tools, tool_name):
        result = await tools[tool_name]()
        assert result["success"] is False
        assert "start_battle" in result["message"] or "battle" in result["message"].lower()


class TestRecordTurn:
    async def test_hp_status_and_reveals_are_applied(self, tools):
        await _started(tools)
        result = await tools["record_turn"](
            events="Tornadus revealed Covert Cloak; Chi-Yu burned Incineroar",
            hp_changes={"opp/tornadus": 55.0, "me/flutter-mane": 80.0},
            status_changes={"me/incineroar": "burn"},
            revealed_items={"opp/tornadus": "covert-cloak"},
            revealed_abilities={"opp/amoonguss": "regenerator"},
        )
        assert result["success"] is True
        assert result["turn"] == 2

        state = await tools["get_battle_state"]()
        opp = {p["name"]: p for p in state["opp_team"]}
        me = {p["name"]: p for p in state["my_team"]}
        assert opp["tornadus"]["hp_percent"] == 55.0
        assert opp["tornadus"]["revealed_item"] == "covert-cloak"
        assert opp["amoonguss"]["revealed_ability"] == "regenerator"
        assert me["incineroar"]["status"] == "burn"

    async def test_zero_hp_faints_and_leaves_field(self, tools):
        await _started(tools)
        await tools["record_turn"](hp_changes={"opp/tornadus": 0})
        state = await tools["get_battle_state"]()
        tornadus = next(p for p in state["opp_team"] if p["name"] == "tornadus")
        assert tornadus["fainted"] is True
        assert tornadus["on_field"] is False

    async def test_tera_is_recorded(self, tools):
        await _started(tools)
        await tools["record_turn"](teras=["me/flutter-mane:fairy"])
        state = await tools["get_battle_state"]()
        fm = next(p for p in state["my_team"] if p["name"] == "flutter-mane")
        assert fm["has_terastallized"] is True
        assert fm["revealed_tera_type"] == "fairy"

    async def test_unknown_pokemon_is_error(self, tools):
        await _started(tools)
        result = await tools["record_turn"](hp_changes={"opp/pikachu": 50})
        assert result["success"] is False

    async def test_switch_replaces_lead(self, tools):
        await _started(tools)
        result = await tools["record_turn"](my_lead=["incineroar", "rillaboom"])
        assert result["success"] is True
        state = await tools["get_battle_state"]()
        on_field = [p["name"] for p in state["my_team"] if p["on_field"]]
        assert sorted(on_field) == ["incineroar", "rillaboom"]

    async def test_field_timers_set_and_decay(self, tools):
        await _started(tools)
        # record_turn sets tailwind to 4, then advance_turn decays it to 3
        await tools["record_turn"](tailwind="me", weather="rain")
        state = await tools["get_battle_state"]()
        assert state["field"]["my_tailwind_turns"] == 3
        assert state["field"]["weather"] == "rain"
        assert state["field"]["weather_turns_left"] == 4


class TestSuggestNextMove:
    async def test_snapshot_structure(self, tools):
        await _started(tools)
        result = await tools["suggest_next_move"]()
        assert result["success"] is True
        for key in ("position", "score", "my_field", "opp_field", "bench",
                    "fainted", "field", "tera_available", "recommendation_seed"):
            assert key in result
        assert result["position"] == "even"
        assert result["tera_available"] == {"me": True, "opp": True}

    async def test_position_reflects_faints(self, tools):
        await _started(tools)
        await tools["record_turn"](hp_changes={"opp/tornadus": 0})
        result = await tools["suggest_next_move"]()
        assert result["position"] == "ahead"
        assert "tornadus" in result["fainted"]["opp"]

    async def test_low_hp_threat_generates_finish_hint(self, tools):
        await _started(tools)
        await tools["record_turn"](hp_changes={"opp/tornadus": 25})
        result = await tools["suggest_next_move"]()
        hints = " ".join(result["recommendation_seed"]["priority_actions"])
        assert "tornadus" in hints

    async def test_used_tera_flips_availability(self, tools):
        await _started(tools)
        await tools["record_turn"](teras=["me/flutter-mane:fairy"])
        result = await tools["suggest_next_move"]()
        assert result["tera_available"]["me"] is False
        assert result["tera_available"]["opp"] is True


class TestEndBattle:
    async def test_end_archives_and_clears(self, tools):
        await _started(tools)
        result = await tools["end_battle"](outcome="win", notes="clean 4-0")
        assert result["success"] is True
        assert result["outcome"] == "win"
        assert result["final_state"]["my_team"]
        # Battle is gone afterwards
        after = await tools["get_battle_state"]()
        assert after["success"] is False
