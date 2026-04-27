"""Name normalization utilities for consistent lookups.

All Pokemon-related names (moves, abilities, items, Pokemon names) should be
normalized to a consistent format for dictionary lookups.

Standard format: lowercase with hyphens (e.g., "life-orb", "sheer-force", "flare-blitz")

Handles Smogon API's concatenated format (e.g., "lifeorb" -> "life-orb").

This is the single canonical normalization module — DO NOT re-implement these
functions per-file. Import from here:

    from vgc_mcp_core.utils.normalize import (
        normalize_name, normalize_pokemon_name,
        normalize_move, normalize_ability, normalize_item,
        ITEM_ALIASES, ABILITY_ALIASES,
    )
"""

from functools import lru_cache


# Smogon API returns concatenated item names (e.g., "lifeorb")
# This maps them to hyphenated format for damage calc comparisons.
ITEM_ALIASES: dict[str, str] = {
    # Choice items
    "lifeorb": "life-orb",
    "choiceband": "choice-band",
    "choicespecs": "choice-specs",
    "choicescarf": "choice-scarf",
    "assaultvest": "assault-vest",
    # Defensive items
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
    # Coverage / utility
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
    "throatspray": "throat-spray",
    "leftovers": "leftovers",
    "eviolite": "eviolite",
    # Ogerpon masks
    "hearthflamemask": "hearthflame-mask",
    "wellspringmask": "wellspring-mask",
    "cornerstonemask": "cornerstone-mask",
    # Resistance berries
    "occaberry": "occa-berry",
    "passhoberry": "passho-berry",
    "wacanberry": "wacan-berry",
    "rindoberry": "rindo-berry",
    "yacheberry": "yache-berry",
    "chopleberry": "chople-berry",
    "kebiaberry": "kebia-berry",
    "shucaberry": "shuca-berry",
    "cobaberry": "coba-berry",
    "payapaberry": "payapa-berry",
    "tangaberry": "tanga-berry",
    "chartiberry": "charti-berry",
    "kasibberry": "kasib-berry",
    "habanberry": "haban-berry",
    "colburberry": "colbur-berry",
    "babiriberry": "babiri-berry",
    "roseliberry": "roseli-berry",
}

# Smogon API returns concatenated ability names (e.g., "sheerforce")
# This maps them to hyphenated format for damage calc comparisons.
ABILITY_ALIASES: dict[str, str] = {
    # Offensive
    "sheerforce": "sheer-force",
    "sandforce": "sand-force",
    "hugepower": "huge-power",
    "purepower": "pure-power",
    "gorillatactics": "gorilla-tactics",
    "toughclaws": "tough-claws",
    "ironfist": "iron-fist",
    "strongjaw": "strong-jaw",
    "rockypayload": "rocky-payload",
    "supremeoverlord": "supreme-overlord",
    "orichalcumpulse": "orichalcum-pulse",
    "hadronengine": "hadron-engine",
    "unseenfist": "unseen-fist",
    "mindseye": "minds-eye",
    "embodyaspect": "embody-aspect",
    # Type-changing (-ate)
    "pixilate": "pixilate",
    "refrigerate": "refrigerate",
    "galvanize": "galvanize",
    "aerilate": "aerilate",
    # Paradox
    "quarkdrive": "quark-drive",
    "protosynthesis": "protosynthesis",
    # Ruin
    "swordofruin": "sword-of-ruin",
    "beadsofruin": "beads-of-ruin",
    "tabletsofruin": "tablets-of-ruin",
    "vesselofruin": "vessel-of-ruin",
    # Defensive
    "multiscale": "multiscale",
    "shadowshield": "shadow-shield",
    "icescales": "ice-scales",
    "solidrock": "solid-rock",
    "filter": "filter",
    "prismarmor": "prism-armor",
    "fluffy": "fluffy",
    "thickfat": "thick-fat",
    "furcoat": "fur-coat",
    "waterbubble": "water-bubble",
    "heatproof": "heatproof",
    "purifyingsalt": "purifying-salt",
    "terashell": "tera-shell",
    "friendguard": "friend-guard",
    # Common utility
    "intimidate": "intimidate",
    "moldbreaker": "mold-breaker",
    "teravolt": "teravolt",
    "turboblaze": "turboblaze",
    "clearbody": "clear-body",
    "innerfocus": "inner-focus",
    "regenerator": "regenerator",
    "magicguard": "magic-guard",
    "magicbounce": "magic-bounce",
    "prankster": "prankster",
    "technician": "technician",
    "adaptability": "adaptability",
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
        Normalized move name (lowercase, hyphenated, no apostrophes)
    """
    if not move:
        return ""
    return move.lower().replace(" ", "-").replace("'", "").strip()


# Backwards-compatible alias — some older modules imported this name.
# Prefer normalize_move in new code.
normalize_move_name = normalize_move


def normalize_smogon_name(name: str) -> str:
    """Normalize Smogon's concatenated names (items + abilities) to hyphenated format.

    Smogon API uses concatenated names ("lifeorb", "sheerforce") while damage
    calc expects hyphenated ("life-orb", "sheer-force"). This checks both
    ITEM_ALIASES and ABILITY_ALIASES.

    Args:
        name: Smogon-style name (concatenated or already hyphenated)

    Returns:
        Hyphenated name suitable for damage calc lookup
    """
    if not name:
        return ""
    name_lower = name.lower().replace(" ", "-").strip()
    concat = name_lower.replace("-", "")
    return ITEM_ALIASES.get(concat) or ABILITY_ALIASES.get(concat) or name_lower


def clear_caches():
    """Clear all normalization caches. Useful for testing."""
    normalize_name.cache_clear()
    normalize_pokemon_name.cache_clear()
    normalize_ability.cache_clear()
    normalize_item.cache_clear()
    normalize_move.cache_clear()
