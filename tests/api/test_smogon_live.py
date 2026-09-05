"""Opt-in network check: python -m pytest tests/api/test_smogon_live.py -m integration."""

import pytest

from vgc_mcp_core.api.cache import APICache
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.rules.regulation_loader import RegulationConfig
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.tools.preparation_handlers import common_build, prepare_team_handler
from vgc_mcp_core.tools.smogon_helpers import get_common_spreads

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("regulation,allocation", [("reg_i", "evs"), ("reg_mb_champs", "sps")])
async def test_live_chaos_common_sets_reach_calculations(tmp_path, regulation, allocation):
    config = RegulationConfig()
    config.set_session_regulation(regulation)
    cache = APICache(str(tmp_path / "cache"))
    client = SmogonStatsClient(cache, config)
    try:
        sets = await client.get_common_sets("incineroar")
        assert sets and sets["top_spreads"] and sets["top_items"] and sets["top_moves"]
        assert sets["_meta"]["format"] in config.get_smogon_formats(regulation)
        assert "/chaos/" in sets["_meta"]["source_url"]
        common = await get_common_spreads(client, "incineroar")
        assert common[0][allocation] == sets["top_spreads"][0][allocation]
        assert common[0]["item"] and common[0]["ability"]
        cap, budget = (32, 66) if allocation == "sps" else (252, 508)
        assert all(0 <= value <= cap for value in common[0][allocation].values())
        assert sum(common[0][allocation].values()) <= budget
    finally:
        await client.close()
        cache.close()


@pytest.mark.parametrize("regulation", ["reg_i", "reg_mb_champs"])
async def test_live_preparation_workflow(tmp_path, regulation):
    cache = APICache(str(tmp_path / "preparation-cache"))
    pokeapi = PokeAPIClient(cache)
    smogon = SmogonStatsClient(cache)
    try:
        pokemon, source = await common_build("incineroar", pokeapi, smogon, regulation)
        result = await prepare_team_handler(pokemon_build_to_showdown(pokemon), regulation,
                                            ["incineroar"], 1, None, pokeapi, smogon, TeamManager())
        assert result["source"]["source_url"] == source["source_url"]
        assert result["matchups"][0]["incoming"]["damage"]
        assert result["matchups"][0]["outgoing"]["damage"]
        assert result["legality"]["valid"]
        assert "EVs:" in result["showdown_paste"] if regulation == "reg_i" else "SPs:" in result["showdown_paste"]
    finally:
        await pokeapi.close()
        await smogon.close()
        cache.close()
