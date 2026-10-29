"""Tests for DamageModifiers.from_scenario, the shared tool-layer modifier factory."""

from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature
from vgc_mcp_core.tools.build_helpers import build_pokemon

CHIEN_PAO = BaseStats(hp=80, attack=120, defense=80, special_attack=90, special_defense=65, speed=135)
INCINEROAR = BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60)
ICICLE_CRASH = Move(name="icicle-crash", type="Ice", category=MoveCategory.PHYSICAL,
                    power=85, accuracy=90, pp=10, target="selected-pokemon")


def _attacker(ability):
    return build_pokemon("chien-pao", CHIEN_PAO, ["Dark", "Ice"], nature=Nature.JOLLY,
                         spread=EVSpread(attack=252, speed=252), item="focus-sash", ability=ability)


def _defender():
    return build_pokemon("incineroar", INCINEROAR, ["Fire", "Dark"], nature=Nature.CAREFUL,
                         spread=EVSpread(hp=252, defense=4), ability="blaze")


def test_defaults_match_plain_constructor():
    assert DamageModifiers.from_scenario() == DamageModifiers()


def test_builds_supply_item_and_abilities_unless_overridden():
    mods = DamageModifiers.from_scenario(_attacker("sword-of-ruin"), _defender())
    assert (mods.attacker_item, mods.attacker_ability, mods.defender_ability) == (
        "focus-sash", "sword-of-ruin", "blaze")
    assert mods.defender_item is None  # left for calculate_damage to fill
    mods = DamageModifiers.from_scenario(_attacker("sword-of-ruin"), attacker_ability="inner-focus")
    assert mods.attacker_ability == "inner-focus"


def test_intimidate_only_applies_to_physical_and_stacks_on_explicit_stage():
    assert DamageModifiers.from_scenario(intimidate_stage=-1).attack_stage == -1
    assert DamageModifiers.from_scenario(intimidate_stage=-1, is_physical=False).attack_stage == 0
    assert DamageModifiers.from_scenario(intimidate_stage=-1, attack_stage=2).attack_stage == 1


def test_tera_active_follows_tera_type_unless_given():
    mods = DamageModifiers.from_scenario(tera_type="Ice", defender_tera_type="Water")
    assert mods.tera_active and mods.defender_tera_active
    assert not DamageModifiers.from_scenario(tera_type="Ice", tera_active=False).tera_active
    assert not DamageModifiers.from_scenario().tera_active


def test_sword_of_ruin_still_applies_on_critical_hits():
    defender = _defender()
    ruin = calculate_damage(_attacker("sword-of-ruin"), defender, ICICLE_CRASH,
                            DamageModifiers.from_scenario(_attacker("sword-of-ruin"), defender, is_critical=True))
    plain = calculate_damage(_attacker("inner-focus"), defender, ICICLE_CRASH,
                             DamageModifiers.from_scenario(_attacker("inner-focus"), defender, is_critical=True))
    assert ruin.max_damage > plain.max_damage
