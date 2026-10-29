"""Calc tools in the spread/workflow/preparation modules follow the response contract."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from tests.tools.test_preparation_workflows import OPPONENT, PASTE, call, workflow  # noqa: F401
from tests.tools.test_slash_allocation import mainline, tools  # noqa: F401
from vgc_mcp.tools.workflow_tools import register_workflow_tools
from vgc_mcp_core.tools.response_contract import HEADLINE_MAX

CONTRACT_TOOLS = [
    "design_spread_with_benchmarks", "optimize_multi_survival_spread", "optimize_dual_survival_spread",
    "calc_damage_vs_smogon_sets", "verify_spread_benchmarks", "recommend_verified_spreads",
    "calculate_move_outcomes",
]
KEYS = ("headline", "spreads_used", "data_source", "showdown_paste")


def assert_contract(result, *, sourced=False):
    assert "error" not in result, result
    for key in KEYS:
        assert key in result, key
    assert 0 < len(result["headline"]) <= HEADLINE_MAX
    assert result["spreads_used"]
    assert (result["data_source"] is not None) == sourced


def test_contract_tools_publish_output_schema():
    import vgc_mcp.server as server

    listed = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    for name in CONTRACT_TOOLS:
        schema = listed[name].outputSchema
        assert schema is not None, name
        assert set(KEYS) <= set(schema["properties"]), name


async def test_design_spread_contract(tools):  # noqa: F811
    result = await tools["design_spread_with_benchmarks"](
        pokemon_name="amoonguss", nature="bold", survive_pokemon="incineroar", survive_move="flare-blitz",
        survive_pokemon_ability="blaze", survive_pokemon_item="life-orb", outspeed_pokemon="amoonguss",
        outspeed_pokemon_evs=0, item="rocky-helmet", ability="regenerator",
    )
    assert_contract(result)
    assert "survive" in result["headline"] and "Flare Blitz" in result["headline"]
    assert result["spreads_used"]["attacker"].startswith("Adamant 0/252/0/0/0/0 Incineroar @ Life Orb")
    assert "@ Rocky Helmet" in result["spreads_used"]["pokemon"]


async def test_dual_and_multi_survival_contract(tools):  # noqa: F811
    dual = await tools["optimize_dual_survival_spread"](
        pokemon_name="amoonguss", survive_hit1_attacker="incineroar", survive_hit1_move="flare-blitz",
        survive_hit1_nature="adamant", survive_hit1_evs=252, survive_hit2_attacker="incineroar",
        survive_hit2_move="heat-wave", survive_hit2_nature="modest", survive_hit2_evs="4/0/0/252/0/252",
        nature="calm",
    )
    assert_contract(dual)
    assert set(dual["spreads_used"]) == {"pokemon", "attacker_1", "attacker_2"}

    threats = [{"attacker": "incineroar", "move": m, "nature": "adamant", "evs": 252, "item": "life-orb",
                "ability": "blaze"} for m in ("flare-blitz", "knock-off", "heat-wave")]
    multi = await tools["optimize_multi_survival_spread"](pokemon_name="amoonguss", threats=threats, nature="calm")
    assert_contract(multi)
    assert "survives 3/3 threats" in multi["headline"]


async def test_calc_damage_vs_smogon_sets_contract(mainline):  # noqa: F811
    from tests.tools.test_slash_allocation import BASES, MOVES

    api = AsyncMock()
    api.get_base_stats = AsyncMock(side_effect=lambda n: BASES[n.lower()])
    api.get_pokemon_types = AsyncMock(return_value=["Fire", "Dark"])
    api.get_move = AsyncMock(side_effect=lambda name, user_name=None: MOVES[name])
    smogon = AsyncMock()
    smogon.get_pokemon_usage.return_value = {
        "spreads": [{"nature": "Adamant", "evs": {"hp": 252, "attack": 252, "speed": 4}, "usage": 30}],
        "items": {"Life Orb": 50}, "abilities": {"Blaze": 90},
        "_meta": {"format": "gen9vgc2025regh", "month": "2026-09", "rating": 1630},
    }
    mcp = FastMCP("test")
    register_workflow_tools(mcp, api, smogon, AsyncMock(), AsyncMock())
    fn = {t.name: t.fn for t in mcp._tool_manager._tools.values()}["calc_damage_vs_smogon_sets"]
    result = await fn(my_pokemon="amoonguss", my_nature="bold", my_spread="252/0/252/0/4/0",
                      opponent_pokemon="incineroar", move="flare-blitz")
    assert_contract(result, sourced=True)
    assert result["data_source"]["month"] == "2026-09"
    assert result["spreads_used"]["pokemon"].startswith("Bold 252/0/252/0/4/0 Amoonguss")
    assert "opponent_set_1" in result["spreads_used"]


async def test_preparation_tools_contract_through_mcp(workflow):  # noqa: F811
    mcp, _, _ = workflow
    exact = [{"kind": "survive", "opponent_paste": OPPONENT, "move": "wood-hammer", "probability": 100}]
    verified = await call(mcp, "verify_spread_benchmarks", pokemon_paste=PASTE, benchmarks=exact, regulation="reg_i")
    assert_contract(verified)
    assert "benchmarks" in verified["headline"]

    chaos = [{"kind": "survive", "opponent_name": "rillaboom", "move": "wood-hammer"}]
    sourced = await call(mcp, "verify_spread_benchmarks", pokemon_paste=PASTE, benchmarks=chaos, regulation="reg_i")
    assert_contract(sourced, sourced=True)
    assert sourced["data_source"]["month"] == "2026-06"

    recommended = await call(mcp, "recommend_verified_spreads", pokemon_paste=PASTE, benchmarks=exact,
                             regulation="reg_i", natures=["careful"])
    assert_contract(recommended)
    assert recommended["showdown_paste"] == recommended["candidates"][0]["showdown_paste"]

    outcomes = await call(mcp, "calculate_move_outcomes", attacker_paste=PASTE, defender_paste=OPPONENT,
                          move_name="flare-blitz", regulation="reg_i")
    for key in KEYS:
        assert key in outcomes
    assert set(outcomes["spreads_used"]) == {"attacker", "defender"}
    assert outcomes["data_source"] is None


@pytest.mark.parametrize("tool", ["verify_spread_benchmarks", "recommend_verified_spreads"])
async def test_contract_tool_errors_still_validate(workflow, tool):  # noqa: F811
    mcp, _, _ = workflow
    result = await call(mcp, tool, pokemon_paste=PASTE, regulation="reg_unknown", benchmarks=[
        {"kind": "survive", "opponent_paste": OPPONENT, "move": "wood-hammer"}])
    assert result["success"] is False
    assert result["error"] == "invalid_parameter"
