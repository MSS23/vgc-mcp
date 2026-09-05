"""Exact move outcomes with independent rolls and state between hits.

The ordinary calculator remains conditional on landing the chosen number of
hits. This module also supports move accuracy and random hit-count distributions.
Fractions preserve exact probability mass, including tiny survival chances.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import TYPE_CHECKING

from ..models.move import Move, MoveCategory, get_multi_hit_info
from ..models.pokemon import PokemonBuild
from ..utils.damage_verdicts import KOProbability, _format_ko_verdict
from ..utils.normalize import normalize_ability, normalize_item, normalize_move
from .modifiers import DamageModifiers
from .stats import calculate_all_stats

if TYPE_CHECKING:
    from .damage import DamageResult


@dataclass(frozen=True)
class OutcomeSummary:
    """Move-level outcomes; ranges express HP lost after any berry recovery."""

    hp: int
    damage_weights: dict[int, Fraction]
    ko_chances: tuple[Fraction, ...]
    hit_weights: dict[int, Fraction]
    accuracy_included: bool
    parental_bond: bool
    first_hit: "DamageResult"
    healing_item: bool


def hit_count_weights(
    move: Move, mods: DamageModifiers, ability: str, item: str, random_hits: bool
) -> dict[int, Fraction]:
    """Gen 9 2-5 hit weights; Loaded Dice and Skill Link override them."""
    info = get_multi_hit_info(move.name)
    low, high = info[:2] if info else (move.min_hits, move.max_hits)
    if mods.move_hits:
        if not low <= mods.move_hits <= high:
            raise ValueError(f"{move.name} supports {low}-{high} hits")
        return {mods.move_hits: Fraction(1)}
    if not random_hits or low == high or ability == "skill-link":
        return {high: Fraction(1)}
    if (low, high) == (2, 5):
        if item == "loaded-dice":
            return {4: Fraction(1, 2), 5: Fraction(1, 2)}
        return {2: Fraction(7, 20), 3: Fraction(7, 20), 4: Fraction(3, 20), 5: Fraction(3, 20)}
    # Population Bomb's hit count is determined by per-hit accuracy below.
    return {high: Fraction(1)}


def calculate_move_outcomes(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move: Move,
    modifiers: DamageModifiers | None = None,
    *,
    include_accuracy: bool = True,
    random_hits: bool = True,
    max_uses: int = 4,
) -> OutcomeSummary:
    """Resolve up to four uses, preserving consumed berries and remaining HP.

    Assumes no between-turn recovery, switches, or newly chosen moves. Accuracy
    uses the supplied Move accuracy; caller must encode accuracy/evasion changes.
    """
    from .damage import MOLD_BREAKER_ABILITIES, RESISTANCE_BERRIES, _calculate_damage_rolls

    if not 1 <= max_uses <= 4:
        raise ValueError("max_uses must be between 1 and 4")

    mods = modifiers or DamageModifiers()
    ability = normalize_ability(attacker.ability or "" if mods.attacker_ability is None else mods.attacker_ability)
    defender_ability = normalize_ability(defender.ability or "" if mods.defender_ability is None else mods.defender_ability)
    item = normalize_item(attacker.item or "" if mods.attacker_item is None else mods.attacker_item)
    defender_item = normalize_item(
        defender.item or "" if mods.defender_item is None else mods.defender_item
    )
    ignores_ability = ability in MOLD_BREAKER_ABILITIES and defender_item != "ability-shield"
    hp = calculate_all_stats(defender)["hp"]
    name = normalize_move(move.name)
    parental = ability == "parental-bond" and not get_multi_hit_info(move.name) and not move.is_multi_hit and not (
        move.is_spread and mods.is_doubles and mods.multiple_targets
    ) and move.is_damaging
    hit_weights = {2: Fraction(1)} if parental else hit_count_weights(move, mods, ability, item, random_hits)
    accuracy = Fraction(move.accuracy if move.accuracy is not None else 100, 100) if include_accuracy else Fraction(1)
    if include_accuracy and name in ("thunder", "hurricane"):
        if mods.weather in ("rain", "heavy_rain"):
            accuracy = Fraction(1)
        elif mods.weather in ("sun", "harsh_sun"):
            accuracy = Fraction(1, 2)
    if include_accuracy and name == "blizzard" and mods.weather == "snow":
        accuracy = Fraction(1)
    if item == "wide-lens":
        accuracy = min(Fraction(1), accuracy * Fraction(11, 10))
    if ability == "no-guard" or defender_ability == "no-guard":
        accuracy = Fraction(1)
    per_hit_accuracy = name in ("population-bomb", "triple-axel", "triple-kick")
    if per_hit_accuracy and (ability == "skill-link" or item == "loaded-dice"):
        per_hit_accuracy = False
    if name == "population-bomb" and item == "loaded-dice" and random_hits and not mods.move_hits:
        hit_weights = {hits: Fraction(1, 7) for hits in range(4, 11)}

    # State = (HP remaining, item consumed). Negative HP is retained for range
    # display; healing never revives a fainted Pokemon.
    # The hit counter only matters for deterministic on-hit effects; cap stage
    # effects at six to keep probability-state growth bounded.
    tracks_hits = defender_ability in ("stamina", "weak-armor", "disguise") or name == "power-up-punch"
    State = tuple[int, bool, int]
    cache: dict[tuple[int, bool, bool, int], DamageResult] = {}
    healing = defender_item in ("sitrus-berry", "oran-berry", "figy-berry", "wiki-berry", "mago-berry", "aguav-berry", "iapapa-berry")

    def hit_result(index: int, full: bool, consumed: bool, landed: int = 0) -> "DamageResult":
        key = index, full, consumed, landed
        if key not in cache:
            hit_move = move
            if name in ("triple-axel", "triple-kick"):
                hit_move = move.model_copy(update={"power": (20 if name == "triple-axel" else 10) * (index + 1)})
            hit_mods = replace(
                mods, move_hits=1, defender_at_full_hp=full,
                defender_item="" if consumed else defender_item,
                attack_stage=min(6, mods.attack_stage + (landed if name == "power-up-punch" else 0)),
                defense_stage=max(-6, min(6, mods.defense_stage + (
                    landed if defender_ability == "stamina" else
                    -landed if defender_ability == "weak-armor" and move.category == MoveCategory.PHYSICAL else 0))),
            )
            cache[key] = _calculate_damage_rolls(
                attacker, defender, hit_move, hit_mods, single_hit=True,
                parental_child=parental and index == 1,
            )
        return cache[key]

    first = hit_result(0, mods.defender_at_full_hp, False)

    def use_move(initial: dict[State, Fraction]) -> dict[State, Fraction]:
        final: defaultdict[State, Fraction] = defaultdict(Fraction)
        for hits, hit_weight in hit_weights.items():
            active = {state: weight * hit_weight for state, weight in initial.items()}
            for index in range(hits):
                following: defaultdict[State, Fraction] = defaultdict(Fraction)
                hit_accuracy = accuracy if index == 0 or per_hit_accuracy else Fraction(1)
                for (remaining, consumed, landed), weight in active.items():
                    final[(remaining, consumed, landed)] += weight * (1 - hit_accuracy)
                    result = hit_result(index, remaining == hp and mods.defender_at_full_hp, consumed, landed)
                    berry_activates = (
                        defender_item in RESISTANCE_BERRIES and not consumed
                        and RESISTANCE_BERRIES[defender_item] == result.details.get("effective_move_type", move.type.capitalize())
                        and (result.details.get("type_effectiveness", 0) >= 2 or defender_item == "chilan-berry")
                        and ability not in ("unnerve", "as-one-glastrier", "as-one-spectrier")
                    )
                    for roll, frequency in Counter(result.rolls).items():
                        disguise = roll > 0 and defender_ability == "disguise" and landed == 0 and not ignores_ability
                        if disguise:
                            roll = hp // 8
                        after = remaining - roll
                        used = consumed or berry_activates
                        if after <= 0 and remaining == hp and mods.defender_at_full_hp and (
                            (defender_item == "focus-sash" and not consumed) or
                            (defender_ability == "sturdy" and not ignores_ability)
                        ):
                            after = 1
                            used = used or defender_item == "focus-sash"
                        if healing and not used and after > 0 and ability not in ("unnerve", "as-one-glastrier", "as-one-spectrier"):
                            threshold = hp // 2 if defender_item in ("sitrus-berry", "oran-berry") or defender_ability == "gluttony" else hp // 4
                            if after <= threshold:
                                recovery = 10 if defender_item == "oran-berry" else hp // (4 if defender_item == "sitrus-berry" else 3)
                                if defender_ability == "ripen":
                                    recovery *= 2
                                after = min(hp, after + recovery)
                                used = True
                        new_landed = min(12, landed + int(roll > 0)) if tracks_hits else 0
                        following[(after, used, new_landed)] += weight * hit_accuracy * frequency / len(result.rolls)
                active = dict(following)
            for state, weight in active.items():
                final[state] += weight
        return {state: weight for state, weight in final.items() if weight}

    states: dict[State, Fraction] = {(hp, False, 0): Fraction(1)}
    probabilities: list[Fraction] = []
    damage_weights: defaultdict[int, Fraction] = defaultdict(Fraction)
    for use in range(max_uses):
        states = use_move(states)
        probabilities.append(sum((weight for (remaining, _, _), weight in states.items() if remaining <= 0), Fraction()))
        if use == 0:
            for (remaining, _, _), weight in states.items():
                damage_weights[hp - remaining] += weight
        # Subsequent uses need only survival states; combine all KOs.
        compact: defaultdict[State, Fraction] = defaultdict(Fraction)
        for (remaining, consumed, landed), weight in states.items():
            compact[(max(0, remaining), consumed, landed)] += weight
        states = dict(compact)
    return OutcomeSummary(
        hp, dict(damage_weights),
        tuple(probabilities),
        hit_weights, include_accuracy, parental, first, healing,
    )


def result_from_outcomes(summary: OutcomeSummary) -> "DamageResult":
    """Adapt exact weighted outcomes to the established damage result contract."""
    from .damage import DamageResult

    if len(summary.ko_chances) != 4:
        raise ValueError("The legacy damage result requires four move-use probabilities")

    low, high = min(summary.damage_weights), max(summary.damage_weights)
    chances = [float(probability * 100) for probability in summary.ko_chances]
    guaranteed = next((i for i, p in enumerate(summary.ko_chances, 1) if p == 1), None)
    probability = summary.ko_chances[0]
    verdict = _format_ko_verdict(chances[0], chances[1], chances[2], chances[3], guaranteed)
    ko = KOProbability(chances[0], chances[1], chances[2], chances[3], guaranteed,
                       probability.numerator, verdict, probability.denominator)
    details = dict(summary.first_hit.details)
    details.update({
        "hit_count": max(summary.hit_weights), "hit_count_distribution": {str(k): float(v) for k, v in summary.hit_weights.items()},
        "accuracy_included": summary.accuracy_included,
        "hit_count_basis": "Selected number of hits before accuracy checks; damage ranges retain overkill damage.",
        "damage_basis": "net HP loss after berry recovery" if summary.healing_item else "damage",
        "parental_bond": summary.parental_bond,
        "outcome_distribution": [{"damage": damage, "probability": float(weight)} for damage, weight in sorted(summary.damage_weights.items())],
        "probability_assumptions": "No switches or between-turn recovery. Base move accuracy with Wide Lens, No Guard and Thunder/Hurricane/Blizzard weather rules; no accuracy/evasion stages or other accuracy abilities/items.",
        "mechanics_scope": "Independent damage rolls, supplied accuracy, hit-count distribution, consumed resistance/healing berries, Focus Sash, Sturdy, Disguise, Multiscale, Stamina, Weak Armor and Power-Up Punch. Does not simulate recoil, contact retaliation, random secondary effects or all battle events.",
    })
    if summary.parental_bond:
        details["modifiers_applied"] = [*details.get("modifiers_applied", []), "Parental Bond (2nd hit 0.25x)"]
    if max(summary.hit_weights) > 1:
        details["modifiers_applied"] = [*details.get("modifiers_applied", []), f"Multi-hit ({max(summary.hit_weights)} hits)"]
    return DamageResult(
        low, high, int(low / summary.hp * 1000) / 10, int(high / summary.hp * 1000) / 10,
        [low + (high - low) * i // 15 for i in range(16)], summary.hp,
        verdict if high else "Immune (0 damage)", probability == 1, probability > 0,
        details, ko if high else None,
    )
