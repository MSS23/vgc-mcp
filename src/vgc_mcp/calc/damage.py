"""Full Gen 9 VGC damage calculator.

Damage Formula:
Base = floor(floor(floor(floor(2*Level/5+2) * Power * Atk/Def) / 50) + 2)

Then apply modifiers in order (each floors the result):
1. Spread move (0.75x in doubles when hitting multiple targets)
2. Weather
3. Critical hit (1.5x)
4. Random (0.85 to 1.0 in 16 rolls)
5. STAB (1.5x, or 2x with Adaptability, or 2x with same-type Tera)
6. Type effectiveness
7. Burn (0.5x on physical, unless Guts/Facade)
8. Screens (0.5x singles, 0.667x doubles)
9. Item modifiers
10. Ability modifiers
"""

import math
from dataclasses import dataclass
from typing import Optional

from ..models.pokemon import PokemonBuild
from ..models.move import Move, MoveCategory, get_multi_hit_info, GEN9_SPECIAL_MOVES
from ..config import EV_BREAKPOINTS_LV50
from .stats import calculate_all_stats
from .modifiers import (
    DamageModifiers,
    get_type_effectiveness,
    is_super_effective,
)


@dataclass
class DamageResult:
    """Result of damage calculation."""
    min_damage: int
    max_damage: int
    min_percent: float
    max_percent: float
    rolls: list[int]
    defender_hp: int
    ko_chance: str
    is_guaranteed_ohko: bool
    is_possible_ohko: bool
    details: dict

    @property
    def damage_range(self) -> str:
        """Formatted damage range string."""
        return f"{self.min_damage}-{self.max_damage} ({self.min_percent:.1f}%-{self.max_percent:.1f}%)"


def calculate_damage(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move: Move,
    modifiers: Optional[DamageModifiers] = None
) -> DamageResult:
    """
    Calculate damage from one Pokemon to another.

    Args:
        attacker: Attacking Pokemon with full build
        defender: Defending Pokemon with full build
        move: Move being used
        modifiers: Battle conditions and modifiers

    Returns:
        DamageResult with damage range, percentages, and KO probability
    """
    if modifiers is None:
        modifiers = DamageModifiers()

    # Check for multi-hit move mechanics
    multi_hit_info = get_multi_hit_info(move.name)
    hit_count = 1
    always_crit = False
    if multi_hit_info:
        min_hits, max_hits, always_crit = multi_hit_info
        # Use specified hit count from modifiers, or default to max hits for calc
        if modifiers.move_hits > 0:
            hit_count = modifiers.move_hits
        else:
            hit_count = max_hits  # Show max damage potential by default
        # Surging Strikes always crits
        if always_crit:
            modifiers.is_critical = True

    # Non-damaging moves
    if not move.is_damaging:
        return DamageResult(
            min_damage=0,
            max_damage=0,
            min_percent=0,
            max_percent=0,
            rolls=[0] * 16,
            defender_hp=1,
            ko_chance="N/A (Status move)",
            is_guaranteed_ohko=False,
            is_possible_ohko=False,
            details={"reason": "Status move"}
        )

    # Calculate stats
    attacker_stats = calculate_all_stats(attacker)
    defender_stats = calculate_all_stats(defender)

    # Determine attacking and defending stats
    if move.category == MoveCategory.PHYSICAL:
        attack_stat_name = "attack"
        defense_stat_name = "defense"
    else:
        attack_stat_name = "special_attack"
        defense_stat_name = "special_defense"

    attack_stat = attacker_stats[attack_stat_name]
    defense_stat = defender_stats[defense_stat_name]

    # Apply stat stage modifiers
    if move.category == MoveCategory.PHYSICAL:
        attack_stat = int(attack_stat * modifiers.get_stat_stage_multiplier(modifiers.attack_stage))
        if not modifiers.is_critical:  # Crits ignore positive defense stages
            if modifiers.defense_stage > 0:
                defense_stat = int(defense_stat * modifiers.get_stat_stage_multiplier(modifiers.defense_stage))
            else:
                defense_stat = int(defense_stat * modifiers.get_stat_stage_multiplier(modifiers.defense_stage))
    else:
        attack_stat = int(attack_stat * modifiers.get_stat_stage_multiplier(modifiers.special_attack_stage))
        if not modifiers.is_critical:
            if modifiers.special_defense_stage > 0:
                defense_stat = int(defense_stat * modifiers.get_stat_stage_multiplier(modifiers.special_defense_stage))
            else:
                defense_stat = int(defense_stat * modifiers.get_stat_stage_multiplier(modifiers.special_defense_stage))

    # Apply Choice Band/Specs (to stat, not damage)
    if modifiers.attacker_item:
        item = modifiers.attacker_item.lower().replace(" ", "-")
        if item == "choice-band" and move.category == MoveCategory.PHYSICAL:
            attack_stat = int(attack_stat * 1.5)
        elif item == "choice-specs" and move.category == MoveCategory.SPECIAL:
            attack_stat = int(attack_stat * 1.5)

    # Apply stat-doubling abilities
    if modifiers.attacker_ability:
        ability = modifiers.attacker_ability.lower().replace(" ", "-")
        # Huge Power / Pure Power double Attack stat
        if ability in ("huge-power", "pure-power") and move.category == MoveCategory.PHYSICAL:
            attack_stat = int(attack_stat * 2)

    # Commander ability (Dondozo + Tatsugiri combo)
    # When Commander is active, Dondozo's Attack, Defense, SpA, SpD, and Speed are doubled
    # For offensive calcs: doubles Dondozo's attacking stat (Attack or SpA)
    # For defensive calcs: doubles Dondozo's defensive stat (Defense or SpD)
    commander_boost_applied = False
    if modifiers.commander_active:
        attack_stat = int(attack_stat * 2)
        commander_boost_applied = True

    # Defender has Commander active - doubles their defensive stat
    if modifiers.defender_commander_active:
        defense_stat = int(defense_stat * 2)

    # Apply Ruin abilities
    # Sword of Ruin (Chien-Pao): Lowers foe Defense to 0.75x
    if modifiers.sword_of_ruin and move.category == MoveCategory.PHYSICAL:
        defense_stat = int(defense_stat * 0.75)

    # Beads of Ruin (Chi-Yu): Lowers foe Special Defense to 0.75x
    if modifiers.beads_of_ruin and move.category == MoveCategory.SPECIAL:
        defense_stat = int(defense_stat * 0.75)

    # Tablets of Ruin (Wo-Chien): Lowers foe Attack to 0.75x
    if modifiers.tablets_of_ruin and move.category == MoveCategory.PHYSICAL:
        attack_stat = int(attack_stat * 0.75)

    # Vessel of Ruin (Ting-Lu): Lowers foe Special Attack to 0.75x
    if modifiers.vessel_of_ruin and move.category == MoveCategory.SPECIAL:
        attack_stat = int(attack_stat * 0.75)

    # Apply Protosynthesis/Quark Drive boosts (1.3x, or 1.5x for Speed)
    # These boost the attacker's relevant stat if it matches the boosted stat
    for boost_stat in [modifiers.protosynthesis_boost, modifiers.quark_drive_boost]:
        if boost_stat:
            boost_multiplier = 1.5 if boost_stat == "speed" else 1.3
            if boost_stat == "attack" and move.category == MoveCategory.PHYSICAL:
                attack_stat = int(attack_stat * boost_multiplier)
            elif boost_stat == "special_attack" and move.category == MoveCategory.SPECIAL:
                attack_stat = int(attack_stat * boost_multiplier)

    # Apply defender's Protosynthesis/Quark Drive boosts
    for boost_stat in [modifiers.defender_protosynthesis_boost, modifiers.defender_quark_drive_boost]:
        if boost_stat:
            boost_multiplier = 1.5 if boost_stat == "speed" else 1.3
            if boost_stat == "defense" and move.category == MoveCategory.PHYSICAL:
                defense_stat = int(defense_stat * boost_multiplier)
            elif boost_stat == "special_defense" and move.category == MoveCategory.SPECIAL:
                defense_stat = int(defense_stat * boost_multiplier)

    # Get base power
    power = move.power

    # Apply power modifiers from abilities (Technician, etc.)
    if modifiers.attacker_ability:
        ability = modifiers.attacker_ability.lower().replace(" ", "-")
        if ability == "technician" and power <= 60:
            power = int(power * 1.5)
        elif ability == "sheer-force" and move.effect_chance:
            power = int(power * 1.3)

    # Level constant for level 50: floor(2*50/5+2) = 22
    level_factor = 22

    # Base damage formula
    # floor(floor(floor(level_factor * power * atk / def) / 50) + 2)
    base_damage = math.floor(
        math.floor(
            math.floor(level_factor * power * attack_stat / defense_stat) / 50
        ) + 2
    )

    # Track applied modifiers for details
    applied_mods = []

    # 1. Spread move modifier (0.75x in doubles when hitting multiple)
    if move.is_spread and modifiers.is_doubles and modifiers.multiple_targets:
        base_damage = int(base_damage * 0.75)
        applied_mods.append("Spread (0.75x)")

    # 2. Weather modifier
    weather_mod = modifiers.get_weather_modifier(move.type)
    if weather_mod != 1.0:
        base_damage = int(base_damage * weather_mod)
        applied_mods.append(f"Weather ({weather_mod}x)")

    # 2.5. Terrain modifier (applied after weather, before crit)
    terrain_mod = modifiers.get_terrain_modifier(move.type, move.category == MoveCategory.PHYSICAL)
    if terrain_mod != 1.0:
        base_damage = int(base_damage * terrain_mod)
        terrain_name = modifiers.terrain.capitalize() if modifiers.terrain else "Terrain"
        applied_mods.append(f"{terrain_name} Terrain ({terrain_mod}x)")

    # 3. Critical hit (1.5x in Gen 9)
    if modifiers.is_critical:
        base_damage = int(base_damage * 1.5)
        applied_mods.append("Critical (1.5x)")

    # Calculate 16 damage rolls (random factor 0.85 to 1.0)
    rolls = []
    for i in range(16):
        random_factor = (85 + i) / 100
        damage = int(base_damage * random_factor)

        # 5. STAB (after random)
        stab_mod = _get_stab_modifier(attacker, move, modifiers)
        if stab_mod != 1.0:
            damage = int(damage * stab_mod)

        # 6. Type effectiveness
        defender_types = defender.types
        if modifiers.defender_tera_active and modifiers.defender_tera_type:
            defender_types = [modifiers.defender_tera_type]

        type_eff = get_type_effectiveness(move.type, defender_types)
        if type_eff != 1.0:
            damage = int(damage * type_eff)

        # 7. Burn (0.5x on physical unless Guts/Facade)
        if modifiers.attacker_burned and move.category == MoveCategory.PHYSICAL:
            if not modifiers.has_guts and move.name.lower() != "facade":
                damage = int(damage * 0.5)

        # 8. Screens
        screen_mod = modifiers.get_screen_modifier(move.category == MoveCategory.PHYSICAL)
        if screen_mod != 1.0:
            damage = int(damage * screen_mod)

        # 9. Item modifiers (Life Orb, type-boosting items)
        item_mod = modifiers.get_item_modifier(move.type, move.category == MoveCategory.PHYSICAL)
        if item_mod != 1.0:
            damage = int(damage * item_mod)

        # Expert Belt (only if super effective)
        if modifiers.attacker_item and modifiers.attacker_item.lower().replace(" ", "-") == "expert-belt":
            if type_eff >= 2.0:
                damage = int(damage * 1.2)

        # 10. Helping Hand (1.5x)
        if modifiers.helping_hand:
            damage = int(damage * 1.5)

        # Friend Guard (0.75x damage to ally)
        if modifiers.friend_guard:
            damage = int(damage * 0.75)

        # Minimum 1 damage per hit
        damage = max(1, damage)

        # Apply multi-hit multiplier (damage per hit * number of hits)
        if hit_count > 1:
            damage = damage * hit_count

        rolls.append(damage)

    # Calculate results
    min_damage = min(rolls)
    max_damage = max(rolls)
    defender_hp = defender_stats["hp"]

    # Truncate to 1 decimal place (matching Showdown's behavior)
    # e.g., 98.49% becomes 98.4%, not 98.5%
    min_percent = int((min_damage / defender_hp) * 1000) / 10
    max_percent = int((max_damage / defender_hp) * 1000) / 10

    # KO calculations
    kos = sum(1 for r in rolls if r >= defender_hp)
    is_guaranteed_ohko = kos == 16
    is_possible_ohko = kos > 0

    if is_guaranteed_ohko:
        ko_chance = "Guaranteed OHKO"
    elif kos == 0:
        ko_chance = f"0% OHKO ({max_percent:.1f}% max)"
    else:
        ko_chance = f"{(kos/16)*100:.1f}% OHKO"

    # Add STAB to applied mods
    stab_mod = _get_stab_modifier(attacker, move, modifiers)
    if stab_mod != 1.0:
        if stab_mod == 2.0:
            applied_mods.append("STAB (2.0x - Tera/Adaptability)")
        else:
            applied_mods.append("STAB (1.5x)")

    # Add type effectiveness to mods
    type_eff = get_type_effectiveness(move.type, defender_types)
    if type_eff == 0:
        applied_mods.append("Immune (0x)")
    elif type_eff == 0.25:
        applied_mods.append("4x Resist (0.25x)")
    elif type_eff == 0.5:
        applied_mods.append("Resist (0.5x)")
    elif type_eff == 2:
        applied_mods.append("Super Effective (2x)")
    elif type_eff == 4:
        applied_mods.append("4x Super Effective (4x)")

    # Add multi-hit info to mods
    if hit_count > 1:
        crit_note = " (always crits)" if always_crit else ""
        applied_mods.append(f"Multi-hit ({hit_count} hits{crit_note})")

    # Add Commander to mods
    if commander_boost_applied:
        applied_mods.append("Commander (2x all stats)")

    return DamageResult(
        min_damage=min_damage,
        max_damage=max_damage,
        min_percent=min_percent,
        max_percent=max_percent,
        rolls=rolls,
        defender_hp=defender_hp,
        ko_chance=ko_chance,
        is_guaranteed_ohko=is_guaranteed_ohko,
        is_possible_ohko=is_possible_ohko,
        details={
            "attacker_stat": attack_stat,
            "defender_stat": defense_stat,
            "base_power": power,
            "type_effectiveness": type_eff,
            "modifiers_applied": applied_mods,
            "hit_count": hit_count,
            "always_crit": always_crit,
        }
    )


def _get_stab_modifier(
    attacker: PokemonBuild,
    move: Move,
    modifiers: DamageModifiers
) -> float:
    """Calculate STAB modifier including Tera considerations."""
    move_type = move.type.capitalize()
    original_types = [t.capitalize() for t in attacker.types]

    tera_type = None
    if modifiers.tera_active and modifiers.tera_type:
        tera_type = modifiers.tera_type.capitalize()

    # Check if move type matches Tera type
    if tera_type:
        if move_type == tera_type:
            if move_type in original_types:
                # Tera into same type = 2x STAB
                return 2.0
            else:
                # Tera into new type = 1.5x
                return 1.5
        elif move_type in original_types:
            # Original type moves still get 1.5x STAB when Terastallized
            return 1.5
    else:
        # Not Terastallized
        if move_type in original_types:
            if modifiers.has_adaptability:
                return 2.0
            return 1.5

    return 1.0


def calculate_ko_threshold(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move: Move,
    modifiers: Optional[DamageModifiers] = None,
    target_ko_chance: float = 100.0
) -> Optional[dict]:
    """
    Find minimum EVs needed to achieve a certain KO probability.

    Args:
        attacker: Attacker base build (EVs will be varied)
        defender: Defender build
        move: Move being used
        modifiers: Battle conditions
        target_ko_chance: Target KO probability (100 = guaranteed)

    Returns:
        Dict with required EVs and resulting calc, or None if impossible
    """
    from ..models.pokemon import EVSpread

    is_physical = move.category == MoveCategory.PHYSICAL
    stat_name = "attack" if is_physical else "special_attack"

    # Use valid level 50 EV breakpoints (0, 4, 12, 20, 28...)
    for ev in EV_BREAKPOINTS_LV50:
        # Create modified attacker with test EVs
        test_evs = EVSpread()
        if is_physical:
            test_evs.attack = ev
        else:
            test_evs.special_attack = ev

        test_attacker = attacker.model_copy()
        test_attacker.evs = test_evs

        result = calculate_damage(test_attacker, defender, move, modifiers)

        # Calculate actual KO chance from rolls
        kos = sum(1 for r in result.rolls if r >= result.defender_hp)
        ko_pct = (kos / 16) * 100

        if ko_pct >= target_ko_chance:
            return {
                "evs_needed": ev,
                "stat_name": stat_name,
                "ko_chance": ko_pct,
                "damage_range": result.damage_range,
                "result": result
            }

    return None  # Cannot achieve target KO


def calculate_bulk_threshold(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move: Move,
    modifiers: Optional[DamageModifiers] = None,
    target_survival_chance: float = 100.0
) -> Optional[dict]:
    """
    Find minimum bulk EVs to survive an attack.

    Args:
        attacker: Attacker build
        defender: Defender base build (EVs will be varied)
        move: Move being used
        modifiers: Battle conditions
        target_survival_chance: Target survival % (100 = guaranteed survive)

    Returns:
        Dict with required HP/Def EVs and resulting calc
    """
    from ..models.pokemon import EVSpread

    is_physical = move.category == MoveCategory.PHYSICAL
    def_stat_name = "defense" if is_physical else "special_defense"

    # Try HP investment first, then defensive stat (level 50 breakpoints)
    for hp_ev in EV_BREAKPOINTS_LV50:
        for def_ev in EV_BREAKPOINTS_LV50:
            if hp_ev + def_ev > 508:
                continue

            test_evs = EVSpread(hp=hp_ev)
            if is_physical:
                test_evs.defense = def_ev
            else:
                test_evs.special_defense = def_ev

            test_defender = defender.model_copy()
            test_defender.evs = test_evs

            result = calculate_damage(attacker, test_defender, move, modifiers)

            # Calculate survival chance
            survives = sum(1 for r in result.rolls if r < result.defender_hp)
            survival_pct = (survives / 16) * 100

            if survival_pct >= target_survival_chance:
                return {
                    "hp_evs": hp_ev,
                    "def_evs": def_ev,
                    "def_stat_name": def_stat_name,
                    "survival_chance": survival_pct,
                    "damage_range": result.damage_range,
                    "result": result
                }

    return None  # Cannot achieve target survival
