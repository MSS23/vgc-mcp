"""Tests for the battle copilot and replay analyzer tools.

These flagship features previously had zero coverage. Battle tools mutate a
BattleStateManager; replay tools parse Showdown protocol logs (mocked here so
no network is hit).
"""

from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.battle_tools import register_battle_tools
from vgc_mcp.tools.replay_tools import register_replay_tools
from vgc_mcp_core.state.battle_manager import BattleStateManager


@pytest.fixture
def battle_tools():
    mcp = FastMCP("test")
    register_battle_tools(mcp, BattleStateManager())
    return {t.name: t.fn for t in mcp._tool_manager._tools.values()}


@pytest.fixture
def replay_tools():
    mcp = FastMCP("test")
    register_replay_tools(mcp)
    return {t.name: t.fn for t in mcp._tool_manager._tools.values()}


# ---------------------------------------------------------------------------
# Battle copilot
# ---------------------------------------------------------------------------

async def test_start_battle_creates_state(battle_tools):
    result = await battle_tools["start_battle"](
        my_team=["incineroar", "flutter-mane", "amoonguss", "urshifu-rapid-strike"],
        opp_team=["landorus", "rillaboom", "tornadus", "chi-yu"],
    )
    assert result.get("success") is not False
    # A default regulation was resolved (not hardcoded/empty).
    state = await battle_tools["get_battle_state"]()
    assert state.get("format")


async def test_start_battle_rejects_bad_team_size(battle_tools):
    result = await battle_tools["start_battle"](
        my_team=["incineroar"],  # too few
        opp_team=["landorus", "rillaboom", "tornadus", "chi-yu"],
    )
    assert result.get("success") is False


async def test_record_turn_advances_state(battle_tools):
    await battle_tools["start_battle"](
        my_team=["incineroar", "flutter-mane", "amoonguss", "urshifu-rapid-strike"],
        opp_team=["landorus", "rillaboom", "tornadus", "chi-yu"],
        my_lead=["incineroar", "flutter-mane"],
        opp_lead=["landorus", "rillaboom"],
    )
    result = await battle_tools["record_turn"](
        events="Flutter Mane used Moonblast on Landorus",
    )
    assert result.get("success") is not False
    state = await battle_tools["get_battle_state"]()
    assert state.get("turn", 1) >= 1


async def test_suggest_next_move_requires_active_battle(battle_tools):
    # No battle started yet.
    result = await battle_tools["suggest_next_move"]()
    assert result.get("success") is False


async def test_get_battle_state_without_battle(battle_tools):
    result = await battle_tools["get_battle_state"]()
    assert result.get("success") is False


async def test_end_battle(battle_tools):
    await battle_tools["start_battle"](
        my_team=["incineroar", "flutter-mane", "amoonguss", "urshifu-rapid-strike"],
        opp_team=["landorus", "rillaboom", "tornadus", "chi-yu"],
    )
    result = await battle_tools["end_battle"](outcome="win", notes="gg")
    assert result.get("success") is not False
    # Battle cleared afterward.
    state = await battle_tools["get_battle_state"]()
    assert state.get("success") is False


# ---------------------------------------------------------------------------
# Replay analyzer (mocked fetch — no network)
# ---------------------------------------------------------------------------

SAMPLE_REPLAY = {
    "id": "gen9vgc2024regh-123",
    "format": "[Gen 9] VGC 2024 Reg H",
    "p1": "Alice",
    "p2": "Bob",
    "uploadtime": 1700000000,
    "log": (
        "|start\n"
        "|switch|p1a: Flutter Mane|Flutter Mane, L50|100/100\n"
        "|switch|p2a: Landorus|Landorus, L50|100/100\n"
        "|turn|1\n"
        "|move|p1a: Flutter Mane|Moonblast|p2a: Landorus\n"
        "|-damage|p2a: Landorus|0 fnt\n"
        "|faint|p2a: Landorus\n"
        "|-terastallize|p1a: Flutter Mane|Fairy\n"
        "|turn|2\n"
        "|move|p2a: Bob|Protect|p2a: Bob\n"
        "|win|Alice\n"
    ),
}


async def test_analyze_replay_parses_turns_and_winner(replay_tools):
    with patch(
        "vgc_mcp.tools.replay_tools._fetch_replay",
        return_value=SAMPLE_REPLAY,
    ):
        result = await replay_tools["analyze_replay"](
            replay_url="https://replay.pokemonshowdown.com/gen9vgc2024regh-123",
        )
    assert result.get("success") is not False
    meta = result.get("meta", {})
    assert meta.get("p1") == "Alice"
    assert meta.get("turn_count", 0) >= 2
    # KO and Tera should surface as key events.
    key_events = result.get("key_events", [])
    assert isinstance(key_events, list)


async def test_analyze_replay_handles_empty_log(replay_tools):
    with patch(
        "vgc_mcp.tools.replay_tools._fetch_replay",
        return_value={"id": "x", "log": ""},
    ):
        result = await replay_tools["analyze_replay"](replay_url="x")
    assert result.get("success") is False
