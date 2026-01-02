"""Meta threat damage analysis engine.

This module provides analysis of a Pokemon's spread against the top
threats in the metagame, including damage calculations in both directions.
"""

from dataclasses import dataclass, field
from typing import Optional
import math

from ..models.pokemon import PokemonBuild, BaseStats, EVSpread, Nature
from ..models.move import Move, MoveCategory
from .stats import calculate_all_stats
from ..utils.damage_verdicts import calculate_ko_verdict


@dataclass
class ThreatDamageResult:
    """Result of threat analysis for a single matchup."""
    threat_name: str
    threat_usage_pct: float
    your_damage_to_threat: dict   # Best move, damage range, KO chance
    threat_damage_to_you: dict    # Best move, damage range, KO chance
    speed_comparison: str
    matchup_verdict: str          # "Favorable", "Unfavorable", "Even"
    threat_spread: Optional[dict] = None  # Spread used for calculation (nature, evs, usage)
    threat_stats: Optional[dict] = None   # Calculated stats from spread


@dataclass
class MetaThreatReport:
    """Full report of spread vs meta threats."""
    pokemon_name: str
    spread_summary: str
    threats_analyzed: int
    favorable_matchups: list[ThreatDamageResult]
    unfavorable_matchups: list[ThreatDamageResult]
    even_matchups: list[ThreatDamageResult]
    ohko_threats: list[str]  # Pokemon that can OHKO you
    ohko_targets: list[str]  # Pokemon you can OHKO
    spread_weaknesses: list[str]  # Identified vulnerabilities
    improvement_suggestions: list[str]


def calculate_simple_damage(
    attacker_stats: dict,
    defender_stats: dict,
    move_power: int,
    is_physical: bool,
    stab: bool = False,
    type_effectiveness: float = 1.0,
    is_spread: bool = False
) -> dict:
    """
    Calculate simplified damage without full move/modifier infrastructure.

    This is used for quick threat analysis where we don't have full
    move data but want to estimate damage ranges.

    Returns:
        Dict with min/max damage and percentage
    """
    # Get attacking and defending stats
    atk_stat = attacker_stats["attack"] if is_physical else attacker_stats["special_attack"]
    def_stat = defender_stats["defense"] if is_physical else defender_stats["special_defense"]
    defender_hp = defender_stats["hp"]

    # Level 50 calculation
    level_factor = 22  # floor(2*50/5+2)

    # Base damage
    base_damage = math.floor(
        math.floor(
            math.floor(level_factor * move_power * atk_stat / def_stat) / 50
        ) + 2
    )

    # Apply spread modifier for doubles
    if is_spread:
        base_damage = int(base_damage * 0.75)

    # Calculate damage rolls (0.85 to 1.0)
    min_roll = int(base_damage * 0.85)
    max_roll = base_damage

    # Apply STAB
    if stab:
        min_roll = int(min_roll * 1.5)
        max_roll = int(max_roll * 1.5)

    # Apply type effectiveness
    min_roll = int(min_roll * type_effectiveness)
    max_roll = int(max_roll * type_effectiveness)

    # Ensure minimum 1 damage
    min_roll = max(1, min_roll)
    max_roll = max(1, max_roll)

    min_pct = (min_roll / defender_hp) * 100
    max_pct = (max_roll / defender_hp) * 100

    # KO calculations using accurate verdict system
    is_ohko = min_roll >= defender_hp
    can_ohko = max_roll >= defender_hp

    # Get mathematically accurate verdict
    verdict = calculate_ko_verdict(min_pct, max_pct)

    return {
        "min_damage": min_roll,
        "max_damage": max_roll,
        "min_percent": round(min_pct, 1),
        "max_percent": round(max_pct, 1),
        "is_guaranteed_ohko": is_ohko,
        "is_possible_ohko": can_ohko,
        "ko_chance": verdict.verdict,
        "ko_description": verdict.description,
        "chip_needed": verdict.chip_needed
    }


def analyze_single_threat(
    your_pokemon: PokemonBuild,
    your_stats: dict,
    threat_name: str,
    threat_stats: dict,
    threat_types: list[str],
    threat_usage_pct: float,
    threat_common_moves: list[dict],
    your_common_moves: list[dict],
    your_speed: int,
    threat_spread: Optional[dict] = None
) -> ThreatDamageResult:
    """
    Analyze matchup against a single threat.

    Args:
        your_pokemon: Your Pokemon build
        your_stats: Your calculated stats
        threat_name: Threat's name
        threat_stats: Threat's stats (dict with hp, attack, defense, etc.)
        threat_types: Threat's types
        threat_usage_pct: Threat's usage percentage
        threat_common_moves: List of threat's common moves with power/type/category
        your_common_moves: Your common moves
        your_speed: Your calculated speed
        threat_spread: Optional spread dict with nature, evs, and usage

    Returns:
        ThreatDamageResult with matchup analysis
    """
    your_hp = your_stats["hp"]
    threat_hp = threat_stats.get("hp", 150)  # Default if not available
    threat_speed = threat_stats.get("speed", 100)

    # Find best threat move against you
    best_threat_damage = {"max_percent": 0}
    for move_data in threat_common_moves:
        move_power = move_data.get("power", 0)
        move_type = move_data.get("type", "normal")
        is_physical = move_data.get("category", "physical").lower() == "physical"

        if move_power == 0:
            continue

        # Calculate type effectiveness against your Pokemon
        type_eff = _get_simple_effectiveness(move_type, your_pokemon.types)

        # Check STAB
        stab = move_type.lower() in [t.lower() for t in threat_types]

        damage = calculate_simple_damage(
            threat_stats, your_stats,
            move_power, is_physical,
            stab=stab,
            type_effectiveness=type_eff
        )

        if damage["max_percent"] > best_threat_damage.get("max_percent", 0):
            best_threat_damage = {
                "move": move_data.get("name", "Unknown"),
                "type": move_type,
                **damage
            }

    # Find your best move against threat
    best_your_damage = {"max_percent": 0}
    for move_data in your_common_moves:
        move_power = move_data.get("power", 0)
        move_type = move_data.get("type", "normal")
        is_physical = move_data.get("category", "physical").lower() == "physical"

        if move_power == 0:
            continue

        # Calculate type effectiveness against threat
        type_eff = _get_simple_effectiveness(move_type, threat_types)

        # Check STAB
        stab = move_type.lower() in [t.lower() for t in your_pokemon.types]

        damage = calculate_simple_damage(
            your_stats, threat_stats,
            move_power, is_physical,
            stab=stab,
            type_effectiveness=type_eff
        )

        if damage["max_percent"] > best_your_damage.get("max_percent", 0):
            best_your_damage = {
                "move": move_data.get("name", "Unknown"),
                "type": move_type,
                **damage
            }

    # Speed comparison
    if your_speed > threat_speed:
        speed_comparison = f"You outspeed ({your_speed} vs {threat_speed})"
    elif your_speed < threat_speed:
        speed_comparison = f"They outspeed ({threat_speed} vs {your_speed})"
    else:
        speed_comparison = f"Speed tie ({your_speed})"

    # Determine verdict
    you_ohko = best_your_damage.get("is_guaranteed_ohko", False)
    they_ohko = best_threat_damage.get("is_guaranteed_ohko", False)
    you_faster = your_speed > threat_speed

    if you_ohko and (you_faster or not they_ohko):
        verdict = "Favorable"
    elif they_ohko and (not you_faster or not you_ohko):
        verdict = "Unfavorable"
    elif best_your_damage.get("max_percent", 0) > best_threat_damage.get("max_percent", 0) + 20:
        verdict = "Favorable"
    elif best_threat_damage.get("max_percent", 0) > best_your_damage.get("max_percent", 0) + 20:
        verdict = "Unfavorable"
    else:
        verdict = "Even"

    return ThreatDamageResult(
        threat_name=threat_name,
        threat_usage_pct=threat_usage_pct,
        your_damage_to_threat=best_your_damage if best_your_damage.get("max_percent", 0) > 0 else {"message": "No damaging moves analyzed"},
        threat_damage_to_you=best_threat_damage if best_threat_damage.get("max_percent", 0) > 0 else {"message": "No damaging moves analyzed"},
        speed_comparison=speed_comparison,
        matchup_verdict=verdict,
        threat_spread=threat_spread,
        threat_stats=threat_stats
    )


def _get_simple_effectiveness(move_type: str, defender_types: list[str]) -> float:
    """Get simple type effectiveness multiplier."""
    # Basic type chart (subset for common interactions)
    TYPE_CHART = {
        "fire": {"grass": 2, "ice": 2, "bug": 2, "steel": 2, "water": 0.5, "fire": 0.5, "rock": 0.5, "dragon": 0.5},
        "water": {"fire": 2, "ground": 2, "rock": 2, "water": 0.5, "grass": 0.5, "dragon": 0.5},
        "grass": {"water": 2, "ground": 2, "rock": 2, "fire": 0.5, "grass": 0.5, "poison": 0.5, "flying": 0.5, "bug": 0.5, "dragon": 0.5, "steel": 0.5},
        "electric": {"water": 2, "flying": 2, "electric": 0.5, "grass": 0.5, "dragon": 0.5, "ground": 0},
        "ice": {"grass": 2, "ground": 2, "flying": 2, "dragon": 2, "fire": 0.5, "water": 0.5, "ice": 0.5, "steel": 0.5},
        "fighting": {"normal": 2, "ice": 2, "rock": 2, "dark": 2, "steel": 2, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "fairy": 0.5, "ghost": 0},
        "poison": {"grass": 2, "fairy": 2, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0},
        "ground": {"fire": 2, "electric": 2, "poison": 2, "rock": 2, "steel": 2, "grass": 0.5, "bug": 0.5, "flying": 0},
        "flying": {"grass": 2, "fighting": 2, "bug": 2, "electric": 0.5, "rock": 0.5, "steel": 0.5},
        "psychic": {"fighting": 2, "poison": 2, "psychic": 0.5, "steel": 0.5, "dark": 0},
        "bug": {"grass": 2, "psychic": 2, "dark": 2, "fire": 0.5, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "ghost": 0.5, "steel": 0.5, "fairy": 0.5},
        "rock": {"fire": 2, "ice": 2, "flying": 2, "bug": 2, "fighting": 0.5, "ground": 0.5, "steel": 0.5},
        "ghost": {"psychic": 2, "ghost": 2, "dark": 0.5, "normal": 0},
        "dragon": {"dragon": 2, "steel": 0.5, "fairy": 0},
        "dark": {"psychic": 2, "ghost": 2, "fighting": 0.5, "dark": 0.5, "fairy": 0.5},
        "steel": {"ice": 2, "rock": 2, "fairy": 2, "fire": 0.5, "water": 0.5, "electric": 0.5, "steel": 0.5},
        "fairy": {"fighting": 2, "dragon": 2, "dark": 2, "fire": 0.5, "poison": 0.5, "steel": 0.5},
        "normal": {"ghost": 0, "rock": 0.5, "steel": 0.5},
    }

    effectiveness = 1.0
    move_type_lower = move_type.lower()

    if move_type_lower not in TYPE_CHART:
        return 1.0

    type_matchups = TYPE_CHART[move_type_lower]

    for def_type in defender_types:
        def_type_lower = def_type.lower()
        if def_type_lower in type_matchups:
            effectiveness *= type_matchups[def_type_lower]

    return effectiveness


def generate_spread_suggestions(
    pokemon: PokemonBuild,
    threat_results: list[ThreatDamageResult]
) -> list[str]:
    """
    Generate suggestions to improve the spread based on threat analysis.

    Args:
        pokemon: The Pokemon build
        threat_results: Results from threat analysis

    Returns:
        List of improvement suggestions
    """
    suggestions = []

    # Analyze unfavorable matchups
    unfavorable = [t for t in threat_results if t.matchup_verdict == "Unfavorable"]

    # Check for speed issues
    speed_issues = [t for t in unfavorable if "They outspeed" in t.speed_comparison]
    if speed_issues:
        # Find the fastest threat that outspeeds us
        suggestion_threats = [t.threat_name for t in speed_issues[:3]]
        suggestions.append(
            f"Consider more Speed EVs to outspeed: {', '.join(suggestion_threats)}"
        )

    # Check for bulk issues (getting OHKOd)
    ohko_threats = [t for t in threat_results
                    if t.threat_damage_to_you.get("is_guaranteed_ohko", False)]
    if ohko_threats:
        physical_ohkos = []
        special_ohkos = []
        for t in ohko_threats:
            move_data = t.threat_damage_to_you
            # Rough check - if no category info, assume based on move name patterns
            if "physical" in str(move_data).lower():
                physical_ohkos.append(t.threat_name)
            else:
                special_ohkos.append(t.threat_name)

        if physical_ohkos:
            suggestions.append(
                f"Consider more HP/Defense to survive physical attacks from: {', '.join(physical_ohkos[:3])}"
            )
        if special_ohkos:
            suggestions.append(
                f"Consider more HP/SpD to survive special attacks from: {', '.join(special_ohkos[:3])}"
            )

    # Check for offensive power issues
    low_damage = [t for t in threat_results
                  if t.your_damage_to_threat.get("max_percent", 100) < 50]
    if len(low_damage) > len(threat_results) // 2:
        suggestions.append(
            "Consider more offensive investment - dealing low damage to many threats"
        )

    if not suggestions:
        suggestions.append("Current spread handles the analyzed threats well")

    return suggestions


def create_empty_threat_report(pokemon_name: str, spread_summary: str, reason: str) -> MetaThreatReport:
    """Create an empty threat report when analysis can't be completed."""
    return MetaThreatReport(
        pokemon_name=pokemon_name,
        spread_summary=spread_summary,
        threats_analyzed=0,
        favorable_matchups=[],
        unfavorable_matchups=[],
        even_matchups=[],
        ohko_threats=[],
        ohko_targets=[],
        spread_weaknesses=[reason],
        improvement_suggestions=[]
    )
