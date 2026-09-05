"""Prevent real chaos identifiers from losing their mechanics at API boundaries."""

from unittest.mock import AsyncMock

import pytest

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.utils.normalize import normalize_ability, normalize_item, normalize_move


@pytest.mark.parametrize("raw,expected", [
    ("partingshot", "parting-shot"), ("populationbomb", "population-bomb"),
    ("poweruppunch", "power-up-punch"), ("tripleaxel", "triple-axel"),
])
def test_real_chaos_move_identifiers(raw, expected):
    assert normalize_move(raw) == expected


def test_on_hit_ability_and_berry_identifiers():
    assert normalize_ability("parentalbond") == "parental-bond"
    assert normalize_ability("weakarmor") == "weak-armor"
    assert normalize_ability("grassysurge") == "grassy-surge"
    assert normalize_item("chilanberry") == "chilan-berry"
    assert normalize_item("figyberry") == "figy-berry"


async def test_pokeapi_boundary_accepts_chaos_move_id():
    client = PokeAPIClient()
    client._fetch = AsyncMock(return_value={"name": "parting-shot", "type": {"name": "dark"},
        "damage_class": {"name": "status"}, "power": None, "accuracy": 100, "pp": 20,
        "priority": 0, "target": {"name": "selected-pokemon"}})
    move = await client.get_move("partingshot")
    assert move.name == "parting-shot"
    client._fetch.assert_awaited_once_with("move/parting-shot")
    await client.close()
