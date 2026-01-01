"""Item clause validation for VGC formats."""

from typing import Optional
from collections import Counter


def normalize_item_name(item: str) -> str:
    """Normalize item name for comparison."""
    if not item:
        return ""
    return item.lower().replace(" ", "-").replace("'", "").strip()


def check_item_clause(items: list[Optional[str]]) -> dict:
    """
    Check if a team violates the item clause (no duplicate items).

    Args:
        items: List of held items (can include None for no item)

    Returns:
        Dict with validation result and any duplicates found
    """
    # Filter out None/empty items
    actual_items = [normalize_item_name(item) for item in items if item]

    # Count occurrences
    item_counts = Counter(actual_items)

    # Find duplicates
    duplicates = {item: count for item, count in item_counts.items() if count > 1}

    if duplicates:
        return {
            "valid": False,
            "violation": "item_clause",
            "duplicates": duplicates,
            "message": f"Item clause violation: {', '.join(f'{item} (x{count})' for item, count in duplicates.items())}"
        }

    return {
        "valid": True,
        "violation": None,
        "duplicates": {},
        "message": "No duplicate items found"
    }


def get_duplicate_items(items: list[Optional[str]]) -> list[str]:
    """
    Get list of items that appear more than once.

    Args:
        items: List of held items

    Returns:
        List of duplicate item names
    """
    actual_items = [normalize_item_name(item) for item in items if item]
    item_counts = Counter(actual_items)
    return [item for item, count in item_counts.items() if count > 1]


def suggest_alternative_items(current_item: str, pokemon_role: str = None) -> list[str]:
    """
    Suggest alternative items when there's a duplicate.

    Args:
        current_item: The item that's duplicated
        pokemon_role: Optional role hint (attacker, support, etc.)

    Returns:
        List of suggested alternative items
    """
    # Common competitive items by category
    OFFENSIVE_ITEMS = [
        "choice-band", "choice-specs", "choice-scarf",
        "life-orb", "expert-belt", "muscle-band", "wise-glasses",
        "assault-vest",
    ]

    DEFENSIVE_ITEMS = [
        "leftovers", "sitrus-berry", "assault-vest",
        "rocky-helmet", "safety-goggles", "shed-shell",
    ]

    UTILITY_ITEMS = [
        "focus-sash", "eject-button", "eject-pack",
        "covert-cloak", "clear-amulet", "mirror-herb",
    ]

    BERRIES = [
        "sitrus-berry", "lum-berry", "aguav-berry",
        "figy-berry", "wiki-berry", "mago-berry", "iapapa-berry",
    ]

    TERA_ITEMS = [
        "booster-energy",
    ]

    TYPE_ITEMS = [
        "charcoal", "mystic-water", "magnet", "miracle-seed",
        "never-melt-ice", "black-belt", "poison-barb", "soft-sand",
        "sharp-beak", "twisted-spoon", "silver-powder", "hard-stone",
        "spell-tag", "dragon-fang", "black-glasses", "metal-coat",
        "fairy-feather",
    ]

    normalized = normalize_item_name(current_item)

    # Collect all alternatives
    all_items = (
        OFFENSIVE_ITEMS + DEFENSIVE_ITEMS + UTILITY_ITEMS +
        BERRIES + TERA_ITEMS + TYPE_ITEMS
    )

    # Remove the current item from suggestions
    alternatives = [item for item in all_items if item != normalized]

    # If role is specified, prioritize relevant items
    if pokemon_role:
        role = pokemon_role.lower()
        if role in ["attacker", "offensive", "sweeper"]:
            # Put offensive items first
            offensive_set = set(OFFENSIVE_ITEMS)
            alternatives = (
                [i for i in alternatives if i in offensive_set] +
                [i for i in alternatives if i not in offensive_set]
            )
        elif role in ["support", "defensive", "tank"]:
            # Put defensive/utility items first
            support_set = set(DEFENSIVE_ITEMS + UTILITY_ITEMS)
            alternatives = (
                [i for i in alternatives if i in support_set] +
                [i for i in alternatives if i not in support_set]
            )

    return alternatives[:10]  # Return top 10 suggestions
