"""Regression test for the Paradox (Protosynthesis / Quark Drive) boosted-stat fix.

`damage.calculate_damage` auto-derives which stat Protosynthesis / Quark Drive
boosts via `_highest_non_hp_stat`, which now delegates to `calculate_all_stats`.
That delegation fixed a latent MAINLINE bug: the previous implementation dropped
the nature's +Speed boost when ranking stats, so a Timid (+Spe) build that had
*more* invested Speed than Special Attack could incorrectly pick Special Attack
as the boosted stat.

For a Timid 252 SpA / 252 Spe / 4 HP Iron Valiant the game-accurate boosted stat
is SPEED (invested Speed 184 > invested SpA 172). Because the boost lands on
Speed and not Special Attack, a special attack like Moonblast deals the SAME
damage as it would with no Paradox boost at all. These tests pin that behavior so
it can't silently regress back to boosting Special Attack.
"""

import pytest

from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, BaseStats, EVSpread
from vgc_mcp_core.models.move import Move, MoveCategory


def _iron_valiant() -> PokemonBuild:
    # Timid (+Spe / -Atk) 4 HP / 252 SpA / 252 Spe, base 74/130/90/120/60/116.
    return PokemonBuild(
        name="iron-valiant",
        base_stats=BaseStats(
            hp=74, attack=130, defense=90,
            special_attack=120, special_defense=60, speed=116,
        ),
        nature=Nature.TIMID,
        evs=EVSpread(hp=4, special_attack=252, speed=252),
        types=["Fairy", "Fighting"],
    )


def _neutral_dummy() -> PokemonBuild:
    # Plain 100-across, no investment, Normal type for neutral Fairy damage.
    return PokemonBuild(
        name="dummy",
        base_stats=BaseStats(
            hp=100, attack=100, defense=100,
            special_attack=100, special_defense=100, speed=100,
        ),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=["Normal"],
    )


def _moonblast() -> Move:
    return Move(
        name="moonblast",
        type="Fairy",
        category=MoveCategory.SPECIAL,
        power=95,
        accuracy=100,
        pp=15,
        target="normal",
    )


def _highest_non_hp_stat(p: PokemonBuild) -> str:
    """Mirror of damage._highest_non_hp_stat selection (Speed wins ties)."""
    stats = {k: v for k, v in calculate_all_stats(p).items() if k != "hp"}
    max_value = max(stats.values())
    tied = [s for s, v in stats.items() if v == max_value]
    return "speed" if "speed" in tied else tied[0]


def test_invested_speed_beats_invested_spa():
    """Sanity-pin the stat numbers the fix depends on: Speed 184 > SpA 172."""
    stats = calculate_all_stats(_iron_valiant())
    assert stats["speed"] == 184
    assert stats["special_attack"] == 172
    assert stats["speed"] > stats["special_attack"]


def test_quark_drive_boosts_speed_not_spa():
    """The boosted stat must be Speed (game-accurate), not Special Attack."""
    assert _highest_non_hp_stat(_iron_valiant()) == "speed"


def test_quark_drive_speed_boost_does_not_change_special_damage():
    """Quark Drive (Booster Energy) boosts Speed, so Moonblast damage is
    unchanged versus no Paradox boost. If the boost wrongly landed on Special
    Attack the range would jump (~102-120 instead of 76-91)."""
    iv = _iron_valiant()
    dummy = _neutral_dummy()
    moon = _moonblast()

    boosted = calculate_damage(
        iv, dummy, moon,
        DamageModifiers(attacker_ability="quark-drive", attacker_item="booster-energy"),
    )
    baseline = calculate_damage(iv, dummy, moon, DamageModifiers())

    # Stable, game-accurate range vs the neutral 100-bulk dummy.
    assert boosted.min_damage == 76
    assert boosted.max_damage == 91

    # Boost landed on Speed -> special damage identical to the no-boost case.
    assert boosted.min_damage == baseline.min_damage
    assert boosted.max_damage == baseline.max_damage


def test_electric_terrain_quark_drive_also_boosts_speed():
    """Electric Terrain is the other Quark Drive trigger; same Speed selection,
    so special damage is still unchanged."""
    iv = _iron_valiant()
    dummy = _neutral_dummy()
    moon = _moonblast()

    boosted = calculate_damage(
        iv, dummy, moon,
        DamageModifiers(attacker_ability="quark-drive", terrain="electric"),
    )
    assert boosted.min_damage == 76
    assert boosted.max_damage == 91


def test_wrongly_boosting_spa_would_raise_damage():
    """Guard the contrast: forcing the (incorrect) SpA boost yields a clearly
    higher range, proving the Speed selection materially matters."""
    iv = _iron_valiant()
    dummy = _neutral_dummy()
    moon = _moonblast()

    wrong = calculate_damage(
        iv, dummy, moon,
        DamageModifiers(
            attacker_ability="quark-drive",
            attacker_item="booster-energy",
            quark_drive_boost="special_attack",
        ),
    )
    assert wrong.max_damage > 91  # ~120: distinct from the correct 91
