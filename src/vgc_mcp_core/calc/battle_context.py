"""Adapter: live battle state -> DamageModifiers.

The battle copilot (`BattleStateManager`) tracks everything the damage engine
needs to give turn-accurate KO ranges — weather, terrain, screens, stat stages,
revealed items/abilities, Tera, status, HP — but nothing wired those facts into
`calculate_damage`. This module is that wire: given an active `BattleState` and
an attacker/defender, it produces a `DamageModifiers` reflecting the current
field so `suggest_next_move` (or any coaching tool) can compute real damage
instead of generic estimates.

Pure and synchronous — it only maps state to modifiers; the caller supplies the
`PokemonBuild`s and calls `calculate_damage`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .modifiers import DamageModifiers

if TYPE_CHECKING:
    from ..state.battle_manager import BattleState, FieldState, PokemonBattleState

# Ruin abilities -> the DamageModifiers flag that applies their field effect.
_RUIN_FLAGS = {
    "beads of ruin": "beads_of_ruin",
    "sword of ruin": "sword_of_ruin",
    "tablets of ruin": "tablets_of_ruin",
    "vessel of ruin": "vessel_of_ruin",
}


def _screens_for_side(field: "FieldState", side: str) -> tuple[bool, bool, bool]:
    """(reflect, light_screen, aurora_veil) active on the given side."""
    if side == "me":
        return (
            field.my_reflect_turns > 0,
            field.my_light_screen_turns > 0,
            field.my_aurora_veil_turns > 0,
        )
    return (
        field.opp_reflect_turns > 0,
        field.opp_light_screen_turns > 0,
        field.opp_aurora_veil_turns > 0,
    )


def build_modifiers_from_battle(
    battle: "BattleState",
    attacker: "PokemonBattleState",
    defender: "PokemonBattleState",
    base: Optional[DamageModifiers] = None,
) -> DamageModifiers:
    """Construct DamageModifiers from the live battle state.

    Args:
        battle: the active BattleState (for field conditions).
        attacker / defender: the two PokemonBattleState involved.
        base: optional DamageModifiers to start from (its non-default fields
            are preserved unless the battle state overrides them).

    Returns a DamageModifiers with weather/terrain/screens/stages/items/
    abilities/Tera/status filled from the battle.
    """
    field = battle.field
    mods = base or DamageModifiers()

    # Field-wide conditions.
    mods.weather = field.weather
    mods.terrain = field.terrain

    # Screens protect the DEFENDER's side.
    reflect, light_screen, aurora_veil = _screens_for_side(field, defender.side)
    mods.reflect_up = reflect
    mods.light_screen_up = light_screen
    mods.aurora_veil_up = aurora_veil

    # Offensive stat stages come from the attacker; defensive from the defender.
    mods.attack_stage = attacker.stages.get("attack", 0)
    mods.special_attack_stage = attacker.stages.get("special_attack", 0)
    mods.defense_stage = defender.stages.get("defense", 0)
    mods.special_defense_stage = defender.stages.get("special_defense", 0)
    mods.total_positive_stages = sum(v for v in attacker.stages.values() if v > 0)

    # Revealed items / abilities.
    if attacker.revealed_item:
        mods.attacker_item = attacker.revealed_item
    if defender.revealed_item:
        mods.defender_item = defender.revealed_item
    if attacker.revealed_ability:
        mods.attacker_ability = attacker.revealed_ability
    if defender.revealed_ability:
        mods.defender_ability = defender.revealed_ability

    # Ruin abilities are field effects — set the flag from whichever side reveals
    # the ability (they always apply regardless of who holds them).
    for mon in (attacker, defender):
        ability = (mon.revealed_ability or "").lower()
        flag = _RUIN_FLAGS.get(ability)
        if flag:
            setattr(mods, flag, True)

    # Terastallization.
    if attacker.has_terastallized and attacker.revealed_tera_type:
        mods.tera_active = True
        mods.tera_type = attacker.revealed_tera_type
    if defender.has_terastallized and defender.revealed_tera_type:
        mods.defender_tera_active = True
        mods.defender_tera_type = defender.revealed_tera_type

    # Status: burn cuts physical damage; several variable-BP moves read status.
    mods.attacker_burned = attacker.status == "burn"
    mods.attacker_statused = attacker.status is not None
    mods.defender_statused = defender.status is not None

    # HP-gated defensive abilities (Multiscale / Tera Shell).
    mods.defender_at_full_hp = defender.hp_percent >= 100.0

    return mods
