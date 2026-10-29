"""Tests for the shared PokemonBuild factory."""

import pytest

from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature, StatPointSpread
from vgc_mcp_core.tools.build_helpers import build_pokemon, parse_ev_string, parse_sp_string

FLUTTER = BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135)


def _build(**kw):
    return build_pokemon("flutter-mane", FLUTTER, ["Ghost", "Fairy"], nature=Nature.TIMID, **kw)


@pytest.mark.parametrize("spread", [
    EVSpread(hp=4, special_attack=252, speed=252),
    {"hp": 4, "special_attack": 252, "speed": 252},
    {"hp": 4, "spa": 252, "spe": 252},
    "4/0/0/252/0/252",
])
def test_mainline_accepts_every_allocation_shape(spread):
    pkm = _build(spread=spread)
    assert pkm.format_system == "mainline"
    assert pkm.sps is None
    assert pkm.evs == EVSpread(hp=4, special_attack=252, speed=252)
    assert calculate_all_stats(pkm)["speed"] == 205


@pytest.mark.parametrize("spread", [
    StatPointSpread(hp=2, special_attack=32, speed=32),
    {"hp": 2, "special_attack": 32, "speed": 32},
    {"hp": 2, "sa": 32, "sp": 32},
    "2/0/0/32/0/32",
])
def test_champions_accepts_every_allocation_shape(spread):
    pkm = _build(spread=spread, champions=True)
    assert pkm.format_system == "champions"
    assert pkm.sps == StatPointSpread(hp=2, special_attack=32, speed=32)
    assert pkm.evs == EVSpread()
    # 32 SP Timid Flutter Mane == 252 EV Timid Flutter Mane (205 Speed).
    assert calculate_all_stats(pkm)["speed"] == 205


def test_format_is_inferred_from_spread_type_and_defaults_are_empty():
    assert _build(spread=StatPointSpread(speed=32)).format_system == "champions"
    assert _build().format_system == "mainline"
    assert _build(champions=True).sps == StatPointSpread()


def test_legacy_evs_keyword_still_works():
    assert _build(evs=EVSpread(speed=252)).evs.speed == 252


def test_mismatched_or_duplicate_allocations_raise():
    with pytest.raises(TypeError):
        _build(spread=EVSpread(speed=252), champions=True)
    with pytest.raises(TypeError):
        _build(spread=StatPointSpread(speed=32), champions=False)
    with pytest.raises(TypeError):
        _build(spread=EVSpread(), evs=EVSpread())


def test_slash_parsers_reject_wrong_length():
    with pytest.raises(ValueError):
        parse_ev_string("252/252")
    with pytest.raises(ValueError):
        parse_sp_string("32/32")
    assert parse_sp_string("2, 0, 0, 32, 0, 32").special_attack == 32
