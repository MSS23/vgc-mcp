"""Tests for the shared Smogon spread helpers."""

from vgc_mcp_core.models.pokemon import StatPointSpread
from vgc_mcp_core.tools.smogon_helpers import sps_from_smogon_spread


def test_champions_spread_becomes_stat_point_spread():
    spread = {"format_system": "champions", "sps": {"hp": 2, "attack": 32, "speed": 32}}
    sps = sps_from_smogon_spread(spread)
    assert isinstance(sps, StatPointSpread)
    assert (sps.hp, sps.attack, sps.speed) == (2, 32, 32)


def test_non_champions_or_empty_spreads_return_none():
    assert sps_from_smogon_spread(None) is None
    assert sps_from_smogon_spread({}) is None
    assert sps_from_smogon_spread({"format_system": "mainline", "evs": {"hp": 252}}) is None
    assert sps_from_smogon_spread({"format_system": "champions", "sps": {}}) is None
