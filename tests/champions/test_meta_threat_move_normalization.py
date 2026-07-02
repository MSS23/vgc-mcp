"""Regression tests for the move-fetch crash in meta_threat_tools.py.

Reproduces the pre-existing bug (failed in BOTH formats) where Smogon usage
move keys arrive concatenated (e.g. "fakeout", "partingshot") and were passed
straight to pokeapi.get_move:

  1. Concatenated keys like "fakeout" don't resolve as "fakeout" — they must be
     normalized to "fake-out" first.
  2. Keys PokeAPI still can't resolve (e.g. status moves / unmapped names) made
     get_move raise PokeAPIError -> the whole tool died with a ToolError.
  3. get_move returns a Move OBJECT, but the "your moves" loop treated it as a
     dict (move_data.get(...)) -> "'Move' object has no attribute 'get'".

The fix normalizes keys, tolerates unresolvable ones, and reads Move attributes.
These tests drive the ACTUAL registered tools with fake clients so they assert
the real dispatch behavior, in both a Champions and a mainline session.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.meta_threat_tools import register_meta_threat_tools
from vgc_mcp_core.api.pokeapi import PokeAPIError
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import get_regulation_config

_BASE = {
    "incineroar": BaseStats(hp=95, attack=115, defense=90,
                            special_attack=80, special_defense=90, speed=60),
    "flutter-mane": BaseStats(hp=55, attack=55, defense=55,
                              special_attack=135, special_defense=135, speed=135),
}
_TYPES = {
    "incineroar": ["fire", "dark"],
    "flutter-mane": ["ghost", "fairy"],
}

# A small move catalog keyed by the NORMALIZED (hyphenated) name PokeAPI uses.
_MOVE_CATALOG = {
    "fake-out": Move(name="fake-out", type="normal", category=MoveCategory.PHYSICAL,
                     power=40, accuracy=100, target="selected-pokemon"),
    "flare-blitz": Move(name="flare-blitz", type="fire", category=MoveCategory.PHYSICAL,
                        power=120, accuracy=100, target="selected-pokemon"),
    "moonblast": Move(name="moonblast", type="fairy", category=MoveCategory.SPECIAL,
                      power=95, accuracy=100, target="selected-pokemon"),
}


def _catalog_get_move(name, *a, **k):
    """Emulate pokeapi.get_move: resolve hyphenated names, raise on unknown.

    This is the crux of the regression: the raw Smogon key "fakeout" only
    resolves once normalize_move turns it into "fake-out", and "partingshot"
    (a status move not in the catalog) must NOT bring the tool down.
    """
    if name in _MOVE_CATALOG:
        return _MOVE_CATALOG[name]
    raise PokeAPIError(f"Not found: move/{name}")


def _fake_pokeapi():
    api = MagicMock()
    api.get_base_stats = AsyncMock(side_effect=lambda n, *a, **k: _BASE[n])
    api.get_pokemon_types = AsyncMock(side_effect=lambda n, *a, **k: _TYPES[n])
    api.get_pokemon_abilities = AsyncMock(return_value=["Intimidate"])
    api.get_move = AsyncMock(side_effect=_catalog_get_move)
    return api


def _fake_smogon():
    """Usage data with Smogon CONCATENATED move keys, incl. an unresolvable one."""
    incin_usage = {
        # "fakeout" -> "fake-out" (needs normalize), "partingshot" -> 404 (skip),
        # "flareblitz" -> "flare-blitz" (needs normalize).
        "moves": {"fakeout": 0.9, "partingshot": 0.8, "flareblitz": 0.5},
        "spreads": [],
    }
    flutter_usage = {
        "moves": {"moonblast": 0.95, "shadowball": 0.4},  # shadowball -> 404, skip
        "spreads": [],
    }

    def usage(name, *a, **k):
        return {"incineroar": incin_usage, "flutter-mane": flutter_usage}.get(name)

    s = MagicMock()
    s.get_pokemon_usage = AsyncMock(side_effect=usage)
    s.get_usage_stats = AsyncMock(return_value={
        "_meta": {},
        "data": {"flutter-mane": {"usage": 0.5}},
    })
    return s


def _register(pokeapi, smogon, team_manager=None):
    mcp = FastMCP("test")
    captured = {}
    orig = mcp.tool

    def patched(*a, **k):
        decorator = orig(*a, **k)

        def wrap(fn):
            captured[fn.__name__] = fn
            return decorator(fn)

        return wrap

    mcp.tool = patched
    register_meta_threat_tools(mcp, smogon, pokeapi, team_manager or MagicMock())
    return captured


@pytest.fixture
def champions_session():
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_ma_champs")
    try:
        yield cfg
    finally:
        cfg.clear_session_override()


@pytest.fixture
def mainline_session():
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_f")
    try:
        yield cfg
    finally:
        cfg.clear_session_override()


class TestAnalyzeSpreadVsThreatsMoveFetch:
    def test_does_not_crash_on_smogon_move_keys_mainline(self, mainline_session):
        # Before the fix this raised ToolError "Not found: move/fakeout" (or the
        # "'Move' object has no attribute 'get'" on the your-moves path).
        tools = _register(_fake_pokeapi(), _fake_smogon())
        res = asyncio.run(tools["analyze_spread_vs_threats"](
            pokemon_name="incineroar", nature="adamant",
            hp_evs=252, atk_evs=4, def_evs=252, top_threats=3,
        ))
        assert "error" not in res
        assert res["threats_analyzed"] >= 1
        assert "EVs:" in res["showdown_paste"]

    def test_does_not_crash_on_smogon_move_keys_champions(self, champions_session):
        tools = _register(_fake_pokeapi(), _fake_smogon())
        res = asyncio.run(tools["analyze_spread_vs_threats"](
            pokemon_name="incineroar", nature="adamant",
            hp_evs=252, atk_evs=4, def_evs=252, top_threats=3,
        ))
        assert "error" not in res
        assert res["threats_analyzed"] >= 1
        # Champions subject stays SP-scale.
        assert res["spread"]["format_system"] == "champions"
        assert all(0 <= v <= 32 for v in res["spread"]["sps"].values())
        assert "SPs:" in res["showdown_paste"]
        assert "EVs:" not in res["showdown_paste"]

    def test_resolvable_moves_used_unresolvable_skipped(self, mainline_session):
        # Assert the normalize path actually resolved the concatenated keys and
        # that the threat's resolvable move surfaced in the matchup.
        tools = _register(_fake_pokeapi(), _fake_smogon())
        res = asyncio.run(tools["analyze_spread_vs_threats"](
            pokemon_name="incineroar", nature="adamant",
            hp_evs=252, atk_evs=4, def_evs=252, top_threats=3,
        ))
        rows = res["matchups"]
        assert rows, "expected at least one threat matchup"
        # Flutter Mane's only resolvable move is moonblast; shadowball was skipped.
        their_move = rows[0]["their_damage_detail"]["move"]
        assert their_move == "moonblast"


class TestAnalyzeStoredPokemonThreatsMoveFetch:
    def test_stored_subject_does_not_crash(self, mainline_session):
        # The stored-Pokemon variant has the same your-moves Move-vs-dict bug.
        from vgc_mcp_core.models.pokemon import EVSpread, Nature, PokemonBuild

        tm = MagicMock()
        stored = PokemonBuild(
            name="incineroar",
            base_stats=_BASE["incineroar"],
            types=_TYPES["incineroar"],
            nature=Nature.ADAMANT,
            evs=EVSpread(hp=252, attack=4, defense=252),
            level=50,
        )
        tm.get_pokemon_context = MagicMock(return_value=stored)
        tm.list_pokemon_context = MagicMock(return_value=[])

        tools = _register(_fake_pokeapi(), _fake_smogon(), team_manager=tm)
        res = asyncio.run(tools["analyze_stored_pokemon_threats"](top_threats=3))
        assert "error" not in res
        assert res["threats_analyzed"] >= 1
