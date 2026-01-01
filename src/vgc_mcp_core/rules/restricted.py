"""Restricted and banned Pokemon lists for VGC formats.

This module provides functions to check Pokemon restriction status,
using the unified regulation configuration from regulation_loader.
"""

from typing import Optional

from .regulation_loader import get_regulation_config


# Some Pokemon that are specifically allowed despite being legendary
# (Not restricted, can use as many as you want)
# This list is shared across all regulations
ALLOWED_LEGENDARIES = {
    # Legendary birds
    "articuno", "articuno-galar",
    "zapdos", "zapdos-galar",
    "moltres", "moltres-galar",

    # Legendary beasts
    "raikou", "entei", "suicune",

    # Regis
    "regirock", "regice", "registeel", "regigigas",
    "regieleki", "regidrago",

    # Lake trio
    "uxie", "mesprit", "azelf",

    # Swords of Justice
    "cobalion", "terrakion", "virizion",

    # Forces of Nature
    "tornadus", "tornadus-therian",
    "thundurus", "thundurus-therian",
    "landorus", "landorus-therian",
    "enamorus", "enamorus-therian",

    # Tapus
    "tapu-koko", "tapu-lele", "tapu-bulu", "tapu-fini",

    # Ultra Beasts
    "nihilego", "buzzwole", "pheromosa", "xurkitree",
    "celesteela", "kartana", "guzzlord",
    "poipole", "naganadel", "stakataka", "blacephalon",

    # Treasures of Ruin
    "wo-chien", "chien-pao", "ting-lu", "chi-yu",

    # Loyal Three
    "okidogi", "munkidori", "fezandipiti",
    "ogerpon", "ogerpon-wellspring", "ogerpon-hearthflame", "ogerpon-cornerstone",
}


def normalize_pokemon_name(name: str) -> str:
    """Normalize Pokemon name for comparison."""
    return name.lower().replace(" ", "-").replace("'", "").strip()


def is_restricted(pokemon_name: str, regulation: Optional[str] = None) -> bool:
    """
    Check if a Pokemon is restricted (box legend).

    Args:
        pokemon_name: Name of the Pokemon
        regulation: Regulation code (e.g., "reg_f"). Uses current if None.

    Returns:
        True if the Pokemon counts toward the restricted limit
    """
    config = get_regulation_config()
    restricted_set = config.get_restricted_pokemon(regulation)
    normalized = normalize_pokemon_name(pokemon_name)

    # Check exact match first
    if normalized in restricted_set:
        return True

    # Check base form (e.g., "calyrex-ice-rider" -> check "calyrex")
    base_name = normalized.split("-")[0]
    if base_name in restricted_set:
        return True

    return False


def is_banned(pokemon_name: str, regulation: Optional[str] = None) -> bool:
    """
    Check if a Pokemon is completely banned from VGC.

    Args:
        pokemon_name: Name of the Pokemon
        regulation: Regulation code (e.g., "reg_f"). Uses current if None.

    Returns:
        True if the Pokemon cannot be used at all
    """
    config = get_regulation_config()
    banned_set = config.get_banned_pokemon(regulation)
    normalized = normalize_pokemon_name(pokemon_name)

    # Check exact match first
    if normalized in banned_set:
        return True

    # Check base form
    base_name = normalized.split("-")[0]
    if base_name in banned_set:
        return True

    return False


def get_restricted_status(pokemon_name: str, regulation: Optional[str] = None) -> str:
    """
    Get the restriction status of a Pokemon.

    Args:
        pokemon_name: Name of the Pokemon
        regulation: Regulation code (e.g., "reg_f"). Uses current if None.

    Returns:
        "banned", "restricted", or "allowed"
    """
    if is_banned(pokemon_name, regulation):
        return "banned"
    if is_restricted(pokemon_name, regulation):
        return "restricted"
    return "allowed"


def get_pokemon_legality(pokemon_name: str, regulation: Optional[str] = None) -> dict:
    """
    Get detailed status of a Pokemon's legality.

    Args:
        pokemon_name: Name of the Pokemon
        regulation: Regulation code (e.g., "reg_f"). Uses current if None.

    Returns:
        Dict with restricted/banned status and details
    """
    config = get_regulation_config()
    reg = regulation or config.current_regulation
    normalized = normalize_pokemon_name(pokemon_name)

    if is_banned(normalized, regulation):
        return {
            "pokemon": pokemon_name,
            "status": "banned",
            "can_use": False,
            "counts_as_restricted": False,
            "reason": "Mythical Pokemon are banned from VGC",
            "regulation": reg
        }

    if is_restricted(normalized, regulation):
        limit = config.get_restricted_limit(regulation)
        return {
            "pokemon": pokemon_name,
            "status": "restricted",
            "can_use": True,
            "counts_as_restricted": True,
            "reason": f"Box Legend - counts toward restricted limit ({limit} allowed)",
            "regulation": reg
        }

    return {
        "pokemon": pokemon_name,
        "status": "allowed",
        "can_use": True,
        "counts_as_restricted": False,
        "reason": "Regular Pokemon with no restrictions",
        "regulation": reg
    }


def count_restricted(pokemon_names: list[str], regulation: Optional[str] = None) -> int:
    """
    Count how many restricted Pokemon are in a list.

    Args:
        pokemon_names: List of Pokemon names
        regulation: Regulation code (e.g., "reg_f"). Uses current if None.

    Returns:
        Number of restricted Pokemon found
    """
    count = 0
    for name in pokemon_names:
        if is_restricted(name, regulation):
            count += 1
    return count


def find_restricted(pokemon_names: list[str], regulation: Optional[str] = None) -> list[str]:
    """
    Find all restricted Pokemon in a list.

    Args:
        pokemon_names: List of Pokemon names
        regulation: Regulation code (e.g., "reg_f"). Uses current if None.

    Returns:
        List of restricted Pokemon names
    """
    return [name for name in pokemon_names if is_restricted(name, regulation)]


def find_banned(pokemon_names: list[str], regulation: Optional[str] = None) -> list[str]:
    """
    Find any banned Pokemon in a list.

    Args:
        pokemon_names: List of Pokemon names
        regulation: Regulation code (e.g., "reg_f"). Uses current if None.

    Returns:
        List of banned Pokemon found
    """
    return [name for name in pokemon_names if is_banned(name, regulation)]


def validate_restricted_limit(
    pokemon_names: list[str],
    regulation: Optional[str] = None
) -> dict:
    """
    Validate if a team meets the restricted Pokemon limit.

    Args:
        pokemon_names: List of Pokemon names
        regulation: Regulation code (e.g., "reg_f"). Uses current if None.

    Returns:
        Dict with validation result
    """
    config = get_regulation_config()
    limit = config.get_restricted_limit(regulation)
    restricted = find_restricted(pokemon_names, regulation)
    count = len(restricted)

    return {
        "valid": count <= limit,
        "count": count,
        "limit": limit,
        "restricted_pokemon": restricted,
        "message": (
            f"Team has {count}/{limit} restricted Pokemon"
            if count <= limit
            else f"Too many restricted Pokemon: {count}/{limit}"
        )
    }
