"""Exhaustively compare legal stat inputs to independent integer formulas."""

import pytest

from vgc_mcp_core.calc.stats import calculate_hp, calculate_stat
from vgc_mcp_core.calc.stats_champions import calculate_hp_sp, calculate_stat_sp


@pytest.mark.parametrize("level", [1, 50, 100])
@pytest.mark.parametrize("iv", [0, 31])
def test_mainline_formula_grid(level, iv):
    for base in range(2, 256):
        for ev in range(0, 253, 4):
            inner = (2 * base + iv + ev // 4) * level // 100
            assert calculate_hp(base, iv, ev, level) == inner + level + 10
            for numerator in (9, 10, 11):
                assert calculate_stat(base, iv, ev, level, numerator / 10) == (
                    (inner + 5) * numerator // 10
                )


def test_champions_closed_formula_grid():
    for base in range(2, 256):
        for sp in range(33):
            assert calculate_hp_sp(base, sp=sp) == base + sp + 75
            for numerator in (9, 10, 11):
                assert calculate_stat_sp(base, sp=sp, nature_mod=numerator / 10) == (
                    (base + sp + 20) * numerator // 10
                )
