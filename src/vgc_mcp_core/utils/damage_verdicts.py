"""Accurate damage verdict generation for VGC MCP tools.

This module provides mathematically correct KO analysis descriptions,
avoiding misleading statements like "clean 2HKO" when the math doesn't add up.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DamageVerdict:
    """Structured damage analysis result."""
    min_percent: float
    max_percent: float
    verdict: str           # Short label: "Guaranteed OHKO", "2HKO", "3HKO", "Chip"
    description: str       # Full explanation
    chip_needed: Optional[float] = None  # How much prior damage needed for KO
    is_guaranteed: bool = False


def calculate_ko_verdict(
    min_percent: float,
    max_percent: float,
    include_prior_damage_calc: bool = True
) -> DamageVerdict:
    """
    Generate accurate KO verdict based on damage percentages.

    The math:
    - Guaranteed OHKO: min_percent >= 100%
    - Possible OHKO: max_percent >= 100% but min_percent < 100%
    - Guaranteed 2HKO: min_percent >= 50% (two min rolls >= 100%)
    - Possible 2HKO: max_percent >= 50% but min_percent < 50%
    - Guaranteed 3HKO: min_percent >= 34% (three min rolls >= 102%)
    - etc.

    Args:
        min_percent: Minimum damage roll percentage
        max_percent: Maximum damage roll percentage
        include_prior_damage_calc: Whether to calculate chip damage needed

    Returns:
        DamageVerdict with accurate description
    """
    # OHKO analysis
    if min_percent >= 100:
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Guaranteed OHKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Guaranteed OHKO",
            is_guaranteed=True
        )

    if max_percent >= 100:
        # Calculate OHKO chance (simplified - assumes uniform distribution)
        ohko_chance = ((max_percent - 100) / (max_percent - min_percent)) * 100 if max_percent > min_percent else 100
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Possible OHKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - {ohko_chance:.0f}% chance to OHKO",
            chip_needed=100 - min_percent if include_prior_damage_calc else None,
            is_guaranteed=False
        )

    # 2HKO analysis
    two_hit_min = min_percent * 2
    two_hit_max = max_percent * 2

    if min_percent >= 50:
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Guaranteed 2HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Guaranteed 2HKO",
            is_guaranteed=True
        )

    if max_percent >= 50:
        # Can 2HKO with good rolls, calculate chip needed for guarantee
        chip_for_2hko = 100 - two_hit_min if include_prior_damage_calc else None
        if chip_for_2hko and chip_for_2hko > 0:
            return DamageVerdict(
                min_percent=min_percent,
                max_percent=max_percent,
                verdict="Possible 2HKO",
                description=f"{min_percent:.0f}-{max_percent:.0f}% - 2HKO with good rolls, needs ~{chip_for_2hko:.0f}% chip to guarantee",
                chip_needed=chip_for_2hko,
                is_guaranteed=False
            )
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Possible 2HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Possible 2HKO with high rolls",
            is_guaranteed=False
        )

    # 3HKO analysis
    three_hit_min = min_percent * 3
    three_hit_max = max_percent * 3

    if min_percent >= 34:
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Guaranteed 3HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Guaranteed 3HKO",
            is_guaranteed=True
        )

    if max_percent >= 34:
        chip_for_3hko = 100 - three_hit_min if include_prior_damage_calc else None
        if chip_for_3hko and chip_for_3hko > 0:
            return DamageVerdict(
                min_percent=min_percent,
                max_percent=max_percent,
                verdict="Possible 3HKO",
                description=f"{min_percent:.0f}-{max_percent:.0f}% - 3HKO range, needs ~{chip_for_3hko:.0f}% prior damage to guarantee",
                chip_needed=chip_for_3hko,
                is_guaranteed=False
            )
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Possible 3HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Possible 3HKO",
            is_guaranteed=False
        )

    # 4HKO or worse - just chip damage
    if max_percent >= 25:
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="4HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - 4HKO range, chip damage",
            is_guaranteed=False
        )

    # Minimal chip
    return DamageVerdict(
        min_percent=min_percent,
        max_percent=max_percent,
        verdict="Chip",
        description=f"{min_percent:.0f}-{max_percent:.0f}% - Minor chip damage only",
        is_guaranteed=False
    )


def format_matchup_verdict(
    min_percent: float,
    max_percent: float,
    attacker_faster: bool = False,
    defender_survives_counter: bool = True,
    move_name: Optional[str] = None
) -> str:
    """
    Generate a comprehensive matchup verdict for display.

    Args:
        min_percent: Minimum damage percentage
        max_percent: Maximum damage percentage
        attacker_faster: Whether the attacker outspeeds
        defender_survives_counter: Whether attacker survives the counterattack
        move_name: Name of the move used

    Returns:
        Human-readable matchup summary
    """
    verdict = calculate_ko_verdict(min_percent, max_percent)

    parts = []
    if move_name:
        parts.append(move_name)

    parts.append(verdict.description)

    if attacker_faster and verdict.verdict in ["Guaranteed OHKO", "Possible OHKO"]:
        parts.append("(you move first)")
    elif not attacker_faster and verdict.verdict in ["Guaranteed OHKO", "Possible OHKO"]:
        parts.append("(but they move first)")

    if not defender_survives_counter and verdict.verdict not in ["Guaranteed OHKO"]:
        parts.append("- WARNING: You get KO'd back")

    return " ".join(parts)


# Commonly misused descriptions to avoid
MISLEADING_TERMS = {
    "clean 2HKO": "Use 'Guaranteed 2HKO' only when min% >= 50",
    "solid 2HKO": "Use 'Guaranteed 2HKO' only when min% >= 50",
    "easy 2HKO": "Use 'Guaranteed 2HKO' only when min% >= 50",
    "clean OHKO": "Use 'Guaranteed OHKO' only when min% >= 100",
}


def format_secondary_effect_note(
    move_name: str,
    effect: str,
    chance: int,
    is_relevant: bool = True
) -> str:
    """
    Generate a note about a move's secondary effect.

    Args:
        move_name: Name of the move
        effect: Effect type (burn, paralysis, etc.)
        chance: Effect chance percentage
        is_relevant: Whether the effect matters in context

    Returns:
        Human-readable note about the effect
    """
    effect_impact = {
        "burn": "halves physical damage output",
        "paralysis": "25% full paralysis chance, halves Speed",
        "freeze": "target cannot act until thawed",
        "poison": "1/8 HP damage per turn",
        "badly_poison": "increasing damage each turn",
        "flinch": "target loses their turn (if you're faster)",
        "confusion": "50% chance to hit self",
        "sleep": "target cannot act for 1-3 turns",
        "stat_drop": "affects future damage calculations",
    }

    impact = effect_impact.get(effect, "")

    if chance == 100:
        return f"[!] {move_name.title()} always {effect}s - {impact}"
    elif chance >= 30:
        return f"[!] {move_name.title()} has {chance}% {effect} chance - {impact}"
    else:
        return f"Note: {move_name.title()} has {chance}% {effect} chance"


def enhance_verdict_with_effect(
    base_verdict: DamageVerdict,
    move_name: str,
    secondary_effect: Optional[tuple[str, int]] = None
) -> DamageVerdict:
    """
    Enhance a damage verdict with secondary effect info.

    Args:
        base_verdict: The base damage verdict
        move_name: Name of the move
        secondary_effect: Tuple of (effect_type, chance) or None

    Returns:
        Enhanced DamageVerdict with effect note in description
    """
    if not secondary_effect:
        return base_verdict

    effect_type, chance = secondary_effect

    # Add effect note to description
    effect_note = format_secondary_effect_note(move_name, effect_type, chance)

    enhanced_desc = f"{base_verdict.description}. {effect_note}"

    return DamageVerdict(
        min_percent=base_verdict.min_percent,
        max_percent=base_verdict.max_percent,
        verdict=base_verdict.verdict,
        description=enhanced_desc,
        chip_needed=base_verdict.chip_needed,
        is_guaranteed=base_verdict.is_guaranteed
    )


def format_terrain_note(
    terrain: str,
    move_type: str,
    attacker_grounded: bool = True,
    defender_grounded: bool = True
) -> Optional[str]:
    """
    Generate a note about terrain impact on damage.

    Args:
        terrain: Active terrain (electric, grassy, psychic, misty)
        move_type: Type of the move
        attacker_grounded: Whether attacker is grounded
        defender_grounded: Whether defender is grounded

    Returns:
        Note about terrain effect, or None if no impact
    """
    terrain = terrain.lower() if terrain else None
    move_type = move_type.lower() if move_type else None

    if not terrain:
        return None

    # Attacker must be grounded for offensive terrain boosts
    if terrain == "electric" and move_type == "electric":
        if attacker_grounded:
            return "[TERRAIN] Electric Terrain: +30% Electric damage"
        return "Note: Electric Terrain active but attacker not grounded"

    if terrain == "grassy" and move_type == "grass":
        if attacker_grounded:
            return "[TERRAIN] Grassy Terrain: +30% Grass damage"
        return "Note: Grassy Terrain active but attacker not grounded"

    if terrain == "psychic" and move_type == "psychic":
        if attacker_grounded:
            return "[TERRAIN] Psychic Terrain: +30% Psychic damage"
        return "Note: Psychic Terrain active but attacker not grounded"

    # Misty terrain affects defender
    if terrain == "misty" and move_type == "dragon":
        if defender_grounded:
            return "[TERRAIN] Misty Terrain: -50% Dragon damage (defender grounded)"
        return "Note: Misty Terrain active but defender not grounded"

    # Grassy terrain reduces ground moves
    if terrain == "grassy" and move_type in ["ground"]:
        if defender_grounded:
            return "[TERRAIN] Grassy Terrain: -50% Earthquake/Bulldoze damage"

    return None
