"""Real MCP tool validation/serialization with deterministic external clients."""

import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.preparation_tools import register_preparation_tools
from vgc_mcp.tools.router_tools import register_router_tools
from vgc_mcp.tools.usage_tools import register_usage_tools
from vgc_mcp_core.models.move import Move
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.team.manager import TeamManager

PASTE = """Incineroar @ Sitrus Berry
Ability: Intimidate
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
- Flare Blitz
- Knock Off
- Fake Out
- Protect"""
OPPONENT = """Rillaboom @ Assault Vest
Ability: Grassy Surge
EVs: 252 HP / 252 Atk / 4 SpD
Adamant Nature
- Wood Hammer
- Fake Out
- U-turn
- Grassy Glide"""


@pytest.fixture
def workflow():
    pokeapi = AsyncMock()
    async def stats(name):
        if "rillaboom" in name.lower():
            return BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85)
        return BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60)
    async def types(name):
        return ["Grass"] if "rillaboom" in name.lower() else ["Fire", "Dark"]
    async def move(name, user_name=None):
        data = {"flare-blitz": ("Fire", 120), "wood-hammer": ("Grass", 120),
                "knock-off": ("Dark", 65), "fake-out": ("Normal", 40),
                "u-turn": ("Bug", 70), "grassy-glide": ("Grass", 55)}
        key = name.lower().replace(" ", "-")
        if key == "protect":
            return Move(name=key, type="Normal", category="status")
        type_name, power = data[key]
        return Move(name=key, type=type_name, category="physical", power=power, accuracy=100)
    pokeapi.get_base_stats.side_effect = stats
    pokeapi.get_pokemon_types.side_effect = types
    pokeapi.get_move.side_effect = move
    fmt = get_regulation_config().get_smogon_formats("reg_i")[0]
    meta = {"format": fmt, "month": "2026-06", "rating": 1630,
            "source_url": f"https://www.smogon.com/stats/2026-06/chaos/{fmt}-1630.json"}
    usage = {"name": "Rillaboom", "usage_percent": 20, "items": {"Assault Vest": 60},
             "abilities": {"Grassy Surge": 99}, "moves": {"Wood Hammer": 80, "Fake Out": 90, "U-turn": 30, "Grassy Glide": 70},
             "tera_types": {"Fire": 40}, "spreads": [{"nature": "Adamant", "evs": {"hp": 252, "attack": 252, "special_defense": 4}}],
             "_meta": meta}
    smogon = AsyncMock()
    smogon.get_usage_stats.return_value = {"data": {"Rillaboom": {"usage": .2}}, "_meta": meta}
    smogon.get_pokemon_usage.return_value = usage
    smogon.get_common_sets.return_value = {"pokemon": "Rillaboom", "_meta": meta}
    manager = TeamManager()
    mcp = FastMCP("Workflow tests")
    register_preparation_tools(mcp, pokeapi, smogon, manager)
    register_usage_tools(mcp, smogon, manager)
    register_router_tools(mcp)
    return mcp, manager, smogon


async def call(mcp, name, **arguments):
    content = await mcp.call_tool(name, arguments)
    # FastMCP includes structured output for typed dict tool responses.
    if isinstance(content, tuple):
        return content[1]
    return json.loads(content[0].text)


async def test_natural_team_review_routes_and_delivers_report(workflow):
    mcp, manager, smogon = workflow
    routing = await call(mcp, "what_tool_should_i_use", question="Please review my team for a tournament")
    assert "prepare_team" in str(routing)
    report = await call(mcp, "prepare_team", team_paste=PASTE, regulation="reg_i", meta_limit=1)
    assert "error" not in report, report
    assert report["source"]["rating"] == 1630
    assert report["matchups"][0]["source"]["kind"] == "usage_components"
    assert report["matchups"][0]["outgoing"]["move"] == "flare-blitz"
    assert "Rillaboom" in report["report_markdown"]
    assert "EVs:" in report["showdown_paste"]
    assert manager.get_current_team() is None
    kwargs = smogon.get_pokemon_usage.call_args.args
    assert kwargs[2:] == (1630, "2026-06")


async def test_imported_complete_sets_are_separate_and_session_scoped(workflow):
    mcp, manager, _ = workflow
    args = dict(paste=OPPONENT, source_name="User supplied event team", regulation="reg_i")
    result = await call(mcp, "import_reference_team", **args)
    assert result["session_reference_count"] == 1
    assert not result["source_verified"]
    await call(mcp, "import_reference_team", **args)
    assert len(manager.sourced_sets) == 1
    common = await call(mcp, "get_common_sets", pokemon_name="Rillaboom")
    assert len(common["complete_sets"]) == 1
    assert common["complete_sets"][0]["source_kind"] == "user_imported_complete"
    assert TeamManager().sourced_sets == []


async def test_exact_benchmarks_and_alternatives_round_trip(workflow):
    mcp, _, _ = workflow
    benchmarks = [{"kind": "survive", "opponent_paste": OPPONENT, "move": "wood-hammer", "probability": 100}]
    result = await call(mcp, "recommend_verified_spreads", pokemon_paste=PASTE,
                        benchmarks=benchmarks, regulation="reg_i", natures=["careful"])
    assert "error" not in result, result
    assert {c["purpose"] for c in result["candidates"]} == {"minimum_investment", "more_offense", "more_bulk"}
    for candidate in result["candidates"]:
        assert candidate["investment"] <= 508
        checked = await call(mcp, "verify_spread_benchmarks", pokemon_paste=candidate["showdown_paste"],
                             benchmarks=benchmarks, regulation="reg_i")
        assert checked["verified"]
        assert "opponent_showdown_paste" in checked["benchmarks"][0]


async def test_move_outcomes_through_mcp(workflow):
    mcp, _, _ = workflow
    result = await call(mcp, "calculate_move_outcomes", attacker_paste=PASTE,
                        defender_paste=OPPONENT, move_name="flare-blitz", regulation="reg_i")
    assert "error" not in result, result
    assert result["details"]["accuracy_included"]
    assert sum(o["probability"] for o in result["details"]["outcome_distribution"]) == pytest.approx(1)


@pytest.mark.parametrize("export_format,magic", [("pdf", b"%PDF"), ("excel", b"PK"), ("markdown", b"#"), ("json", b"{")])
async def test_report_exports_are_available_to_remote_clients(workflow, export_format, magic):
    mcp, _, _ = workflow
    report = await call(mcp, "prepare_team", team_paste=PASTE, regulation="reg_i", meta_limit=1, export_format=export_format)
    assert "error" not in report, report
    exported = report["export"]
    data = base64.b64decode(exported["data_base64"])
    assert data.startswith(magic)
    assert Path(exported["file_path"]).read_bytes() == data


async def test_format_mismatch_and_invalid_slot_are_structured_errors(workflow):
    mcp, _, _ = workflow
    result = await call(mcp, "prepare_team", team_paste=PASTE, regulation="reg_mb_champs", meta_limit=1)
    assert result["success"] is False
    assert result["error"] == "invalid_parameter"
    result = await call(mcp, "prepare_team", team_paste=PASTE, regulation="reg_i", benchmarks_by_slot={2: []})
    assert result["error"] == "invalid_parameter"


async def test_champions_sp_paste_preserved(workflow):
    mcp, _, _ = workflow
    paste = PASTE.replace("EVs: 252 HP / 4 Atk / 252 SpD", "SPs: 32 HP / 2 Atk / 32 SpD")
    opponent = OPPONENT.replace("EVs: 252 HP / 252 Atk / 4 SpD", "SPs: 32 HP / 32 Atk / 2 SpD")
    result = await call(mcp, "verify_spread_benchmarks", pokemon_paste=paste,
                        benchmarks=[{"kind": "survive", "opponent_paste": opponent, "move": "wood-hammer"}],
                        regulation="reg_mb_champs")
    assert "error" not in result, result
    assert "SPs:" in result["showdown_paste"]


async def test_preparation_includes_requested_verified_adjustments(workflow):
    mcp, _, _ = workflow
    report = await call(mcp, "prepare_team", team_paste=PASTE, regulation="reg_i", meta_limit=1,
                        benchmarks_by_slot={1: [{"kind": "survive", "opponent_paste": OPPONENT,
                                                  "move": "wood-hammer", "probability": 100}]})
    assert report["verified_adjustments"][0]["verified"]
    assert "minimum_investment" in report["report_markdown"]


@pytest.mark.parametrize("conditions", [{"attack_stage": 7}, {"surprise_bonus": 2}, {"weather": "storm"}, {"move_hits": -1}])
async def test_conditions_rejected_instead_of_silently_ignored(workflow, conditions):
    mcp, _, _ = workflow
    result = await call(mcp, "calculate_move_outcomes", attacker_paste=PASTE, defender_paste=OPPONENT,
                        move_name="flare-blitz", regulation="reg_i", conditions=conditions)
    assert result["error"] == "invalid_parameter"
