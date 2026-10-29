"""Item and chip tools share one format-aware stat helper."""

import pytest

from vgc_mcp_core.calc.stats import calculate_stat_for_format


def test_mainline_matches_ev_formula():
    # Incineroar base HP 95, 252 EVs -> 202 HP; base SpD 90, 252+ -> 156
    assert calculate_stat_for_format(95, 252, is_hp=True) == 202
    assert calculate_stat_for_format(90, 252, 31, 1.1) == 156


def test_champions_uses_stat_points_and_ignores_ivs():
    # 32 SP == 252 EVs; IVs are always 31 in Champions
    assert calculate_stat_for_format(95, 32, 0, is_hp=True, champions=True) == 202
    assert calculate_stat_for_format(90, 32, 0, 1.1, champions=True) == 156


def test_champions_rejects_ev_scale_numbers():
    with pytest.raises(ValueError, match="0-32"):
        calculate_stat_for_format(90, 252, champions=True)
