"""Name normalization utilities for consistent lookups.

All Pokemon-related names (moves, abilities, items, Pokemon names) should be
normalized to a consistent format for dictionary lookups.

Standard format: lowercase with hyphens (e.g., "life-orb", "sheer-force", "flare-blitz")

Handles Smogon API's concatenated format (e.g., "lifeorb" -> "life-orb").
"""

from functools import lru_cache


# Smogon API returns concatenated item names (e.g., "lifeorb")
# This maps them to hyphenated format for damage calc comparisons
ITEM_ALIASES: dict[str, str] = {
    "lifeorb": "life-orb",
    "choiceband": "choice-band",
    "choicespecs": "choice-specs",
    "choicescarf": "choice-scarf",
    "assaultvest": "assault-vest",
    "rockyhelmet": "rocky-helmet",
    "blacksludge": "black-sludge",
    "flameorb": "flame-orb",
    "toxicorb": "toxic-orb",
    "boosterenergy": "booster-energy",
    "focussash": "focus-sash",
    "sitrusberry": "sitrus-berry",
    "lumberry": "lum-berry",
    "clearamulet": "clear-amulet",
    "covertcloak": "covert-cloak",
    "safetygoggles": "safety-goggles",
    "mentalherb": "mental-herb",
    "powerherb": "power-herb",
    "ejectbutton": "eject-button",
    "ejectpack": "eject-pack",
    "expertbelt": "expert-belt",
    "scopelens": "scope-lens",
    "widelens": "wide-lens",
    "zoomlens": "zoom-lens",
    "airballoon": "air-balloon",
    "heavydutyboots": "heavy-duty-boots",
    "punchingglove": "punching-glove",
    "loadeddice": "loaded-dice",
    "mirrorherb": "mirror-herb",
    "redcard": "red-card",
    "weaknesspolicy": "weakness-policy",
    "whiteherb": "white-herb",
    "widelens": "wide-lens",
    "leftovers": "leftovers",  # already correct but included for completeness
}

# Smogon API returns concatenated ability names (e.g., "sheerforce")
# This maps them to hyphenated format for damage calc comparisons
ABILITY_ALIASES: dict[str, str] = {
    "sheerforce": "sheer-force",
    "hugepower": "huge-power",
    "purepower": "pure-power",
    "gorillatactics": "gorilla-tactics",
    "quarkdrive": "quark-drive",
    "protosynthesis": "protosynthesis",  # already correct
    "orichalcumpulse": "orichalcum-pulse",
    "hadronengine": "hadron-engine",
    "supremeoverlord": "supreme-overlord",
    "rockypayload": "rocky-payload",
    "strongjaw": "strong-jaw",
    "toughclaws": "tough-claws",
    "ironfist": "iron-fist",
    "sandforce": "sand-force",
    "adaptability": "adaptability",  # already correct
    "technician": "technician",  # already correct
    "unseenfist": "unseen-fist",
    "mindseye": "minds-eye",
    "embodyaspect": "embody-aspect",
    "terashell": "tera-shell",
    "purifyingsalt": "purifying-salt",
    "regenerator": "regenerator",  # already correct
    "intimidate": "intimidate",  # already correct
}


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

    Handles Smogon's concatenated format (e.g., "sheerforce" -> "sheer-force").

    Args:
        ability: Ability name

    Returns:
        Normalized ability name in hyphenated format
    """
    if not ability:
        return ""
    lower = ability.lower().replace(" ", "-").replace("'", "").strip()
    # Check for concatenated Smogon format
    concat = lower.replace("-", "")
    return ABILITY_ALIASES.get(concat, lower)


@lru_cache(maxsize=256)
def normalize_item(item: str) -> str:
    """Normalize item name for consistent lookups.

    Handles Smogon's concatenated format (e.g., "lifeorb" -> "life-orb").

    Args:
        item: Item name

    Returns:
        Normalized item name in hyphenated format
    """
    if not item:
        return ""
    lower = item.lower().replace(" ", "-").replace("_", "-").strip()
    # Check for concatenated Smogon format
    concat = lower.replace("-", "")
    return ITEM_ALIASES.get(concat, lower)


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
