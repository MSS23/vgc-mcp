"""Name normalization utilities for consistent lookups.

All Pokemon-related names (moves, abilities, items, Pokemon names) should be
normalized to a consistent format for dictionary lookups.

Standard format: lowercase with hyphens (e.g., "life-orb", "sheer-force", "flare-blitz")
"""

from functools import lru_cache


@lru_cache(maxsize=1024)
def normalize_name(name: str) -> str:
    """Normalize any Pokemon-related name to lowercase hyphenated format.

    Handles spaces, underscores, and apostrophes. Results are cached for performance.

    Examples:
        "Life Orb" -> "life-orb"
        "Sheer Force" -> "sheer-force"
        "Flare Blitz" -> "flare-blitz"
        "King's Rock" -> "kings-rock"

    Args:
        name: The name to normalize (move, ability, item, or Pokemon name)

    Returns:
        Normalized lowercase hyphenated string
    """
    if not name:
        return ""
    return name.lower().replace(" ", "-").replace("_", "-").replace("'", "").strip()


@lru_cache(maxsize=512)
def normalize_pokemon_name(name: str) -> str:
    """Normalize Pokemon name to lowercase hyphenated format.

    Same as normalize_name but with a separate cache for Pokemon names.

    Args:
        name: Pokemon name

    Returns:
        Normalized Pokemon name
    """
    if not name:
        return ""
    return name.lower().replace(" ", "-").replace("_", "-").strip()


@lru_cache(maxsize=256)
def normalize_ability(ability: str) -> str:
    """Normalize ability name for consistent lookups.

    Args:
        ability: Ability name

    Returns:
        Normalized ability name
    """
    if not ability:
        return ""
    return ability.lower().replace(" ", "-").replace("'", "").strip()


@lru_cache(maxsize=256)
def normalize_item(item: str) -> str:
    """Normalize item name for consistent lookups.

    Args:
        item: Item name

    Returns:
        Normalized item name
    """
    if not item:
        return ""
    return item.lower().replace(" ", "-").replace("_", "-").strip()


@lru_cache(maxsize=512)
def normalize_move(move: str) -> str:
    """Normalize move name for consistent lookups.

    Args:
        move: Move name

    Returns:
        Normalized move name
    """
    if not move:
        return ""
    return move.lower().replace(" ", "-").replace("'", "").strip()


def clear_caches():
    """Clear all normalization caches. Useful for testing."""
    normalize_name.cache_clear()
    normalize_pokemon_name.cache_clear()
    normalize_ability.cache_clear()
    normalize_item.cache_clear()
    normalize_move.cache_clear()
