"""Exact independent-roll checks, including ten-hit performance regressions."""

from itertools import product

import pytest

from vgc_mcp_core.utils.damage_verdicts import (
    calculate_ko_probability,
    calculate_multi_hit_ko_probability,
)


@pytest.mark.parametrize("hits", [2, 3, 5])
@pytest.mark.parametrize("hp", [10, 25, 40])
def test_multihit_matches_independent_enumeration(hits, hp):
    rolls = [2, 3, 3, 8]
    expected = sum(sum(combo) >= hp for combo in product(rolls, repeat=hits))
    result = calculate_multi_hit_ko_probability(rolls, hits, hp)
    assert result.rolls_that_ohko == expected
    assert result.total_combinations == len(rolls) ** hits
    assert result.ohko_chance == round(100 * expected / len(rolls) ** hits, 2)


def test_ten_hits_are_exact_without_enumerating_a_trillion_combinations():
    # Only the all-minimum outcome fails: count it independently by hand.
    result = calculate_multi_hit_ko_probability([1] + [2] * 15, 10, 11)
    assert result.total_combinations == 16 ** 10
    assert result.rolls_that_ohko == 16 ** 10 - 1
    assert result.guaranteed_ko == 2
    assert "Guaranteed" not in result.verdict


def test_near_certain_threehko_is_not_guaranteed():
    result = calculate_ko_probability([10] + [11] * 15, 31)
    assert result.guaranteed_ko == 4
    assert result.threehko_chance == 99.98
    assert result.verdict == "99.98% chance to 3HKO"


def test_two_uses_of_a_multihit_move_can_guarantee_a_ko():
    result = calculate_multi_hit_ko_probability([10] * 16, 3, 50)
    assert result.ohko_chance == 0
    assert result.twohko_chance == 100
    assert result.guaranteed_ko == 2
    assert result.verdict == "Guaranteed 2HKO"


def test_singlehit_probabilities_match_independent_enumeration():
    rolls = [1, 5, 5, 7]
    result = calculate_ko_probability(rolls, 16)
    for uses, actual in enumerate([
        result.ohko_chance, result.twohko_chance, result.threehko_chance, result.fourhko_chance
    ], 1):
        expected = sum(sum(combo) >= 16 for combo in product(rolls, repeat=uses))
        assert actual == round(100 * expected / len(rolls) ** uses, 2)
