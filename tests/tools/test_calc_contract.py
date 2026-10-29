"""Core calc tools return the shared response contract and publish an outputSchema."""

import asyncio

import pytest

from vgc_mcp_core.tools.response_contract import HEADLINE_MAX, CalcResult

from .test_merged_tools import mainline_session, pokeapi, smogon, tools  # noqa: F401

CONTRACT_TOOLS = (
    "calculate_damage_output",
    "find_survival_evs",
    "calculate_bulk_offensive_calcs",
    "compare_speed",
    "find_speed_evs_to_outspeed",
    "analyze_outspeed_probability",
    "get_pokemon_stats",
)

CALLS = {
    "calculate_damage_output": dict(
        attacker_name="flutter-mane", defender_name="garchomp", move_name="moonblast",
        attacker_nature="timid", attacker_spa_evs=252, defender_nature="careful", defender_hp_evs=252),
    "find_survival_evs": dict(
        attacker_name="flutter-mane", defender_name="garchomp", move_name="moonblast",
        attacker_nature="modest", attacker_evs="0/0/0/252/4/252", use_smogon_spreads=False),
    "calculate_bulk_offensive_calcs": dict(
        attacker_name="landorus", move_names=["earthquake"], defender_names=["garchomp"],
        attacker_nature="adamant", attacker_evs="4/252/0/0/0/252"),
    "compare_speed": dict(pokemon1_name="garchomp", pokemon2_name="landorus", pokemon1_speed_evs=252),
    "find_speed_evs_to_outspeed": dict(pokemon_name="garchomp", target_speed=150, nature="jolly"),
    "analyze_outspeed_probability": dict(pokemon_name="garchomp", target_pokemon="landorus", speed_evs=252),
    "get_pokemon_stats": dict(pokemon_name="garchomp", nature="jolly", atk_evs=252, spe_evs=252),
}


@pytest.fixture
def all_tools(tools, pokeapi):  # noqa: F811
    from mcp.server.fastmcp import FastMCP

    from vgc_mcp.tools.stats_tools import register_stats_tools

    mcp = FastMCP("stats")
    register_stats_tools(mcp, pokeapi)
    return {**tools, **{n: t.fn for n, t in mcp._tool_manager._tools.items()}}


@pytest.mark.parametrize("name", CONTRACT_TOOLS)
async def test_contract_fields(all_tools, name):
    result = await all_tools[name](**CALLS[name])
    assert "error" not in result, result
    for key in ("headline", "spreads_used", "data_source", "showdown_paste"):
        assert key in result, key
    assert result["headline"] and len(result["headline"]) <= HEADLINE_MAX
    assert result["spreads_used"] and all(isinstance(v, str) for v in result["spreads_used"].values())
    CalcResult.model_validate(result)


async def test_damage_headline_and_paste(all_tools):
    result = await all_tools["calculate_damage_output"](**CALLS["calculate_damage_output"])
    assert result["headline"].startswith(("Yes, Moonblast OHKOs Garchomp", "No, Moonblast does not OHKO Garchomp"))
    assert result["showdown_paste"] == result["attacker_showdown_paste"]
    assert result["spreads_used"]["attacker"].startswith("Timid 0/0/0/252/0/0 Flutter Mane")


def test_contract_tools_publish_output_schema():
    from vgc_mcp import server

    listed = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    for name in CONTRACT_TOOLS:
        schema = listed[name].outputSchema
        assert schema and "headline" in schema["properties"], name
