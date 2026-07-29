"""Tests for Phase-4 engine accuracy fixes: Parental Bond, Knock Off,
and Smogon month arithmetic."""

from vgc_mcp_core.calc.damage import DamageModifiers, calculate_damage
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature, PokemonBuild


def _mon(name, types, **base):
    stats = {
        "hp": 100, "attack": 100, "defense": 100,
        "special_attack": 100, "special_defense": 100, "speed": 100,
    }
    stats.update(base)
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(**stats),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=types,
    )


# ---------------------------------------------------------------------------
# Parental Bond (0.5)
# ---------------------------------------------------------------------------

def test_parental_bond_adds_roughly_25_percent():
    kang = _mon("kangaskhan-mega", ["Normal"], attack=125)
    foe = _mon("target", ["Water"])
    move = Move(name="double-edge", type="Normal", category=MoveCategory.PHYSICAL, power=120)

    base = calculate_damage(kang, foe, move, DamageModifiers(attacker_ability="Scrappy"))
    pb = calculate_damage(kang, foe, move, DamageModifiers(attacker_ability="Parental Bond"))

    assert pb.max_damage > base.max_damage
    ratio = pb.max_damage / base.max_damage
    assert 1.20 <= ratio <= 1.30


def test_parental_bond_does_not_apply_to_spread_moves():
    kang = _mon("kangaskhan-mega", ["Normal"], attack=125)
    foe = _mon("target", ["Water"])
    spread = Move(
        name="rock-slide", type="Rock", category=MoveCategory.PHYSICAL,
        power=75, target="all-opponents",
    )
    mods = DamageModifiers(
        attacker_ability="Parental Bond", is_doubles=True, multiple_targets=True
    )
    base_mods = DamageModifiers(
        attacker_ability="Scrappy", is_doubles=True, multiple_targets=True
    )
    pb = calculate_damage(kang, foe, spread, mods)
    base = calculate_damage(kang, foe, spread, base_mods)
    # Spread move: Parental Bond strikes only once, so no boost.
    assert pb.max_damage == base.max_damage


def test_parental_bond_ignored_on_immune_target():
    kang = _mon("kangaskhan-mega", ["Normal"], attack=125)
    ghost = _mon("gastly", ["Ghost"])
    move = Move(name="body-slam", type="Normal", category=MoveCategory.PHYSICAL, power=85)
    pb = calculate_damage(kang, ghost, move, DamageModifiers(attacker_ability="Parental Bond"))
    assert pb.max_damage == 0


# ---------------------------------------------------------------------------
# Knock Off (2.1)
# ---------------------------------------------------------------------------

def test_knock_off_boosted_when_target_holds_item():
    attacker = _mon("weavile", ["Dark", "Ice"], attack=120)
    defender = _mon("target", ["Psychic"])
    knock = Move(name="knock-off", type="Dark", category=MoveCategory.PHYSICAL, power=65)

    with_item = calculate_damage(
        attacker, defender, knock, DamageModifiers(defender_item="leftovers")
    )
    without_item = calculate_damage(
        attacker, defender, knock, DamageModifiers(defender_item=None)
    )
    assert with_item.max_damage > without_item.max_damage
    ratio = with_item.max_damage / without_item.max_damage
    assert 1.45 <= ratio <= 1.55


# ---------------------------------------------------------------------------
# Smogon month arithmetic (2.2)
# ---------------------------------------------------------------------------

def test_recent_months_are_distinct_and_descending():
    from vgc_mcp_core.api.cache import APICache
    from vgc_mcp_core.api.smogon import SmogonStatsClient

    client = SmogonStatsClient(APICache())
    months = client._get_recent_months(count=6)
    assert len(months) == 6
    assert len(set(months)) == 6  # no duplicates (the old 30-day bug repeated)
    # Strictly descending YYYY-MM strings.
    assert months == sorted(months, reverse=True)
    # Each is a valid calendar month.
    for m in months:
        year, mon = m.split("-")
        assert 1 <= int(mon) <= 12
