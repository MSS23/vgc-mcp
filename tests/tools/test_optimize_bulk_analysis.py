"""optimize_bulk returns its analysis block only when asked."""

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.spread_tools import register_spread_tools
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import get_regulation_config

BASES = {
    "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
    "amoonguss": BaseStats(hp=114, attack=85, defense=70, special_attack=85, special_defense=80, speed=30),
}


@pytest.fixture
def mainline():
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_h")
    try:
        yield
    finally:
        cfg.clear_session_override()


@pytest.fixture
def pokeapi():
    client = AsyncMock(spec=PokeAPIClient)
    client.get_base_stats = AsyncMock(side_effect=lambda n: BASES[n.lower()])
    client.get_pokemon_types = AsyncMock(return_value=["Fire", "Dark"])
    return client


@pytest.fixture
def spread_tools(pokeapi):
    mcp = FastMCP("test")
    register_spread_tools(mcp, pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


async def test_optimize_bulk_analysis_is_opt_in(spread_tools, mainline):
    plain = await spread_tools["optimize_bulk"].fn(pokemon_name="incineroar", nature="careful")
    assert "bulk_scores" not in plain
    spread = plain["optimal_spread"]
    assert spread["hp_evs"] + spread["def_evs"] + spread["spd_evs"] <= 252
