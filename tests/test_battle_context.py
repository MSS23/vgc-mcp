"""Tests for the battle-state -> DamageModifiers adapter (feature #1 foundation)."""

from vgc_mcp_core.calc.battle_context import build_modifiers_from_battle
from vgc_mcp_core.state.battle_manager import BattleStateManager


def _fresh_battle():
    m = BattleStateManager()
    b = m.start(
        ["incineroar", "flutter-mane", "amoonguss", "urshifu-rapid-strike"],
        ["landorus", "rillaboom", "tornadus", "chi-yu"],
    )
    return b


def test_adapter_maps_field_conditions():
    b = _fresh_battle()
    b.field.weather = "rain"
    b.field.terrain = "electric"
    atk = b.find("me", "urshifu-rapid-strike")
    dfn = b.find("opp", "landorus")

    mods = build_modifiers_from_battle(b, atk, dfn)
    assert mods.weather == "rain"
    assert mods.terrain == "electric"


def test_adapter_maps_screens_to_defender_side():
    b = _fresh_battle()
    b.field.opp_reflect_turns = 4
    b.field.opp_aurora_veil_turns = 0
    atk = b.find("me", "flutter-mane")
    dfn = b.find("opp", "landorus")  # defender on opp side

    mods = build_modifiers_from_battle(b, atk, dfn)
    assert mods.reflect_up is True
    assert mods.aurora_veil_up is False

    # If the defender were on MY side, opp screens must NOT apply.
    my_dfn = b.find("me", "incineroar")
    my_atk = b.find("opp", "chi-yu")
    mods2 = build_modifiers_from_battle(b, my_atk, my_dfn)
    assert mods2.reflect_up is False


def test_adapter_maps_stages_items_status_tera():
    b = _fresh_battle()
    atk = b.find("me", "flutter-mane")
    dfn = b.find("opp", "landorus")
    atk.stages["special_attack"] = 2
    dfn.stages["special_defense"] = -1
    dfn.revealed_item = "assault-vest"
    dfn.revealed_ability = "intimidate"
    dfn.status = "burn"
    dfn.hp_percent = 60.0
    atk.has_terastallized = True
    atk.revealed_tera_type = "Fairy"

    mods = build_modifiers_from_battle(b, atk, dfn)
    assert mods.special_attack_stage == 2
    assert mods.special_defense_stage == -1
    assert mods.defender_item == "assault-vest"
    assert mods.defender_ability == "intimidate"
    assert mods.defender_statused is True
    assert mods.defender_at_full_hp is False
    assert mods.tera_active is True
    assert mods.tera_type == "Fairy"


def test_adapter_sets_ruin_flag_from_revealed_ability():
    b = _fresh_battle()
    atk = b.find("opp", "chi-yu")
    atk.revealed_ability = "Beads of Ruin"
    dfn = b.find("me", "incineroar")

    mods = build_modifiers_from_battle(b, atk, dfn)
    assert mods.beads_of_ruin is True


def test_adapter_produces_usable_modifiers_for_calc():
    """End-to-end: adapter output feeds calculate_damage without error."""
    from vgc_mcp_core.calc.damage import calculate_damage
    from vgc_mcp_core.models.move import Move, MoveCategory
    from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature, PokemonBuild

    b = _fresh_battle()
    b.field.weather = "sun"
    atk_state = b.find("me", "flutter-mane")
    dfn_state = b.find("opp", "landorus")
    atk_state.stages["special_attack"] = 2

    mods = build_modifiers_from_battle(b, atk_state, dfn_state)

    attacker = PokemonBuild(
        name="flutter-mane",
        base_stats=BaseStats(hp=55, attack=55, defense=55,
                             special_attack=135, special_defense=135, speed=135),
        nature=Nature.TIMID, evs=EVSpread(special_attack=252, speed=252),
        types=["Ghost", "Fairy"],
    )
    defender = PokemonBuild(
        name="landorus",
        base_stats=BaseStats(hp=89, attack=125, defense=90,
                             special_attack=115, special_defense=80, speed=101),
        nature=Nature.MODEST, evs=EVSpread(hp=4), types=["Ground", "Flying"],
    )
    move = Move(name="moonblast", type="Fairy", category=MoveCategory.SPECIAL, power=95)

    result = calculate_damage(attacker, defender, move, mods)
    assert result.max_damage > 0
