"""Speed probability analysis using Smogon spread distributions.

This module calculates the probability of outspeeding opponents based on
their actual usage spread distributions from Smogon stats.
"""

from dataclasses import dataclass
from typing import Optional
import math

from ..models.pokemon import Nature, NATURE_MODIFIERS
from ..config import EV_BREAKPOINTS_LV50


@dataclass
class SpeedTierResult:
    """Result of a speed probability calculation against a specific target."""
    your_speed: int
    target_pokemon: str
    target_base_speed: int
    outspeed_probability: float  # 0-100%
    speed_tie_probability: float  # 0-100%
    underspeed_probability: float  # 0-100%
    target_speed_distribution: list[dict]  # [{speed, usage_pct, nature, evs}, ...]
    analysis: str


@dataclass
class MetaSpeedResult:
    """Result of a meta-wide speed analysis."""
    your_speed: int
    your_pokemon: str
    total_outspeed_rate: float  # Usage-weighted % of meta you outspeed
    pokemon_analysis: list[dict]  # Per-Pokemon breakdown
    speed_tier_summary: str
    threats: list[str]  # Pokemon that outspeed you
    outspeeds: list[str]  # Pokemon you outspeed


def get_nature_speed_modifier(nature_name: str) -> float:
    """Get speed modifier from nature name string."""
    nature_name_lower = nature_name.lower().strip()

    for nature in Nature:
        if nature.value == nature_name_lower:
            mods = NATURE_MODIFIERS.get(nature, {})
            return mods.get("speed", 1.0)

    return 1.0


def calculate_speed_stat(
    base_speed: int,
    nature: str,
    speed_evs: int,
    speed_iv: int = 31,
    level: int = 50
) -> int:
    """
    Calculate the actual speed stat from base stats and spread.

    Formula (Level 50):
    Stat = floor((floor((2 * Base + IV + EV/4) * Level/100) + 5) * Nature)

    Args:
        base_speed: Base speed stat of the Pokemon
        nature: Nature name (e.g., "Timid", "Jolly")
        speed_evs: Speed EVs (0-252)
        speed_iv: Speed IV (0-31, default 31)
        level: Pokemon level (default 50 for VGC)

    Returns:
        Calculated speed stat
    """
    nature_mod = get_nature_speed_modifier(nature)
    inner = math.floor((2 * base_speed + speed_iv + speed_evs // 4) * level / 100)
    return math.floor((inner + 5) * nature_mod)


def parse_spread_to_speed(
    base_speed: int,
    spread: dict,
    level: int = 50
) -> int:
    """
    Convert Smogon spread dict to calculated speed stat.

    Args:
        base_speed: Base speed stat of the Pokemon
        spread: Smogon spread dict with 'nature' and 'evs' keys
        level: Pokemon level (default 50 for VGC)

    Returns:
        Calculated speed stat
    """
    nature = spread.get("nature", "Serious")
    evs = spread.get("evs", {})
    speed_evs = evs.get("speed", 0)

    return calculate_speed_stat(base_speed, nature, speed_evs, level=level)


def calculate_outspeed_probability(
    your_speed: int,
    target_base_speed: int,
    target_spreads: list[dict],
    target_pokemon: str = "Target"
) -> SpeedTierResult:
    """
    Calculate probability of outspeeding based on target's spread distribution.

    This uses the actual Smogon usage data to determine what % of the time
    you will outspeed the opponent based on their common spread choices.
    Results are normalized to 100% for accurate probability representation.

    Args:
        your_speed: Your Pokemon's calculated speed stat
        target_base_speed: Target Pokemon's base speed stat
        target_spreads: List of spread dicts from Smogon, each with:
            - nature: str
            - evs: dict with 'speed' key
            - usage: float (percentage)
        target_pokemon: Name of target Pokemon for display

    Returns:
        SpeedTierResult with outspeed/tie/underspeed probabilities (normalized to 100%)
    """
    if not target_spreads:
        return SpeedTierResult(
            your_speed=your_speed,
            target_pokemon=target_pokemon,
            target_base_speed=target_base_speed,
            outspeed_probability=0.0,
            speed_tie_probability=0.0,
            underspeed_probability=100.0,
            target_speed_distribution=[],
            analysis=f"No spread data available for {target_pokemon}"
        )

    outspeed_total = 0.0
    tie_total = 0.0
    underspeed_total = 0.0

    speed_distribution = []

    for spread in target_spreads:
        usage_pct = spread.get("usage", 0)
        target_speed = parse_spread_to_speed(target_base_speed, spread)

        speed_info = {
            "speed": target_speed,
            "usage_pct": usage_pct,
            "nature": spread.get("nature", "Unknown"),
            "speed_evs": spread.get("evs", {}).get("speed", 0),
            "spread_string": spread.get("spread_string", "")
        }
        speed_distribution.append(speed_info)

        if your_speed > target_speed:
            outspeed_total += usage_pct
        elif your_speed == target_speed:
            # Speed tie - 50% chance each
            tie_total += usage_pct
        else:
            underspeed_total += usage_pct

    # Sort distribution by speed (descending)
    speed_distribution.sort(key=lambda x: x["speed"], reverse=True)

    # Normalize to 100% (spreads may not sum to exactly 100%)
    total_usage = outspeed_total + tie_total + underspeed_total
    if total_usage > 0:
        outspeed_pct = (outspeed_total / total_usage) * 100
        tie_pct = (tie_total / total_usage) * 100
        underspeed_pct = (underspeed_total / total_usage) * 100
    else:
        outspeed_pct = 0.0
        tie_pct = 0.0
        underspeed_pct = 100.0

    # Generate analysis text
    if outspeed_pct >= 95:
        analysis = f"You outspeed virtually all {target_pokemon} spreads ({outspeed_pct:.1f}%)"
    elif outspeed_pct >= 75:
        analysis = f"You outspeed most {target_pokemon} spreads ({outspeed_pct:.1f}%)"
    elif outspeed_pct >= 50:
        analysis = f"Speed is contested - you outspeed {outspeed_pct:.1f}% of {target_pokemon}"
    elif outspeed_pct >= 25:
        analysis = f"Most {target_pokemon} outspeed you ({underspeed_pct:.1f}% faster)"
    else:
        analysis = f"Nearly all {target_pokemon} outspeed you ({underspeed_pct:.1f}%)"

    if tie_pct >= 5:
        analysis += f" - significant tie chance ({tie_pct:.1f}%)"

    return SpeedTierResult(
        your_speed=your_speed,
        target_pokemon=target_pokemon,
        target_base_speed=target_base_speed,
        outspeed_probability=round(outspeed_pct, 1),
        speed_tie_probability=round(tie_pct, 1),
        underspeed_probability=round(underspeed_pct, 1),
        target_speed_distribution=speed_distribution,
        analysis=analysis
    )


def calculate_meta_outspeed_rate(
    your_speed: int,
    your_pokemon: str,
    top_pokemon_data: list[dict],
    usage_weighted: bool = True
) -> MetaSpeedResult:
    """
    Calculate % of entire meta you outspeed.

    This provides a comprehensive view of your speed tier relative to
    the entire metagame, weighted by Pokemon usage.

    Args:
        your_speed: Your Pokemon's calculated speed stat
        your_pokemon: Your Pokemon's name
        top_pokemon_data: List of dicts, each with:
            - name: Pokemon name
            - base_speed: Base speed stat
            - usage_percent: Overall usage %
            - spreads: List of spread dicts
        usage_weighted: If True, weight by both Pokemon usage and spread usage

    Returns:
        MetaSpeedResult with meta-wide analysis
    """
    pokemon_analysis = []
    threats = []
    outspeeds = []

    total_weighted_outspeed = 0.0
    total_weight = 0.0

    for pokemon_data in top_pokemon_data:
        name = pokemon_data.get("name", "Unknown")
        base_speed = pokemon_data.get("base_speed", 50)
        usage_percent = pokemon_data.get("usage_percent", 0)
        spreads = pokemon_data.get("spreads", [])

        # Calculate outspeed probability for this Pokemon
        result = calculate_outspeed_probability(
            your_speed, base_speed, spreads, name
        )

        # Weight by Pokemon's usage in the meta
        weight = usage_percent if usage_weighted else 1.0
        total_weight += weight

        # Weighted outspeed rate
        weighted_outspeed = result.outspeed_probability * weight / 100
        total_weighted_outspeed += weighted_outspeed

        pokemon_analysis.append({
            "pokemon": name,
            "usage_percent": usage_percent,
            "outspeed_probability": result.outspeed_probability,
            "most_common_speed": result.target_speed_distribution[0]["speed"] if result.target_speed_distribution else 0,
            "analysis": result.analysis
        })

        # Categorize as threat or outsped
        if result.outspeed_probability < 50:
            threats.append(f"{name} ({result.underspeed_probability:.0f}% faster)")
        elif result.outspeed_probability >= 50:
            outspeeds.append(f"{name} ({result.outspeed_probability:.0f}%)")

    # Calculate overall meta outspeed rate
    if total_weight > 0:
        meta_outspeed_rate = (total_weighted_outspeed / total_weight) * 100
    else:
        meta_outspeed_rate = 0.0

    # Generate summary
    if meta_outspeed_rate >= 80:
        summary = f"{your_pokemon} at {your_speed} Speed is extremely fast for the meta"
    elif meta_outspeed_rate >= 60:
        summary = f"{your_pokemon} at {your_speed} Speed outspeeds most of the meta"
    elif meta_outspeed_rate >= 40:
        summary = f"{your_pokemon} at {your_speed} Speed sits in the middle of the meta"
    elif meta_outspeed_rate >= 20:
        summary = f"{your_pokemon} at {your_speed} Speed is on the slower side"
    else:
        summary = f"{your_pokemon} at {your_speed} Speed is quite slow for the meta"

    return MetaSpeedResult(
        your_speed=your_speed,
        your_pokemon=your_pokemon,
        total_outspeed_rate=round(meta_outspeed_rate, 1),
        pokemon_analysis=pokemon_analysis,
        speed_tier_summary=summary,
        threats=threats[:10],  # Top 10 threats
        outspeeds=outspeeds[:10]  # Top 10 you outspeed
    )


def build_speed_distribution_data(
    top_pokemon_data: list[dict],
) -> list[dict]:
    """
    Build cumulative speed distribution for UI visualization.

    Takes pre-fetched Pokemon data and creates a sorted list of speed points
    with cumulative outspeed percentages for client-side calculation.

    Args:
        top_pokemon_data: List of dicts, each with:
            - name: Pokemon name
            - base_speed: Base speed stat
            - usage_percent: Overall usage % in meta (0-100)
            - spreads: List of spread dicts with nature, evs, usage

    Returns:
        List of speed distribution entries sorted by speed (ascending):
        [{
            speed: int,
            cumulative_outspeed_pct: float,  # % of meta slower than this speed
            pokemon_at_speed: [{name, usage_pct, nature, evs}]
        }]
    """
    # Collect all speed values with their usage weights
    speed_entries: list[dict] = []

    for pokemon_data in top_pokemon_data:
        pokemon_name = pokemon_data.get("name", "Unknown")
        base_speed = pokemon_data.get("base_speed", 50)
        pokemon_usage = pokemon_data.get("usage_percent", 0) / 100  # Convert to 0-1
        spreads = pokemon_data.get("spreads", [])

        for spread in spreads:
            spread_usage = spread.get("usage", 0) / 100  # Convert to 0-1
            nature = spread.get("nature", "Serious")
            evs = spread.get("evs", {})
            speed_evs = evs.get("speed", 0)

            # Calculate actual speed stat
            speed_stat = calculate_speed_stat(base_speed, nature, speed_evs)

            # Weight = pokemon usage * spread usage
            weight = pokemon_usage * spread_usage

            speed_entries.append({
                "speed": speed_stat,
                "pokemon": pokemon_name,
                "weight": weight,
                "nature": nature,
                "evs": speed_evs
            })

    # Group by speed value
    speed_map: dict[int, dict] = {}
    for entry in speed_entries:
        speed = entry["speed"]
        if speed not in speed_map:
            speed_map[speed] = {"pokemon_at_speed": [], "total_weight": 0.0}
        speed_map[speed]["pokemon_at_speed"].append({
            "name": entry["pokemon"],
            "usage_pct": round(entry["weight"] * 100, 2),
            "nature": entry["nature"],
            "evs": entry["evs"]
        })
        speed_map[speed]["total_weight"] += entry["weight"]

    # Sort by speed and calculate cumulative
    sorted_speeds = sorted(speed_map.keys())
    cumulative = 0.0
    result = []

    for speed in sorted_speeds:
        data = speed_map[speed]
        cumulative += data["total_weight"] * 100
        result.append({
            "speed": speed,
            "cumulative_outspeed_pct": round(cumulative, 1),
            "pokemon_at_speed": data["pokemon_at_speed"]
        })

    return result


def calculate_speed_creep_evs(
    your_base_speed: int,
    your_nature: str,
    target_base_speed: int,
    target_spreads: list[dict],
    desired_outspeed_pct: float = 100.0
) -> dict:
    """
    Calculate how many Speed EVs needed to outspeed a target percentage of spreads.

    This helps determine the minimum speed investment needed to outspeed
    a specific portion of a Pokemon's spread distribution.

    Args:
        your_base_speed: Your Pokemon's base speed
        your_nature: Your Pokemon's nature
        target_base_speed: Target's base speed
        target_spreads: Target's spread distribution from Smogon
        desired_outspeed_pct: Desired % of spreads to outspeed (0-100)

    Returns:
        Dict with recommended Speed EVs and resulting stats
    """
    if not target_spreads:
        return {
            "error": "No spread data available",
            "evs_needed": None
        }

    # Calculate all target speed stats
    target_speeds = []
    for spread in target_spreads:
        speed = parse_spread_to_speed(target_base_speed, spread)
        usage = spread.get("usage", 0)
        target_speeds.append({"speed": speed, "usage": usage})

    # Sort by speed ascending
    target_speeds.sort(key=lambda x: x["speed"])

    # Find the speed threshold for desired outspeed %
    cumulative_usage = 0
    threshold_speed = target_speeds[-1]["speed"] + 1  # Default: faster than all

    for entry in target_speeds:
        cumulative_usage += entry["usage"]
        remaining_usage = 100 - cumulative_usage
        if remaining_usage <= (100 - desired_outspeed_pct):
            threshold_speed = entry["speed"] + 1  # Need to be 1 faster
            break

    # Find minimum EVs to reach threshold speed (level 50 breakpoints)
    nature_mod = get_nature_speed_modifier(your_nature)

    for evs in EV_BREAKPOINTS_LV50:
        your_speed = calculate_speed_stat(your_base_speed, your_nature, evs)
        if your_speed >= threshold_speed:
            return {
                "evs_needed": evs,
                "resulting_speed": your_speed,
                "target_threshold_speed": threshold_speed,
                "actual_outspeed_pct": desired_outspeed_pct,
                "nature": your_nature,
                "analysis": f"{evs} Speed EVs ({your_nature}) reaches {your_speed} speed, outspeeding {desired_outspeed_pct:.0f}% of target spreads"
            }

    # Cannot achieve desired outspeed %
    max_speed = calculate_speed_stat(your_base_speed, your_nature, 252)
    actual_pct = 0
    for entry in target_speeds:
        if max_speed > entry["speed"]:
            actual_pct += entry["usage"]

    return {
        "evs_needed": 252,
        "resulting_speed": max_speed,
        "target_threshold_speed": threshold_speed,
        "actual_outspeed_pct": round(actual_pct, 1),
        "nature": your_nature,
        "cannot_achieve": True,
        "analysis": f"Max Speed ({max_speed} with 252 EVs) only outspeeds {actual_pct:.1f}% of target spreads. Consider a +Speed nature."
    }


def calculate_outspeed_from_distribution(
    your_speed: int,
    speed_distribution: list[dict],
    target_pokemon: str = "Target",
    target_base_speed: int = 0
) -> SpeedTierResult:
    """
    Calculate probability of outspeeding based on pre-calculated speed distribution.

    This uses the output from smogon.get_speed_distribution() which already has
    calculated final speeds with usage percentages.

    Args:
        your_speed: Your Pokemon's calculated speed stat
        speed_distribution: List of dicts from get_speed_distribution(), each with:
            - speed: int (final calculated speed stat)
            - usage: float (percentage 0-100)
        target_pokemon: Name of target Pokemon for display
        target_base_speed: Target Pokemon's base speed stat (for display)

    Returns:
        SpeedTierResult with outspeed/tie/underspeed probabilities (normalized to 100%)
    """
    if not speed_distribution:
        return SpeedTierResult(
            your_speed=your_speed,
            target_pokemon=target_pokemon,
            target_base_speed=target_base_speed,
            outspeed_probability=0.0,
            speed_tie_probability=0.0,
            underspeed_probability=100.0,
            target_speed_distribution=[],
            analysis=f"No spread data available for {target_pokemon}"
        )

    outspeed_total = 0.0
    tie_total = 0.0
    underspeed_total = 0.0

    target_speed_distribution = []

    for entry in speed_distribution:
        target_speed = entry.get("speed", 0)
        usage_pct = entry.get("usage", 0)

        speed_info = {
            "speed": target_speed,
            "usage_pct": usage_pct,
        }
        target_speed_distribution.append(speed_info)

        if your_speed > target_speed:
            outspeed_total += usage_pct
        elif your_speed == target_speed:
            tie_total += usage_pct
        else:
            underspeed_total += usage_pct

    # Sort distribution by speed (descending)
    target_speed_distribution.sort(key=lambda x: x["speed"], reverse=True)

    # Normalize to 100%
    total_usage = outspeed_total + tie_total + underspeed_total
    if total_usage > 0:
        outspeed_pct = (outspeed_total / total_usage) * 100
        tie_pct = (tie_total / total_usage) * 100
        underspeed_pct = (underspeed_total / total_usage) * 100
    else:
        outspeed_pct = 0.0
        tie_pct = 0.0
        underspeed_pct = 100.0

    # Generate analysis text
    if outspeed_pct >= 95:
        analysis = f"You outspeed virtually all {target_pokemon} spreads ({outspeed_pct:.1f}%)"
    elif outspeed_pct >= 75:
        analysis = f"You outspeed most {target_pokemon} spreads ({outspeed_pct:.1f}%)"
    elif outspeed_pct >= 50:
        analysis = f"Speed is contested - you outspeed {outspeed_pct:.1f}% of {target_pokemon}"
    elif outspeed_pct >= 25:
        analysis = f"Most {target_pokemon} outspeed you ({underspeed_pct:.1f}% faster)"
    else:
        analysis = f"Nearly all {target_pokemon} outspeed you ({underspeed_pct:.1f}%)"

    if tie_pct >= 5:
        analysis += f" - significant tie chance ({tie_pct:.1f}%)"

    return SpeedTierResult(
        your_speed=your_speed,
        target_pokemon=target_pokemon,
        target_base_speed=target_base_speed,
        outspeed_probability=round(outspeed_pct, 1),
        speed_tie_probability=round(tie_pct, 1),
        underspeed_probability=round(underspeed_pct, 1),
        target_speed_distribution=target_speed_distribution,
        analysis=analysis
    )
