"""Golden tests for verified Gen 9 damage-math fixes in calc/damage.py.

Each test pins the Showdown-correct (@smogon/calc) expected values for one of the
twelve audited bugs. Expected numbers are hard-coded ground truth from the audit
oracle — they are NOT computed from the code under test.

Stat construction reference (level 50, 0 EV / 31 IV, neutral nature):
    "other" stat = floor(floor((2*base + 31) * 0.5) + 5)
        base 77  -> 97
        base 100 -> 120
        base 120 -> 140
        base 132 -> 152
    HP stat = floor((2*base + 31) * 0.5) + 60
        base 100 -> 175
"""

import math

import pytest

from vgc_mcp_core.calc.damage import (
    calculate_damage,
    apply_stat_stage,
    apply_mod,
    chain_mods,
    poke_round,
    MOD_SHEER_FORCE,
    MOD_TOUGH_CLAWS,
    MOD_TYPE_BOOST,
    MOD_MUSCLE_BAND,
)
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, BaseStats, EVSpread
from vgc_mcp_core.models.move import Move, MoveCategory


def mon(name, types, **base_overrides):
    """Build a level-50, 0-EV/31-IV, neutral-nature Pokemon with given base stats."""
    base = dict(
        hp=100, attack=100, defense=100,
        special_attack=100, special_defense=100, speed=100,
    )
    base.update(base_overrides)
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(**base),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=types,
    )


# ---------------------------------------------------------------------------
# Fix 1 — Tinted Lens applied (doubles resisted damage)
# ---------------------------------------------------------------------------
def test_fix1_tinted_lens_doubles_resisted_damage():
    """Tinted Lens turns a 0.5x (resisted) hit into an effective 1.0x hit.

    Yanmega (Bug) Bug Buzz vs Registeel (Steel) is 0.5x. With Tinted Lens the
    rolls must be EXACTLY double the non-Tinted-Lens rolls (i.e. equal to a
    neutral 1.0x calc).
    """
    yanmega = mon("yanmega", ["Bug", "Flying"], special_attack=116)
    registeel = mon("registeel", ["Steel"], special_defense=150, defense=150, hp=80)
    bug_buzz = Move(
        name="bug-buzz", type="bug", category=MoveCategory.SPECIAL,
        power=90, accuracy=100, pp=10,
    )

    no_tl = calculate_damage(yanmega, registeel, bug_buzz, DamageModifiers(is_doubles=True))
    with_tl = calculate_damage(
        yanmega, registeel, bug_buzz,
        DamageModifiers(is_doubles=True, attacker_ability="tinted-lens"),
    )

    # Every roll must be exactly doubled (2x = back to neutral).
    assert with_tl.rolls == [r * 2 for r in no_tl.rolls]
    # Sanity: the hit really was resisted before Tinted Lens.
    assert no_tl.details["type_effectiveness"] == 0.5


# ---------------------------------------------------------------------------
# Fix 2 — Burn is a discrete floor(d/2) step, not in the final-mod chain
# ---------------------------------------------------------------------------
def test_fix2_burn_with_life_orb():
    """Burn + Life Orb. Fire Atk 97 vs Normal Def 152, physical BP120.

    Showdown applies burn as floor(d/2) BEFORE the chained final mods (Life Orb).
    """
    attacker = mon("fire-mon", ["Fire"], attack=77)        # base 77 -> Atk 97
    defender = mon("normal-mon", ["Normal"], defense=132, hp=132)  # base 132 -> Def 152
    move = Move(
        name="fire-punch-like", type="fire", category=MoveCategory.PHYSICAL,
        power=120, accuracy=100, pp=10,
    )
    result = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, attacker_burned=True, attacker_item="life-orb"),
    )
    assert result.rolls == [27, 29, 29, 29, 30, 30, 30, 31, 31, 31, 31, 31, 31, 32, 32, 34]


# ---------------------------------------------------------------------------
# Fix 3 — Terrain boost is a base-power modifier
# ---------------------------------------------------------------------------
def test_fix3_electric_terrain_is_base_power():
    """Electric BP50, SpA 120 vs SpD 120, grounded, Electric Terrain, no STAB.

    Applying the terrain boost as a base-power mod yields rolls 25..30
    (NOT 26..31, which is what applying it post-formula produced).
    """
    attacker = mon("a", ["Normal"], special_attack=100)   # base 100 -> SpA 120
    defender = mon("d", ["Normal"])                         # base 100 -> SpD 120
    move = Move(
        name="shock", type="electric", category=MoveCategory.SPECIAL,
        power=50, accuracy=100, pp=10,
    )
    result = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, terrain="electric", attacker_grounded=True),
    )
    assert result.rolls == [25, 25, 26, 26, 26, 27, 27, 27, 27, 28, 28, 28, 29, 29, 29, 30]


# ---------------------------------------------------------------------------
# Fix 4 — Stat stages use exact integer floor math
# ---------------------------------------------------------------------------
def test_fix4_stat_stage_negative_floor():
    """Attack 100 at -1 stage = floor(100 * 2 / 3) = 66 (NOT 67)."""
    assert apply_stat_stage(100, -1) == 66
    assert apply_stat_stage(100, 1) == 150       # floor(100 * 3 / 2)
    assert apply_stat_stage(100, -2) == 50       # floor(100 * 2 / 4)
    assert apply_stat_stage(100, 2) == 200       # floor(100 * 4 / 2)
    assert apply_stat_stage(100, 0) == 100


def test_fix4_intimidate_in_damage():
    """Intimidate (-1 Atk) applied through calculate_damage uses the floor result."""
    attacker = mon("a", ["Normal"], attack=100)   # base 100 -> Atk 120
    defender = mon("d", ["Normal"])
    move = Move(
        name="hit", type="normal", category=MoveCategory.PHYSICAL,
        power=80, accuracy=100, pp=10,
    )
    result = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, attack_stage=-1),
    )
    # 120 Atk at -1 = floor(120 * 2 / 3) = 80
    assert result.details["attacker_stat"] == 80


# ---------------------------------------------------------------------------
# Fix 5 — Embody Aspect (Hearthflame) not double-counted (1.5x, not ~2.24x)
# ---------------------------------------------------------------------------
def test_fix5_embody_aspect_single_count():
    """Ogerpon-Hearthflame +1 Atk on Tera = exactly 1.5x the attacking stat."""
    ogerpon = mon("ogerpon-hearthflame", ["Grass", "Fire"], attack=120)  # base 120 -> Atk 140
    defender = mon("d", ["Normal"])
    move = Move(
        name="hit", type="normal", category=MoveCategory.PHYSICAL,
        power=80, accuracy=100, pp=10,
    )
    result = calculate_damage(
        ogerpon, defender, move,
        DamageModifiers(is_doubles=True, attacker_ability="embody-aspect",
                        tera_active=True, tera_type="fire"),
    )
    # 140 * 3 // 2 = 210 (single +1 stage). Double-counting would give ~314.
    assert result.details["attacker_stat"] == 210


# ---------------------------------------------------------------------------
# Fix 6 — Crits ignore screens
# ---------------------------------------------------------------------------
def test_fix6_crit_ignores_screen():
    """On a critical hit, Reflect must NOT reduce damage."""
    attacker = mon("a", ["Normal"], attack=120)   # Atk 140
    defender = mon("d", ["Normal"])
    move = Move(
        name="hit", type="normal", category=MoveCategory.PHYSICAL,
        power=80, accuracy=100, pp=10,
    )
    crit_with_reflect = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, is_critical=True, reflect_up=True),
    )
    crit_no_reflect = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, is_critical=True, reflect_up=False),
    )
    noncrit_with_reflect = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, is_critical=False, reflect_up=True),
    )
    # Crit through Reflect == crit with no screen (screen ignored on crit).
    assert crit_with_reflect.rolls == crit_no_reflect.rolls
    # But a non-crit through Reflect IS reduced (sanity: screen still works normally).
    assert noncrit_with_reflect.rolls != crit_no_reflect.rolls


# ---------------------------------------------------------------------------
# Fix 7 — Sheer Force uses 5325 (1.3x), only when the move has a secondary effect
# ---------------------------------------------------------------------------
def test_fix7_sheer_force_constant():
    """Sheer Force base-power apply with 5325: BP65->85, BP75->98, BP95->124."""
    assert MOD_SHEER_FORCE == 5325
    assert poke_round(65 * MOD_SHEER_FORCE / 4096) == 85
    assert poke_round(75 * MOD_SHEER_FORCE / 4096) == 98
    assert poke_round(95 * MOD_SHEER_FORCE / 4096) == 124
    # Unchanged BPs (these happen to round the same under 5325).
    assert poke_round(80 * MOD_SHEER_FORCE / 4096) == 104
    assert poke_round(90 * MOD_SHEER_FORCE / 4096) == 117
    assert poke_round(100 * MOD_SHEER_FORCE / 4096) == 130
    assert poke_round(120 * MOD_SHEER_FORCE / 4096) == 156


def test_fix7_sheer_force_only_with_secondary():
    """Sheer Force boosts power only when the move has an effect_chance."""
    attacker = mon("a", ["Normal"], attack=100)
    defender = mon("d", ["Normal"])
    move_secondary = Move(
        name="secondary-move", type="normal", category=MoveCategory.PHYSICAL,
        power=80, accuracy=100, pp=10, effect_chance=10,
    )
    move_plain = Move(
        name="plain-move", type="normal", category=MoveCategory.PHYSICAL,
        power=80, accuracy=100, pp=10,
    )
    r_sec = calculate_damage(
        attacker, defender, move_secondary,
        DamageModifiers(is_doubles=True, attacker_ability="sheer-force"),
    )
    r_plain = calculate_damage(
        attacker, defender, move_plain,
        DamageModifiers(is_doubles=True, attacker_ability="sheer-force"),
    )
    # BP 80 -> 104 with Sheer Force; plain stays 80.
    assert r_sec.details["base_power"] == 104
    assert r_plain.details["base_power"] == 80


# ---------------------------------------------------------------------------
# Fix 8 — Base-power mods chained, not applied per-step
# ---------------------------------------------------------------------------
def test_fix8_base_power_mods_chained():
    """Tough Claws (5325) + type-boost item (4915) chained: BP65->101 (not 102)."""
    chained = chain_mods([MOD_TOUGH_CLAWS, MOD_TYPE_BOOST])
    assert max(1, poke_round(65 * chained / 4096)) == 101
    assert max(1, poke_round(75 * chained / 4096)) == 117
    assert max(1, poke_round(95 * chained / 4096)) == 148


def test_fix8_base_power_chained_in_damage():
    """Tough Claws + Charcoal (Fire) on a contact Fire move chains to BP101 from 65."""
    attacker = mon("a", ["Normal"], attack=100)
    defender = mon("d", ["Normal"])
    move = Move(
        name="fire-contact", type="fire", category=MoveCategory.PHYSICAL,
        power=65, accuracy=100, pp=10, makes_contact=True,
    )
    result = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, attacker_ability="tough-claws",
                        attacker_item="charcoal"),
    )
    assert result.details["base_power"] == 101


# ---------------------------------------------------------------------------
# Fix 9 — Muscle Band value 4505 and applied as base-power mod
# ---------------------------------------------------------------------------
def test_fix9_muscle_band_value_and_stage():
    """Muscle Band is 4505 and boosts base power (not final damage)."""
    assert MOD_MUSCLE_BAND == 4505
    attacker = mon("a", ["Normal"], attack=100)
    defender = mon("d", ["Normal"])
    move = Move(
        name="hit", type="normal", category=MoveCategory.PHYSICAL,
        power=100, accuracy=100, pp=10,
    )
    result = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, attacker_item="muscle-band"),
    )
    # BP 100 * 4505/4096 = 109.99 -> poke_round 110, applied at base-power stage.
    assert result.details["base_power"] == poke_round(100 * 4505 / 4096) == 110


# ---------------------------------------------------------------------------
# Fix 10 — Helping Hand (and Punching Glove) are base-power mods
# ---------------------------------------------------------------------------
def test_fix10_helping_hand_is_base_power():
    """Helping Hand boosts base power by 1.5x at the base-power stage."""
    attacker = mon("a", ["Normal"], attack=100)
    defender = mon("d", ["Normal"])
    move = Move(
        name="hit", type="normal", category=MoveCategory.PHYSICAL,
        power=80, accuracy=100, pp=10,
    )
    result = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, helping_hand=True),
    )
    # BP 80 * 1.5 = 120 at base-power stage.
    assert result.details["base_power"] == 120


def test_fix10_punching_glove_is_base_power():
    """Punching Glove (4506) boosts a punch move's base power."""
    attacker = mon("a", ["Normal"], attack=100)
    defender = mon("d", ["Normal"])
    move = Move(
        name="ice-punch", type="ice", category=MoveCategory.PHYSICAL,
        power=75, accuracy=100, pp=10,
    )
    result = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, attacker_item="punching-glove"),
    )
    # BP 75 * 4506/4096 = 82.5 -> poke_round 82 (0.5 rounds DOWN).
    assert result.details["base_power"] == poke_round(75 * 4506 / 4096)


# ---------------------------------------------------------------------------
# Fix 11 — Collision Course / Electro Drift super-effective boost is base-power
# ---------------------------------------------------------------------------
def test_fix11_collision_course_super_effective():
    """Collision Course, Atk 140 / Def 120 / HP 175, 2x SE -> 67.4-80.0%."""
    attacker = mon("a", ["Normal"], attack=120)   # base 120 -> Atk 140
    defender = mon("d", ["Normal"])               # base 100 -> Def 120, HP 175
    move = Move(
        name="collision-course", type="fighting", category=MoveCategory.PHYSICAL,
        power=100, accuracy=100, pp=5,
    )
    result = calculate_damage(attacker, defender, move, DamageModifiers(is_doubles=True))
    assert result.rolls == [
        118, 120, 120, 122, 124, 126, 126, 128, 130, 130, 132, 134, 134, 136, 138, 140
    ]
    assert result.min_percent == 67.4
    assert result.max_percent == 80.0


# ---------------------------------------------------------------------------
# Fix 12 — Cosmetic STAB label for 2.25x (Tera + Adaptability)
# ---------------------------------------------------------------------------
def test_fix12_stab_label_tera_adaptability():
    """A 2.25x STAB (Tera into same type + Adaptability) is labelled correctly."""
    attacker = mon("a", ["Fire"], special_attack=100)
    defender = mon("d", ["Normal"])
    move = Move(
        name="flamethrower", type="fire", category=MoveCategory.SPECIAL,
        power=90, accuracy=100, pp=10,
    )
    result = calculate_damage(
        attacker, defender, move,
        DamageModifiers(is_doubles=True, tera_active=True, tera_type="fire",
                        has_adaptability=True, attacker_ability="adaptability"),
    )
    labels = result.details["modifiers_applied"]
    assert "STAB (2.25x - Tera+Adaptability)" in labels
