"""Speed comparison and tier utilities."""

from dataclasses import dataclass
from typing import Optional

from ..models.pokemon import Nature, PokemonBuild
from .stats import calculate_speed, calculate_all_stats, find_speed_evs
from ..config import EV_BREAKPOINTS_LV50


@dataclass
class SpeedComparison:
    """Result of comparing two Pokemon speeds."""
    pokemon1_name: str
    pokemon1_speed: int
    pokemon2_name: str
    pokemon2_speed: int
    difference: int
    result: str  # "pokemon1 outspeeds", "pokemon2 outspeeds", "speed tie"
    notes: list[str]


def compare_speeds(
    pokemon1: PokemonBuild,
    pokemon2: PokemonBuild,
    trick_room: bool = False,
    tailwind_pokemon1: bool = False,
    tailwind_pokemon2: bool = False,
    paralysis_pokemon1: bool = False,
    paralysis_pokemon2: bool = False,
) -> SpeedComparison:
    """
    Compare speeds between two Pokemon with modifiers.

    Args:
        pokemon1: First Pokemon
        pokemon2: Second Pokemon
        trick_room: If True, slower Pokemon moves first
        tailwind_pokemon1: If True, pokemon1 has 2x speed
        tailwind_pokemon2: If True, pokemon2 has 2x speed
        paralysis_pokemon1: If True, pokemon1 has 0.5x speed
        paralysis_pokemon2: If True, pokemon2 has 0.5x speed

    Returns:
        SpeedComparison with result and notes
    """
    stats1 = calculate_all_stats(pokemon1)
    stats2 = calculate_all_stats(pokemon2)

    speed1 = stats1["speed"]
    speed2 = stats2["speed"]

    notes = []

    # Apply modifiers
    effective_speed1 = speed1
    effective_speed2 = speed2

    if tailwind_pokemon1:
        effective_speed1 *= 2
        notes.append(f"{pokemon1.name} has Tailwind (2x)")

    if tailwind_pokemon2:
        effective_speed2 *= 2
        notes.append(f"{pokemon2.name} has Tailwind (2x)")

    if paralysis_pokemon1:
        effective_speed1 = int(effective_speed1 * 0.5)
        notes.append(f"{pokemon1.name} is paralyzed (0.5x)")

    if paralysis_pokemon2:
        effective_speed2 = int(effective_speed2 * 0.5)
        notes.append(f"{pokemon2.name} is paralyzed (0.5x)")

    # Determine result
    if trick_room:
        notes.append("Trick Room is active")
        if effective_speed1 < effective_speed2:
            result = f"{pokemon1.name} moves first (slower in Trick Room)"
        elif effective_speed2 < effective_speed1:
            result = f"{pokemon2.name} moves first (slower in Trick Room)"
        else:
            result = "Speed tie (50/50 in Trick Room)"
    else:
        if effective_speed1 > effective_speed2:
            result = f"{pokemon1.name} outspeeds {pokemon2.name}"
        elif effective_speed2 > effective_speed1:
            result = f"{pokemon2.name} outspeeds {pokemon1.name}"
        else:
            result = "Speed tie (50/50 chance)"

    return SpeedComparison(
        pokemon1_name=pokemon1.name,
        pokemon1_speed=speed1,
        pokemon2_name=pokemon2.name,
        pokemon2_speed=speed2,
        difference=abs(effective_speed1 - effective_speed2),
        result=result,
        notes=notes
    )


def find_speed_evs_to_outspeed(
    base_speed: int,
    target_speed: int,
    nature: Nature = Nature.SERIOUS,
    iv: int = 31,
    level: int = 50,
    by: int = 1
) -> Optional[int]:
    """
    Find minimum EVs to outspeed a target by at least 'by' points.

    Args:
        base_speed: Your Pokemon's base Speed
        target_speed: Target Speed stat to outspeed
        nature: Your Pokemon's nature
        iv: Speed IV
        level: Pokemon level
        by: Minimum points to outspeed by (default 1)

    Returns:
        Minimum EVs needed, or None if impossible
    """
    return find_speed_evs(base_speed, target_speed + by, nature, iv, level)


def find_speed_evs_to_underspeed(
    base_speed: int,
    target_speed: int,
    nature: Nature = Nature.SERIOUS,
    iv: int = 31,
    level: int = 50
) -> Optional[int]:
    """
    Find maximum EVs while staying slower than target (for Trick Room).

    Args:
        base_speed: Your Pokemon's base Speed
        target_speed: Target Speed stat to stay under
        nature: Your Pokemon's nature
        iv: Speed IV
        level: Pokemon level

    Returns:
        Maximum EVs while staying slower, or None if impossible
    """
    # Start from 252 and work down (level 50 breakpoints: 252, 244, 236...)
    for ev in reversed(EV_BREAKPOINTS_LV50):
        speed = calculate_speed(base_speed, iv, ev, level, nature)
        if speed < target_speed:
            return ev

    # Even 0 EVs is too fast, try 0 IV
    speed_0iv = calculate_speed(base_speed, 0, 0, level, nature)
    if speed_0iv < target_speed:
        return 0  # Need to use 0 IV

    return None  # Cannot underspeed


# Common speed benchmarks for VGC (updated for current meta)
SPEED_BENCHMARKS = {
    # Base speeds for quick reference
    "regieleki": {"base": 200, "max_positive": 277, "max_neutral": 252},
    "electrode-hisui": {"base": 150, "max_positive": 222, "max_neutral": 202},
    "dragapult": {"base": 142, "max_positive": 213, "max_neutral": 194},
    "iron-bundle": {"base": 136, "max_positive": 205, "max_neutral": 187},
    "flutter-mane": {"base": 135, "max_positive": 205, "max_neutral": 187},
    "miraidon": {"base": 135, "max_positive": 205, "max_neutral": 187},
    "koraidon": {"base": 135, "max_positive": 205, "max_neutral": 187},
    "raging-bolt": {"base": 91, "max_positive": 139, "max_neutral": 127},
    "chi-yu": {"base": 100, "max_positive": 152, "max_neutral": 138},
    "urshifu": {"base": 97, "max_positive": 148, "max_neutral": 135},
    "urshifu-rapid-strike": {"base": 97, "max_positive": 148, "max_neutral": 135},
    "palafin-hero": {"base": 100, "max_positive": 152, "max_neutral": 138},
    "tornadus": {"base": 111, "max_positive": 167, "max_neutral": 152},
    "landorus": {"base": 101, "max_positive": 154, "max_neutral": 140},
    "landorus-therian": {"base": 91, "max_positive": 139, "max_neutral": 127},
    "gholdengo": {"base": 84, "max_positive": 130, "max_neutral": 119},
    "rillaboom": {"base": 85, "max_positive": 132, "max_neutral": 120},
    "incineroar": {"base": 60, "neutral_0ev": 80, "min_negative": 58},
    "kingambit": {"base": 50, "neutral_0ev": 70, "min_negative": 49},
    "iron-hands": {"base": 50, "neutral_0ev": 70, "min_negative": 49},
    "amoonguss": {"base": 30, "neutral_0ev": 50, "min_negative": 31},
    "dondozo": {"base": 35, "neutral_0ev": 55, "min_negative": 36},
    "ting-lu": {"base": 45, "neutral_0ev": 65, "min_negative": 45},
}


def get_speed_tier_info(pokemon_name: str) -> Optional[dict]:
    """Get speed benchmark info for a Pokemon."""
    name = pokemon_name.lower().replace(" ", "-")
    return SPEED_BENCHMARKS.get(name)


def calculate_speed_tier(
    base_speed: int,
    nature: Nature,
    evs: int,
    iv: int = 31,
    level: int = 50
) -> dict:
    """
    Calculate speed tier information for a specific spread.

    Returns dict with speed stat and what it outspeeds/underspeeds.
    """
    speed = calculate_speed(base_speed, iv, evs, level, nature)

    outspeeds = []
    ties_with = []
    underspeeds = []

    for mon, data in SPEED_BENCHMARKS.items():
        if "max_positive" in data:
            if speed > data["max_positive"]:
                outspeeds.append(f"Max Speed {mon.replace('-', ' ').title()}")
            elif speed == data["max_positive"]:
                ties_with.append(f"Max Speed {mon.replace('-', ' ').title()}")

        if "max_neutral" in data:
            if speed > data["max_neutral"]:
                if speed <= data.get("max_positive", 999):
                    outspeeds.append(f"Neutral Speed {mon.replace('-', ' ').title()}")

        if "neutral_0ev" in data:
            if speed < data["neutral_0ev"]:
                underspeeds.append(f"Base {mon.replace('-', ' ').title()}")

    return {
        "speed": speed,
        "outspeeds": outspeeds[:5],  # Limit for readability
        "ties_with": ties_with,
        "underspeeds": underspeeds[:5],
    }
