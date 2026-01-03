"""Synergy utilities for item-ability pairings and team synergy analysis."""

from typing import Optional

# Pre-normalized synergy dictionary for O(1) lookups
# Keys are lowercase with spaces (no hyphens/underscores)
ITEM_ABILITY_SYNERGIES: dict[str, list[str]] = {
    "life orb": ["sheer force"],  # Sheer Force cancels Life Orb recoil
    "choice band": ["huge power", "pure power", "gorilla tactics"],
    "choice specs": ["adaptability"],
    "assault vest": ["regenerator"],
    "rocky helmet": ["rough skin", "iron barbs"],
    "leftovers": ["regenerator", "poison heal"],
    "black sludge": ["regenerator", "poison heal"],
    "flame orb": ["guts", "marvel scale"],
    "toxic orb": ["poison heal", "guts", "marvel scale"],
    "booster energy": ["protosynthesis", "quark drive"],
}


def normalize_item_name(item: str) -> str:
    """Normalize item name for consistent lookup."""
    if not item:
        return ""
    return item.lower().replace("-", " ").replace("_", " ")


def normalize_ability_name(ability: str) -> str:
    """Normalize ability name for consistent lookup."""
    if not ability:
        return ""
    return ability.lower().replace("-", " ").replace("_", " ")


def get_synergy_ability(
    item: str, abilities: dict[str, float]
) -> tuple[Optional[str], float]:
    """Get the best ability to pair with an item based on known synergies.

    Args:
        item: The item being used
        abilities: Dict of ability_name -> usage_percent

    Returns:
        Tuple of (ability_name, usage_percent). Returns (None, 0) if no abilities.
    """
    if not abilities:
        return (None, 0)

    # Normalize item name for matching
    item_lower = normalize_item_name(item)

    # Check if this item has known synergies
    preferred_abilities = ITEM_ABILITY_SYNERGIES.get(item_lower, [])

    # Build normalized ability lookup for O(1) matching
    ability_lookup = {normalize_ability_name(name): (name, usage)
                      for name, usage in abilities.items()}

    for preferred in preferred_abilities:
        if preferred in ability_lookup:
            return ability_lookup[preferred]

    # No synergy found - return the most common ability
    top_ability = next(iter(abilities))
    return (top_ability, abilities[top_ability])


def has_item_ability_synergy(item: str, ability: str) -> bool:
    """Check if an item and ability have a known synergy.

    Args:
        item: The item name
        ability: The ability name

    Returns:
        True if the item and ability have a synergy, False otherwise.
    """
    item_lower = normalize_item_name(item)
    ability_lower = normalize_ability_name(ability)

    preferred = ITEM_ABILITY_SYNERGIES.get(item_lower, [])
    return ability_lower in preferred
