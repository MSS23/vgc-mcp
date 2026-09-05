"""Independent probability and sequential-mechanic regression checks."""

from collections import Counter
from fractions import Fraction
from itertools import product

import pytest

from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.outcomes import calculate_move_outcomes, hit_count_weights
from vgc_mcp_core.models.move import Move
from vgc_mcp_core.models.pokemon import BaseStats, PokemonBuild


def mon(**kwargs):
    return PokemonBuild(name="Mew", types=["Psychic"], base_stats=BaseStats(
        hp=100, attack=100, defense=100, special_attack=100, special_defense=100, speed=100), **kwargs)


def kangaskhan():
    return PokemonBuild(name="Kangaskhan-Mega", types=["Normal"], ability="parental-bond",
                        base_stats=BaseStats(hp=105, attack=125, defense=100, special_attack=60,
                                             special_defense=100, speed=100))


RETURN = Move(name="Return", type="Normal", category="physical", power=102, accuracy=100)


@pytest.mark.parametrize("ability,item,first", [
    ("pressure", None, [70, 72, 72, 73, 73, 75, 75, 76, 78, 78, 79, 79, 81, 81, 82, 84]),
    ("multiscale", None, [35, 36, 36, 36, 36, 37, 37, 38, 39, 39, 39, 39, 40, 40, 41, 42]),
    # Chilan is consumed after hit one. Independent oracle runs with/without
    # the item pin each hit; calc 0.11.0 itself applies Chilan to both PB hits.
    ("pressure", "chilan-berry", [35, 36, 36, 36, 36, 37, 37, 38, 39, 39, 39, 39, 40, 40, 41, 42]),
])
def test_parental_bond_matches_independent_per_hit_oracle(ability, item, first):
    # @smogon/calc 0.11.0, level 50, neutral natures, zero EVs, 31 IVs.
    child = [16, 18, 18, 18, 18, 18, 18, 18, 19, 19, 19, 19, 19, 19, 19, 21]
    counts = Counter(a + b for a, b in product(first, child))
    expected = {damage: Fraction(count, 256) for damage, count in counts.items()}
    result = calculate_move_outcomes(kangaskhan(), mon(ability=ability, item=item), RETURN)
    assert result.damage_weights == expected


def test_parental_bond_power_up_punch_boosts_second_hit():
    move = Move(name="Power-Up Punch", type="Fighting", category="physical", power=40, accuracy=100)
    result = calculate_move_outcomes(kangaskhan(), mon(), move)
    # Independent calc per-hit arrays: first [9,9,10..11], child [3..4].
    assert (min(result.damage_weights), max(result.damage_weights)) == (12, 15)


@pytest.mark.parametrize("item,expected", [
    (None, {2: Fraction(7, 20), 3: Fraction(7, 20), 4: Fraction(3, 20), 5: Fraction(3, 20)}),
    ("loaded-dice", {4: Fraction(1, 2), 5: Fraction(1, 2)}),
])
def test_variable_hit_count_weights(item, expected):
    move = Move(name="bullet-seed", type="Grass", category="physical", power=25)
    assert hit_count_weights(move, DamageModifiers(), "", item, True) == expected
    assert hit_count_weights(move, DamageModifiers(), "skill-link", item, True) == {5: 1}


def test_population_bomb_misses_and_loaded_dice():
    move = Move(name="population-bomb", type="Normal", category="physical", power=20, accuracy=90)
    regular = calculate_move_outcomes(mon(), mon(), move)
    dice = calculate_move_outcomes(mon(item="loaded-dice"), mon(), move)
    assert regular.damage_weights[0] == Fraction(1, 10)
    assert sum(regular.damage_weights.values()) == 1
    assert dice.hit_weights == {hits: Fraction(1, 7) for hits in range(4, 11)}
    assert dice.damage_weights[0] == Fraction(1, 10)
    assert sum(dice.damage_weights.values()) == 1


def test_accuracy_affects_ko_probability_and_repeated_uses():
    move = RETURN.model_copy(update={"power": 10000, "accuracy": 75})
    result = calculate_move_outcomes(mon(), mon(), move)
    assert result.ko_chances == tuple(1 - Fraction(1, 4) ** n for n in range(1, 5))
    conditional = calculate_move_outcomes(mon(), mon(), move, include_accuracy=False)
    assert conditional.ko_chances == (1, 1, 1, 1)


@pytest.mark.parametrize("ability,item", [("sturdy", None), (None, "focus-sash")])
def test_single_hit_survival_protection_is_broken_by_second_hit(ability, item):
    move = RETURN.model_copy(update={"power": 10000})
    defender = mon(ability=ability, item=item)
    result = calculate_move_outcomes(mon(), defender, move)
    assert result.ko_chances == (0, 1, 1, 1)
    multi = calculate_move_outcomes(kangaskhan(), defender, move)
    assert multi.ko_chances[0] == 1


def test_healing_berry_not_reused_and_never_revives():
    # Sitrus triggers only for rolls leaving at most floor(175/2) HP.
    move = RETURN.model_copy(update={"power": 220})
    plain = calculate_move_outcomes(mon(), mon(), move)
    berry = calculate_move_outcomes(mon(), mon(item="sitrus-berry"), move)
    expected = {damage - 43 if damage >= 88 else damage: weight for damage, weight in plain.damage_weights.items()}
    assert berry.damage_weights == expected
    assert berry.ko_chances[1] < plain.ko_chances[1]
    lethal = calculate_move_outcomes(mon(), mon(item="sitrus-berry"), move.model_copy(update={"power": 10000}))
    assert lethal.ko_chances[0] == 1


def test_disguise_breaks_before_parental_child():
    single = calculate_move_outcomes(mon(), mon(ability="disguise"), RETURN)
    assert single.damage_weights == {21: Fraction(1)}
    multi = calculate_move_outcomes(kangaskhan(), mon(ability="disguise"), RETURN)
    assert (min(multi.damage_weights), max(multi.damage_weights)) == (37, 42)


def test_stamina_changes_damage_between_hits():
    move = Move(name="bullet-seed", type="Grass", category="physical", power=25)
    stamina = calculate_damage(mon(), mon(ability="stamina"), move)
    ordinary = calculate_damage(mon(), mon(), move)
    assert stamina.max_damage < ordinary.min_damage


def test_triple_axel_uses_increasing_power_and_separate_accuracy():
    move = Move(name="triple-axel", type="Ice", category="physical", power=20, accuracy=90)
    result = calculate_move_outcomes(mon(), mon(), move)
    assert result.damage_weights[0] == Fraction(1, 10)
    # All rolls across three hits sum to [47,58] on this neutral target.
    landed = calculate_move_outcomes(mon(), mon(), move, include_accuracy=False)
    assert max(landed.damage_weights) > 3 * max(calculate_damage(mon(), mon(), move.model_copy(update={"name": "ordinary"})).rolls)
    assert sum(result.damage_weights.values()) == 1


def test_invalid_hit_count_rejected():
    with pytest.raises(ValueError, match="supports"):
        calculate_move_outcomes(mon(), mon(), RETURN, DamageModifiers(move_hits=5))
