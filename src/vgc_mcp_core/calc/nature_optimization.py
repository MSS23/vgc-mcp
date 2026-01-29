"""Intelligent nature selection for benchmark-based EV spreads.

This module provides algorithms to automatically select optimal natures
when designing EV spreads with specific benchmarks (speed targets, survival requirements).

The core insight: Nature boosts should be applied to stats that need them most,
not blindly to the highest base stat. For example, Entei (base 115 Atk, 100 Spe)
should use Adamant (+Atk) when hitting a speed benchmark, not Timid (+Spe),
because the Attack boost saves more EVs than the Speed boost would.
"""

from typing import Optional
from dataclasses import dataclass
from pydantic import BaseModel

from ..models.pokemon import Nature, BaseStats, get_nature_modifier
from .stats import calculate_stat, calculate_speed, find_speed_evs
from ..config import EV_BREAKPOINTS_LV50


class NatureOptimizationResult(BaseModel):
    """Result of nature optimization analysis."""
    best_nature: Nature
    evs: dict[str, int]
    final_stats: dict[str, int]
    ev_savings: int  # EVs saved vs neutral nature
    reasoning: str
    score: float  # Optimization score (higher is better)


def get_relevant_natures(
    is_physical: bool = False,
    is_special: bool = False,
    role: str = "offensive"
) -> list[Nature]:
    """
    Get list of relevant natures to test (5-10 candidates instead of all 25).

    Filters natures based on:
    - Attack type (physical vs special)
    - Role (offensive, defensive, mixed)

    Args:
        is_physical: True if Pokemon is primarily physical attacker
        is_special: True if Pokemon is primarily special attacker
        role: "offensive", "defensive", or "mixed"

    Returns:
        List of Nature enums to test
    """
    candidates = []

    if role == "defensive":
        # Defensive builds: prefer +Def/+SpD natures
        candidates = [
            Nature.BOLD,      # +Def/-Atk
            Nature.IMPISH,    # +Def/-SpA
            Nature.CALM,      # +SpD/-Atk
            Nature.CAREFUL,   # +SpD/-SpA
            Nature.SERIOUS,   # Neutral
        ]
    elif is_physical:
        # Physical attackers: prefer +Atk, avoid -Atk
        candidates = [
            Nature.ADAMANT,   # +Atk/-SpA (best for physical)
            Nature.JOLLY,      # +Spe/-SpA (good for speed benchmarks)
            Nature.BRAVE,     # +Atk/-Spe (for Trick Room)
            Nature.LONELY,    # +Atk/-Def (if Def not needed)
            Nature.NAUGHTY,   # +Atk/-SpD (if SpD not needed)
            Nature.SERIOUS,   # Neutral
        ]
    elif is_special:
        # Special attackers: prefer +SpA, avoid -SpA
        candidates = [
            Nature.MODEST,    # +SpA/-Atk (best for special)
            Nature.TIMID,     # +Spe/-Atk (good for speed benchmarks)
            Nature.QUIET,      # +SpA/-Spe (for Trick Room)
            Nature.MILD,      # +SpA/-Def (if Def not needed)
            Nature.RASH,      # +SpA/-SpD (if SpD not needed)
            Nature.SERIOUS,   # Neutral
        ]
    else:
        # Mixed or unknown: test common offensive natures
        candidates = [
            Nature.ADAMANT,   # +Atk/-SpA
            Nature.MODEST,    # +SpA/-Atk
            Nature.JOLLY,     # +Spe/-SpA
            Nature.TIMID,     # +Spe/-Atk
            Nature.SERIOUS,   # Neutral
        ]

    return candidates


def calculate_evs_for_benchmarks(
    base_stats: BaseStats,
    nature: Nature,
    benchmarks: dict,
    level: int = 50
) -> Optional[dict[str, int]]:
    """
    Calculate minimum EVs needed to meet all benchmarks with given nature.

    Args:
        base_stats: Pokemon base stats
        nature: Nature to test
        benchmarks: Dict with keys:
            - speed_target: Optional[int] - Target speed stat
            - survive_pokemon: Optional[str] - Attacker to survive (not used here, handled elsewhere)
            - survive_move: Optional[str] - Move to survive (not used here)
            - prioritize: str - "bulk", "offense", or "attack"/"special_attack"
            - offensive_evs: Optional[int] - Target offensive EVs if prioritize="offense"
            - hp_evs: Optional[int] - Target HP EVs
        level: Pokemon level (default 50)

    Returns:
        Dict with EV allocations, or None if benchmarks are impossible
    """
    evs = {
        "hp": 0,
        "attack": 0,
        "defense": 0,
        "special_attack": 0,
        "special_defense": 0,
        "speed": 0
    }

    # 1. Speed benchmark (if specified)
    if benchmarks.get("speed_target"):
        target_speed = benchmarks["speed_target"]
        speed_mod = get_nature_modifier(nature, "speed")
        
        # Find minimum Speed EVs needed
        speed_evs = None
        for ev in EV_BREAKPOINTS_LV50:
            calculated_speed = calculate_stat(
                base_stats.speed, 31, ev, level, speed_mod
            )
            if calculated_speed >= target_speed:
                speed_evs = ev
                break
        
        if speed_evs is None:
            # Cannot reach speed target even with 252 EVs
            return None
        
        evs["speed"] = speed_evs

    # 2. HP benchmark (if specified)
    if benchmarks.get("hp_evs") is not None:
        evs["hp"] = benchmarks["hp_evs"]

    # 3. Offensive EVs (if prioritize="offense")
    if benchmarks.get("prioritize") == "offense" and benchmarks.get("offensive_evs"):
        offensive_evs = benchmarks["offensive_evs"]
        if benchmarks.get("prioritize") == "attack" or (
            base_stats.attack > base_stats.special_attack
        ):
            evs["attack"] = offensive_evs
        else:
            evs["special_attack"] = offensive_evs

    # 4. Distribute remaining EVs based on prioritize
    total_used = sum(evs.values())
    remaining = 508 - total_used

    if remaining < 0:
        # Impossible: benchmarks exceed 508 EVs
        return None

    # If prioritize="bulk" and we have remaining EVs, distribute to bulk
    if benchmarks.get("prioritize") == "bulk" and remaining > 0:
        # Distribute evenly between Def and SpD, ensuring neither exceeds 252
        max_def_add = 252 - evs["defense"]
        max_spd_add = 252 - evs["special_defense"]
        
        # Try to distribute evenly
        def_evs = min(remaining // 2, max_def_add)
        spd_evs = min(remaining - def_evs, max_spd_add)
        
        # If we couldn't add all to SpD, add remainder to Def (if possible)
        if spd_evs < remaining - def_evs and def_evs < max_def_add:
            remaining_after_spd = remaining - def_evs - spd_evs
            def_evs = min(def_evs + remaining_after_spd, max_def_add)
        
        evs["defense"] += def_evs
        evs["special_defense"] += spd_evs
        
        # If still have remaining EVs, add to HP
        total_used = sum(evs.values())
        remaining_after_bulk = 508 - total_used
        if remaining_after_bulk > 0:
            max_hp_add = 252 - evs["hp"]
            hp_evs = min(remaining_after_bulk, max_hp_add)
            evs["hp"] += hp_evs

    return evs


def calculate_nature_score(
    nature: Nature,
    final_stats: dict[str, int],
    is_physical: bool,
    is_special: bool,
    total_evs: int,
    role: str = "offensive"
) -> float:
    """
    Score a nature based on useful stats gained and EV efficiency.

    Scoring formula:
    - Physical attacker: Attack + Speed + HP/2 - EVs_Used/100
    - Special attacker: SpA + Speed + HP/2 - EVs_Used/100
    - Defensive: HP/2 + Defense + SpDefense + min(Atk, SpA) - EVs_Used/100

    The EV penalty ensures we prefer natures that actually save EVs,
    not just blindly boost the highest base stat.

    Args:
        nature: Nature being scored
        final_stats: Dict of final stat values
        is_physical: True if physical attacker
        is_special: True if special attacker
        total_evs: Total EVs used
        role: "offensive" or "defensive"

    Returns:
        Score (higher is better)
    """
    if role == "defensive":
        # Defensive scoring: prioritize bulk
        score = (
            final_stats.get("hp", 0) / 2 +
            final_stats.get("defense", 0) +
            final_stats.get("special_defense", 0) +
            min(final_stats.get("attack", 0), final_stats.get("special_attack", 0))
        )
    elif is_physical:
        # Physical attacker: prioritize Attack + Speed
        score = (
            final_stats.get("attack", 0) +
            final_stats.get("speed", 0) +
            final_stats.get("hp", 0) / 2
        )
    elif is_special:
        # Special attacker: prioritize SpA + Speed
        score = (
            final_stats.get("special_attack", 0) +
            final_stats.get("speed", 0) +
            final_stats.get("hp", 0) / 2
        )
    else:
        # Mixed: score both offensive stats
        score = (
            0.5 * final_stats.get("attack", 0) +
            0.5 * final_stats.get("special_attack", 0) +
            final_stats.get("speed", 0) +
            final_stats.get("hp", 0) / 2
        )

    # Penalize high EV usage (prefer efficient spreads)
    score -= total_evs / 100.0

    return score


def find_optimal_nature_for_benchmarks(
    base_stats: BaseStats,
    benchmarks: dict,
    is_physical: bool = False,
    is_special: bool = False,
    role: str = "offensive",
    level: int = 50
) -> Optional[NatureOptimizationResult]:
    """
    Find optimal nature for benchmark-based EV spread.

    Tests all relevant natures and selects the one that:
    1. Meets all benchmarks (speed targets, survival requirements)
    2. Maximizes total useful stats (Attack/SpA + Speed + HP)
    3. Minimizes wasted EVs

    Args:
        base_stats: Pokemon base stats
        benchmarks: Dict with benchmark requirements (see calculate_evs_for_benchmarks)
        is_physical: True if physical attacker
        is_special: True if special attacker
        role: "offensive", "defensive", or "mixed"
        level: Pokemon level (default 50)

    Returns:
        NatureOptimizationResult with best nature, EVs, and reasoning, or None if impossible
    """
    from .stats import calculate_all_stats
    from ..models.pokemon import PokemonBuild, EVSpread

    # Get relevant natures to test
    candidates = get_relevant_natures(is_physical, is_special, role)

    best_result = None
    best_score = float('-inf')

    # Test each nature candidate
    for nature in candidates:
        # Calculate required EVs for this nature
        evs_dict = calculate_evs_for_benchmarks(base_stats, nature, benchmarks, level)
        
        if evs_dict is None:
            # This nature cannot meet benchmarks
            continue

        # Calculate final stats with this nature and EVs
        evs = EVSpread(**evs_dict)
        pokemon = PokemonBuild(
            name="temp",
            base_stats=base_stats,
            nature=nature,
            evs=evs,
            level=level
        )
        final_stats = calculate_all_stats(pokemon, level)

        # Calculate score
        total_evs = sum(evs_dict.values())
        score = calculate_nature_score(
            nature, final_stats, is_physical, is_special, total_evs, role
        )

        # Compare to neutral nature for EV savings calculation
        neutral_evs = calculate_evs_for_benchmarks(
            base_stats, Nature.SERIOUS, benchmarks, level
        )
        neutral_total = sum(neutral_evs.values()) if neutral_evs else total_evs
        ev_savings = neutral_total - total_evs

        # Track best result
        if score > best_score:
            best_score = score
            
            # Generate reasoning
            boosted_stat = None
            if get_nature_modifier(nature, "attack") > 1.0:
                boosted_stat = "Attack"
            elif get_nature_modifier(nature, "special_attack") > 1.0:
                boosted_stat = "Special Attack"
            elif get_nature_modifier(nature, "speed") > 1.0:
                boosted_stat = "Speed"
            elif get_nature_modifier(nature, "defense") > 1.0:
                boosted_stat = "Defense"
            elif get_nature_modifier(nature, "special_defense") > 1.0:
                boosted_stat = "Special Defense"

            reasoning_parts = []
            if boosted_stat:
                reasoning_parts.append(
                    f"{nature.value.title()}'s +{boosted_stat} boost"
                )
            else:
                reasoning_parts.append(f"{nature.value.title()} nature")

            if benchmarks.get("speed_target"):
                reasoning_parts.append(
                    f"requires {evs_dict['speed']} Speed EVs to hit {benchmarks['speed_target']} Speed"
                )

            if benchmarks.get("prioritize") == "offense":
                off_stat = "Attack" if is_physical else "Special Attack"
                reasoning_parts.append(
                    f"maximizes {off_stat} ({final_stats.get('attack' if is_physical else 'special_attack', 0)})"
                )

            if ev_savings > 0:
                reasoning_parts.append(f"saves {ev_savings} EVs vs neutral nature")

            reasoning = ", ".join(reasoning_parts) + "."

            best_result = NatureOptimizationResult(
                best_nature=nature,
                evs=evs_dict,
                final_stats=final_stats,
                ev_savings=ev_savings,
                reasoning=reasoning,
                score=score
            )

    return best_result
