"""Contract test: tools run against the REAL PokeAPIClient, not a hand-shaped mock.

Tool tests used to mock ``get_pokemon`` with a ``base_stats``/flat ``types``
dict the real client never returned, and to mock ``get_pokemon_stats`` /
``get_nature`` methods the client did not have. Production then raised
KeyError/AttributeError for ~20 tools. Only ``_fetch`` (the network edge) is
patched here, with raw PokeAPI payloads.
"""

from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from tests.api.test_api_clients import FLUTTER_MANE_RESPONSE, MOONBLAST_RESPONSE
from vgc_mcp.tools.chip_damage_tools import register_chip_damage_tools
from vgc_mcp.tools.item_tools import register_item_tools
from vgc_mcp.tools.workflow_tools import register_workflow_tools
from vgc_mcp_core.api.cache import APICache
from vgc_mcp_core.api.pokeapi import PokeAPIClient, PokeAPIError

INCINEROAR_RESPONSE = {
    "name": "incineroar",
    "types": [{"slot": 1, "type": {"name": "fire"}}, {"slot": 2, "type": {"name": "dark"}}],
    "stats": [
        {"base_stat": v, "stat": {"name": n}}
        for n, v in [("hp", 95), ("attack", 115), ("defense", 90),
                     ("special-attack", 80), ("special-defense", 90), ("speed", 60)]
    ],
    "abilities": [{"ability": {"name": "intimidate"}, "is_hidden": True}],
}

RAW = {
    "pokemon/flutter-mane": FLUTTER_MANE_RESPONSE,
    "pokemon/incineroar": INCINEROAR_RESPONSE,
    "move/moonblast": MOONBLAST_RESPONSE,
}


@pytest.fixture
def tools():
    cache = MagicMock(spec=APICache)
    cache.get.return_value = None
    client = PokeAPIClient(cache)

    async def fake_fetch(endpoint):
        if endpoint not in RAW:
            raise PokeAPIError(f"Not found: {endpoint}")
        return RAW[endpoint]

    client._fetch = fake_fetch
    mcp = FastMCP("contract")
    register_workflow_tools(mcp, client, MagicMock(), MagicMock(), MagicMock())
    register_chip_damage_tools(mcp, client)
    register_item_tools(mcp, client)
    return {t.name: t.fn for t in mcp._tool_manager._tools.values()}


def _ok(result: dict) -> None:
    assert result.get("success", True) is not False, result
    assert "error" not in result, result


async def test_quick_damage_check(tools):
    result = await tools["quick_damage_check"](
        attacker="flutter-mane", defender="incineroar", move="moonblast")
    _ok(result)


async def test_analyze_speed_matchup(tools):
    _ok(await tools["analyze_speed_matchup"](
        my_pokemon="flutter-mane", opponent_pokemon="incineroar"))


async def test_weather_damage_uses_types(tools):
    result = await tools["calculate_weather_damage"](pokemon_name="incineroar", weather="sand")
    _ok(result)


async def test_assault_vest_uses_nature(tools):
    neutral = await tools["calculate_assault_vest"](pokemon_name="incineroar")
    calm = await tools["calculate_assault_vest"](pokemon_name="incineroar", nature="calm")
    _ok(neutral)
    _ok(calm)
    assert calm != neutral  # +SpD nature must change the result


async def test_get_nature_shape():
    client = PokeAPIClient(MagicMock(spec=APICache))
    assert await client.get_nature("Modest") == {
        "increased_stat": {"name": "special-attack"},
        "decreased_stat": {"name": "attack"},
    }
    assert await client.get_nature("hardy") == {}
    with pytest.raises(ValueError):
        await client.get_nature("not-a-nature")
