"""Unit tests for `vgc_mcp_core/tools/ability_helpers.py`.

Locks in the contract for:
  - resolve_ability — explicit override > mega-form > Smogon > pokeapi
  - compute_intimidate_attack_stage — every blocker / punisher branch
  - compute_static_attacker_stat_stages — Intrepid Sword, Embody Aspect

Also has end-to-end coverage of the engine-level auto-derives that depend on
this module: Adaptability, Protosynthesis/Quark Drive, Intrepid Sword,
Embody Aspect Hearthflame.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature, PokemonBuild
from vgc_mcp_core.tools.ability_helpers import (
    compute_intimidate_attack_stage,
    compute_static_attacker_stat_stages,
    resolve_ability,
)

# ---------------------------------------------------------------------------
# resolve_ability
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pokeapi():
    p = MagicMock()
    p.get_pokemon_abilities = AsyncMock(return_value=["Inner Focus", "Multiscale"])
    return p


@pytest.fixture
def mock_smogon_with(spread_ability):
    """Factory: build a mock smogon client whose top spread reports `spread_ability`."""
    def _make(spread_ability):
        s = MagicMock()
        s.get_pokemon_usage = AsyncMock(return_value={
            "spreads": [{"nature": "Adamant", "evs": {"attack": 252}, "usage": 0.5}],
            "items": {"life-orb": 0.4},
            "abilities": {spread_ability: 0.95} if spread_ability else {},
        })
        return s
    return _make


async def test_resolve_ability_user_override_wins(mock_pokeapi):
    ab, src = await resolve_ability(
        "dragonite", pokeapi=mock_pokeapi, user_override="multiscale",
    )
    assert ab == "multiscale"
    assert src == "custom"
    mock_pokeapi.get_pokemon_abilities.assert_not_called()


async def test_resolve_ability_mega_form_takes_precedence(mock_pokeapi):
    # Mega Manectric's ability is "Intimidate" — should win even if pokeapi
    # would return something else.
    ab, src = await resolve_ability("manectric-mega", pokeapi=mock_pokeapi)
    assert ab == "Intimidate"
    assert src == "mega-form"


async def test_resolve_ability_smogon_preferred_over_pokeapi(mock_pokeapi):
    smogon = MagicMock()
    smogon.get_pokemon_usage = AsyncMock(return_value={
        "spreads": [{"nature": "Adamant", "evs": {"attack": 252}, "usage": 0.5}],
        "items": {"lum-berry": 0.5},
        "abilities": {"Multiscale": 0.95, "Inner Focus": 0.05},
    })
    ab, src = await resolve_ability(
        "dragonite", pokeapi=mock_pokeapi, smogon_client=smogon,
    )
    assert ab == "multiscale"
    assert src == "smogon"


async def test_resolve_ability_pokeapi_fallback_when_smogon_empty(mock_pokeapi):
    smogon = MagicMock()
    smogon.get_pokemon_usage = AsyncMock(return_value=None)
    ab, src = await resolve_ability(
        "dragonite", pokeapi=mock_pokeapi, smogon_client=smogon,
    )
    assert ab == "Inner Focus"
    assert src == "pokeapi"


async def test_resolve_ability_unknown_when_everything_fails():
    pokeapi = MagicMock()
    pokeapi.get_pokemon_abilities = AsyncMock(return_value=[])
    ab, src = await resolve_ability("unknown", pokeapi=pokeapi)
    assert ab is None
    assert src == "unknown"


# ---------------------------------------------------------------------------
# compute_intimidate_attack_stage
# ---------------------------------------------------------------------------


def test_intimidate_default_drops_attack():
    stage, note = compute_intimidate_attack_stage(
        defender_ability="intimidate",
        attacker_ability="protean",
        is_physical=True,
    )
    assert stage == -1
    assert "Intimidate" in note


def test_intimidate_no_op_for_special_moves():
    stage, note = compute_intimidate_attack_stage(
        defender_ability="intimidate",
        attacker_ability="protean",
        is_physical=False,
    )
    assert stage == 0
    assert note is None


def test_intimidate_blocked_by_clear_body():
    stage, note = compute_intimidate_attack_stage(
        defender_ability="intimidate",
        attacker_ability="clear-body",
        is_physical=True,
    )
    assert stage == 0
    assert "blocked" in note.lower()


def test_intimidate_blocked_by_inner_focus():
    stage, _ = compute_intimidate_attack_stage(
        defender_ability="intimidate",
        attacker_ability="inner-focus",
        is_physical=True,
    )
    assert stage == 0


def test_intimidate_punished_by_defiant():
    stage, note = compute_intimidate_attack_stage(
        defender_ability="intimidate",
        attacker_ability="defiant",
        is_physical=True,
    )
    assert stage == 1  # -1 + 2
    assert "Defiant" in note


def test_intimidate_punished_by_contrary():
    stage, note = compute_intimidate_attack_stage(
        defender_ability="intimidate",
        attacker_ability="contrary",
        is_physical=True,
    )
    assert stage == 1
    assert "Contrary" in note


def test_intimidate_competitive_no_atk_boost_for_physical():
    # Competitive boosts SpA — physical attacker still loses Atk stage
    stage, note = compute_intimidate_attack_stage(
        defender_ability="intimidate",
        attacker_ability="competitive",
        is_physical=True,
    )
    assert stage == -1
    assert "Competitive" in note


def test_intimidate_apply_false_disables():
    stage, note = compute_intimidate_attack_stage(
        defender_ability="intimidate",
        attacker_ability="protean",
        is_physical=True,
        apply=False,
    )
    assert stage == 0
    assert note is None


def test_intimidate_no_op_when_defender_lacks_intimidate():
    stage, note = compute_intimidate_attack_stage(
        defender_ability="multiscale",
        attacker_ability="protean",
        is_physical=True,
    )
    assert stage == 0
    assert note is None


# ---------------------------------------------------------------------------
# compute_static_attacker_stat_stages
# ---------------------------------------------------------------------------


def test_intrepid_sword_adds_atk_stage():
    atk, spa, note = compute_static_attacker_stat_stages(
        attacker_ability="intrepid-sword",
    )
    assert atk == 1
    assert spa == 0
    assert note and "Intrepid Sword" in note


def test_embody_aspect_hearthflame_only_on_tera():
    # Off-Tera → no boost
    atk, _, note = compute_static_attacker_stat_stages(
        attacker_ability="embody-aspect-hearthflame",
        attacker_name="ogerpon-hearthflame",
        tera_active=False,
    )
    assert atk == 0
    assert note is None
    # Tera-on → +1 Atk
    atk, _, note = compute_static_attacker_stat_stages(
        attacker_ability="embody-aspect-hearthflame",
        attacker_name="ogerpon-hearthflame",
        tera_active=True,
    )
    assert atk == 1
    assert "Hearthflame" in note


def test_static_stages_are_zero_for_normal_abilities():
    atk, spa, note = compute_static_attacker_stat_stages(
        attacker_ability="protean",
    )
    assert atk == 0
    assert spa == 0
    assert note is None


# ---------------------------------------------------------------------------
# Engine-level auto-derive integration tests
# ---------------------------------------------------------------------------


def _build(name: str, base: BaseStats, types: list[str], *,
           ability=None, item=None, evs=None, nature=Nature.SERIOUS,
           tera_type=None) -> PokemonBuild:
    return PokemonBuild(
        name=name, base_stats=base, types=types,
        nature=nature, evs=evs or EVSpread(),
        ability=ability, item=item, tera_type=tera_type,
    )


# Use Garchomp for a simple Dragon defender; doesn't matter much for these
GARCHOMP = BaseStats(hp=108, attack=130, defense=95, special_attack=80, special_defense=85, speed=102)
DRAGAPULT = BaseStats(hp=88, attack=120, defense=75, special_attack=100, special_defense=75, speed=142)
IRON_HANDS = BaseStats(hp=154, attack=140, defense=108, special_attack=50, special_defense=68, speed=50)


def _make_simple_move(category: str = "physical", power: int = 80,
                      move_type: str = "Normal"):
    """Construct a minimal Move stub just sufficient for calculate_damage."""
    from vgc_mcp_core.models.move import Move, MoveCategory
    return Move(
        name="test-move", power=power, accuracy=100, pp=10,
        category=MoveCategory(category), type=move_type,
        target="selected-pokemon", priority=0,
    )


def test_engine_auto_applies_adaptability():
    move = _make_simple_move(category="special", power=80, move_type="Ghost")
    a_no = _build("dragapult", DRAGAPULT, ["Dragon", "Ghost"], ability="clear-body",
                  evs=EVSpread(special_attack=252), nature=Nature.TIMID)
    a_ad = _build("dragapult", DRAGAPULT, ["Dragon", "Ghost"], ability="adaptability",
                  evs=EVSpread(special_attack=252), nature=Nature.TIMID)
    d = _build("garchomp", GARCHOMP, ["Dragon", "Ground"], nature=Nature.CAREFUL)
    r_no = calculate_damage(a_no, d, move, DamageModifiers(is_doubles=True))
    r_ad = calculate_damage(a_ad, d, move, DamageModifiers(is_doubles=True))
    assert r_ad.max_damage > r_no.max_damage, (
        f"Adaptability should boost STAB: {r_no.max_damage} -> {r_ad.max_damage}"
    )
    # Adaptability is 2x STAB instead of 1.5x → 1.333x more damage
    assert r_ad.max_damage / r_no.max_damage == pytest.approx(2 / 1.5, rel=0.05)


def test_engine_auto_applies_quark_drive_with_booster_energy():
    move = _make_simple_move(category="physical", power=80, move_type="Normal")
    a_no = _build("iron-hands", IRON_HANDS, ["Fighting", "Electric"], ability="quark-drive",
                  evs=EVSpread(attack=252), nature=Nature.ADAMANT)
    a_be = _build("iron-hands", IRON_HANDS, ["Fighting", "Electric"], ability="quark-drive",
                  item="booster-energy", evs=EVSpread(attack=252), nature=Nature.ADAMANT)
    d = _build("garchomp", GARCHOMP, ["Dragon", "Ground"], nature=Nature.IMPISH)
    r_no = calculate_damage(a_no, d, move, DamageModifiers(is_doubles=True))
    r_be = calculate_damage(a_be, d, move, DamageModifiers(is_doubles=True))
    assert r_be.max_damage > r_no.max_damage, (
        f"Booster Energy should activate Quark Drive on Iron Hands: "
        f"{r_no.max_damage} -> {r_be.max_damage}"
    )
    # 1.3x boost on attack stat (Iron Hands' highest non-HP stat is Attack)
    assert r_be.max_damage / r_no.max_damage == pytest.approx(1.3, rel=0.05)


def test_engine_auto_applies_quark_drive_in_electric_terrain():
    move = _make_simple_move(category="physical", power=80, move_type="Normal")
    a = _build("iron-hands", IRON_HANDS, ["Fighting", "Electric"], ability="quark-drive",
               evs=EVSpread(attack=252), nature=Nature.ADAMANT)
    d = _build("garchomp", GARCHOMP, ["Dragon", "Ground"], nature=Nature.IMPISH)
    r_off = calculate_damage(a, d, move, DamageModifiers(is_doubles=True))
    r_on = calculate_damage(a, d, move, DamageModifiers(is_doubles=True, terrain="electric"))
    assert r_on.max_damage > r_off.max_damage


def test_engine_auto_applies_intrepid_sword():
    """Zacian-Crowned with Intrepid Sword auto-gets +1 Atk."""
    move = _make_simple_move(category="physical", power=100, move_type="Steel")
    base = BaseStats(hp=92, attack=170, defense=115, special_attack=80,
                     special_defense=115, speed=148)
    a_clear = _build("zacian-crowned", base, ["Fairy", "Steel"],
                     ability="clear-body", evs=EVSpread(attack=252), nature=Nature.JOLLY)
    a_is = _build("zacian-crowned", base, ["Fairy", "Steel"],
                  ability="intrepid-sword", evs=EVSpread(attack=252), nature=Nature.JOLLY)
    d = _build("garchomp", GARCHOMP, ["Dragon", "Ground"], nature=Nature.IMPISH)
    r_clear = calculate_damage(a_clear, d, move, DamageModifiers(is_doubles=True))
    r_is = calculate_damage(a_is, d, move, DamageModifiers(is_doubles=True))
    # +1 stage = 1.5x — should produce ~50% more damage
    assert r_is.max_damage / r_clear.max_damage == pytest.approx(1.5, rel=0.05)


def test_engine_auto_applies_embody_aspect_hearthflame_only_on_tera():
    move = _make_simple_move(category="physical", power=100, move_type="Grass")
    base = BaseStats(hp=80, attack=120, defense=84, special_attack=60,
                     special_defense=96, speed=110)
    a = _build("ogerpon-hearthflame", base, ["Grass", "Fire"],
               ability="embody-aspect-hearthflame", evs=EVSpread(attack=252),
               nature=Nature.JOLLY, tera_type="Fire")
    d = _build("garchomp", GARCHOMP, ["Dragon", "Ground"], nature=Nature.IMPISH)
    r_off = calculate_damage(a, d, move, DamageModifiers(is_doubles=True))
    r_on = calculate_damage(a, d, move, DamageModifiers(is_doubles=True, tera_type="Fire", tera_active=True))
    assert r_on.max_damage > r_off.max_damage
