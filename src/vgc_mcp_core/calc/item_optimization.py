"""Item optimization calculations for VGC.

This module provides core logic for comparing items (Life Orb vs Choice items)
and analyzing EV-item trade-offs for competitive optimization.
"""

from typing import Optional
from dataclasses import dataclass, replace

from ..calc.items import calculate_life_orb_effect, get_item_damage_modifier
from ..calc.damage import calculate_damage, DamageResult
from ..models.pokemon import PokemonBuild, BaseStats, Nature, EVSpread
from ..models.move import Move, MoveCategory
from ..calc.modifiers import DamageModifiers


@dataclass
class ItemComparisonResult:
    """Result of comparing multiple items."""
    item: str
    damage_range: str
    damage_percent: str
    recoil_per_attack: int
    recoil_percent: float
    turns_sustainable: int
    recommendation: str
    notes: list[str]


@dataclass
class SustainabilityAnalysis:
    """Analysis of Life Orb sustainability."""
    hp_evs: int
    max_hp: int
    attacks_before_faint: int
    net_hp_after_attacks: dict[int, int]  # turn -> hp remaining
    recommendation: str


@dataclass
class EVTradeoffResult:
    """Result of EV-item trade-off analysis."""
    item: str
    evs: dict[str, int]
    evs_saved: int
    total_useful_stats: int
    final_stats: dict[str, int]
    rank: int
    showdown_paste: str


def compare_items_damage(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move: Move,
    items: list[str],
    modifiers: DamageModifiers,
    has_sheer_force: bool = False
) -> list[ItemComparisonResult]:
    """
    Compare damage output across multiple items.

    Args:
        attacker: Attacker Pokemon build
        defender: Defender Pokemon build
        move: Move being used
        items: List of items to compare
        modifiers: Damage modifiers (weather, terrain, etc.)
        has_sheer_force: True if attacker has Sheer Force (negates Life Orb recoil)

    Returns:
        List of comparison results for each item
    """
    results = []
    base_modifiers = modifiers

    for item in items:
        # Create modified attacker with this item
        attacker_dict = attacker.model_dump()
        attacker_dict["item"] = item
        attacker_with_item = PokemonBuild(**attacker_dict)

        # Update modifiers with item (use dataclasses.replace for cleaner code)
        item_modifiers = replace(base_modifiers, attacker_item=item)

        # Calculate damage
        damage_result = calculate_damage(attacker_with_item, defender, move, item_modifiers)

        # Calculate recoil (if Life Orb)
        recoil = 0
        recoil_percent = 0.0
        if item == "life-orb":
            from ..calc.stats import calculate_hp
            # Use calculated HP, not base HP
            max_hp = calculate_hp(
                attacker.base_stats.hp,
                attacker.ivs.hp,
                attacker.evs.hp,
                attacker.level
            )
            life_orb_data = calculate_life_orb_effect(damage_result.max_damage, max_hp)
            recoil = life_orb_data["recoil"]
            recoil_percent = life_orb_data["recoil_percent"]
            
            # Sheer Force negates recoil
            if has_sheer_force:
                recoil = 0
                recoil_percent = 0.0

        # Calculate sustainability (how many attacks before fainting)
        if recoil > 0:
            from ..calc.stats import calculate_hp
            max_hp_calc = calculate_hp(
                attacker.base_stats.hp,
                attacker.ivs.hp,
                attacker.evs.hp,
                attacker.level
            )
            turns_sustainable = (max_hp_calc // recoil) if recoil > 0 else 999
        else:
            turns_sustainable = 999

        # Generate recommendation
        recommendation = ""
        notes = []
        
        if item == "life-orb" and has_sheer_force:
            recommendation = "BEST - Sheer Force negates recoil"
            notes.append("Life Orb + Sheer Force = no recoil, 1.3x damage")
        elif item == "life-orb":
            recommendation = f"Good damage but {recoil_percent}% recoil per attack"
            notes.append(f"Sustainable for ~{turns_sustainable} attacks")
        elif item in ["choice-band", "choice-specs"]:
            recommendation = "Locked to move after use"
            notes.append("Switching out allows choosing different move")
        elif item == "expert-belt":
            recommendation = "Only 1.2x on super effective moves"
            notes.append("No boost on neutral/not very effective moves")

        results.append(ItemComparisonResult(
            item=item,
            damage_range=f"{damage_result.min_damage}-{damage_result.max_damage}",
            damage_percent=f"{damage_result.min_percent:.1f}-{damage_result.max_percent:.1f}%",
            recoil_per_attack=recoil,
            recoil_percent=recoil_percent,
            turns_sustainable=turns_sustainable,
            recommendation=recommendation,
            notes=notes
        ))

    return results


def analyze_life_orb_sustainability(
    pokemon: PokemonBuild,
    hp_evs: int,
    recovery_sources: list[str],
    moves_per_game: int = 4
) -> SustainabilityAnalysis:
    """
    Analyze Life Orb sustainability with different HP investments.

    Args:
        pokemon: Pokemon build to analyze
        hp_evs: HP EVs to test
        recovery_sources: List like ["grassy-terrain", "leftovers"]
        moves_per_game: Expected number of attacks before fainting

    Returns:
        Sustainability analysis
    """
    from ..calc.stats import calculate_hp

    # Calculate max HP with these EVs
    max_hp = calculate_hp(pokemon.base_stats.hp, pokemon.ivs.hp, hp_evs, pokemon.level)

    # Life Orb recoil: 10% max HP per attack
    recoil_per_attack = max_hp // 10

    # Calculate recovery per turn
    recovery_per_turn = 0
    if "leftovers" in recovery_sources:
        recovery_per_turn += max_hp // 16  # 6.25% per turn
    if "grassy-terrain" in recovery_sources:
        recovery_per_turn += max_hp // 16  # 6.25% per turn

    # Simulate attacks
    current_hp = max_hp
    attacks_before_faint = 0
    net_hp_after_attacks = {}

    for turn in range(1, 21):  # Max 20 turns
        # Take recoil
        current_hp -= recoil_per_attack
        
        # Apply recovery
        current_hp += recovery_per_turn
        current_hp = min(max_hp, current_hp)  # Cap at max HP

        net_hp_after_attacks[turn] = current_hp

        if current_hp <= 0:
            attacks_before_faint = turn
            break

    if attacks_before_faint == 0:
        attacks_before_faint = 999  # Never faints

    # Generate recommendation
    if hp_evs == 0:
        recommendation = f"0 HP EVs: {attacks_before_faint} attacks sustainable"
    elif hp_evs == 252:
        recommendation = f"252 HP EVs: {attacks_before_faint} attacks sustainable"
    else:
        recommendation = f"{hp_evs} HP EVs: {attacks_before_faint} attacks sustainable"

    return SustainabilityAnalysis(
        hp_evs=hp_evs,
        max_hp=max_hp,
        attacks_before_faint=attacks_before_faint,
        net_hp_after_attacks=net_hp_after_attacks,
        recommendation=recommendation
    )


def calculate_ev_tradeoff(
    pokemon: PokemonBuild,
    target_benchmark: dict,
    items_to_test: list[str],
    offensive_stat: str = "auto"
) -> list[EVTradeoffResult]:
    """
    Find optimal item + EV distribution to maximize stats.

    Args:
        pokemon: Base Pokemon build
        target_benchmark: Dict with benchmark requirements
        items_to_test: List of items to compare
        offensive_stat: "attack", "special-attack", or "auto"

    Returns:
        List of trade-off results sorted by total useful stats
    """
    from ..calc.stats import calculate_all_stats

    results = []

    # Determine offensive stat
    if offensive_stat == "auto":
        if pokemon.base_stats.attack > pokemon.base_stats.special_attack:
            offensive_stat = "attack"
        else:
            offensive_stat = "special_attack"

    for item in items_to_test:
        # Calculate required EVs for this item to meet benchmark
        # This is simplified - actual implementation would calculate based on benchmark
        
        # For now, use example calculation
        if item in ["choice-band", "choice-specs"]:
            # Choice items give 1.5x stat boost, so need fewer EVs
            evs = {"attack": 164 if offensive_stat == "attack" else 0,
                   "special_attack": 164 if offensive_stat == "special_attack" else 0,
                   "speed": 252,
                   "hp": 0,
                   "defense": 88,
                   "special_defense": 0}
            evs_saved = 88
        elif item == "life-orb":
            # Life Orb gives 1.3x damage but no stat boost, need full EVs
            evs = {"attack": 252 if offensive_stat == "attack" else 0,
                   "special_attack": 252 if offensive_stat == "special_attack" else 0,
                   "speed": 252,
                   "hp": 0,
                   "defense": 0,
                   "special_defense": 0}
            evs_saved = 0
        else:
            evs = {"attack": 252 if offensive_stat == "attack" else 0,
                   "special_attack": 252 if offensive_stat == "special_attack" else 0,
                   "speed": 252,
                   "hp": 0,
                   "defense": 0,
                   "special_defense": 0}
            evs_saved = 0

        # Create Pokemon with this item and EVs
        pokemon_dict = pokemon.model_dump()
        pokemon_dict["item"] = item
        pokemon_dict["evs"] = EVSpread(**evs)
        test_pokemon = PokemonBuild(**pokemon_dict)

        # Calculate final stats
        final_stats = calculate_all_stats(test_pokemon)

        # Calculate total useful stats (offensive + speed + HP/2)
        total_useful = (
            final_stats.get(offensive_stat, 0) +
            final_stats.get("speed", 0) +
            final_stats.get("hp", 0) // 2
        )

        # Generate Showdown paste using proper formatter
        from ..formats.showdown import pokemon_build_to_showdown
        showdown_paste = pokemon_build_to_showdown(test_pokemon)

        results.append(EVTradeoffResult(
            item=item,
            evs=evs,
            evs_saved=evs_saved,
            total_useful_stats=total_useful,
            final_stats=final_stats,
            rank=0,  # Will be set after sorting
            showdown_paste=showdown_paste
        ))

    # Sort by total useful stats (descending)
    results.sort(key=lambda x: x.total_useful_stats, reverse=True)
    
    # Assign ranks
    for i, result in enumerate(results):
        result.rank = i + 1

    return results
