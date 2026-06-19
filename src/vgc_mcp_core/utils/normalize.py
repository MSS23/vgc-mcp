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

# Smogon API returns concatenated move names (e.g., "surgingstrikes" instead of
# "surging-strikes"). PokeAPI requires the hyphenated form. This is a curated
# list of the 200ish most-used VGC moves where the concatenation is ambiguous
# enough that a naive split won't work. Single-word moves (e.g. "protect",
# "psychic") pass through normalize_move() unchanged.
MOVE_ALIASES: dict[str, str] = {
    "surgingstrikes": "surging-strikes",
    "closecombat": "close-combat",
    "aquajet": "aqua-jet",
    "uturn": "u-turn",
    "voltswitch": "volt-switch",
    "knockoff": "knock-off",
    "earthpower": "earth-power",
    "earthquake": "earthquake",
    "fakeout": "fake-out",
    "rockslide": "rock-slide",
    "stoneedge": "stone-edge",
    "iceshard": "ice-shard",
    "icebeam": "ice-beam",
    "icicelance": "icicle-lance",
    "iciclespear": "icicle-spear",
    "iciclecrash": "icicle-crash",
    "icyshard": "icy-shard",
    "thunderwave": "thunder-wave",
    "thunderbolt": "thunderbolt",
    "thunderpunch": "thunder-punch",
    "wildcharge": "wild-charge",
    "shadowball": "shadow-ball",
    "shadowsneak": "shadow-sneak",
    "moonblast": "moonblast",
    "dazzlinggleam": "dazzling-gleam",
    "playrough": "play-rough",
    "drainingkiss": "draining-kiss",
    "fairyball": "fairy-ball",
    "energyball": "energy-ball",
    "leafstorm": "leaf-storm",
    "leafblade": "leaf-blade",
    "powerwhip": "power-whip",
    "hornleech": "horn-leech",
    "spore": "spore",
    "raining": "raining",
    "ragepowder": "rage-powder",
    "followme": "follow-me",
    "helpinghand": "helping-hand",
    "trickroom": "trick-room",
    "tailwind": "tailwind",
    "lightscreen": "light-screen",
    "reflect": "reflect",
    "auroraveil": "aurora-veil",
    "willowisp": "will-o-wisp",
    "stunspore": "stun-spore",
    "sleeppowder": "sleep-powder",
    "ragingfury": "raging-fury",
    "flareblitz": "flare-blitz",
    "sacredfire": "sacred-fire",
    "heatwave": "heat-wave",
    "flamethrower": "flamethrower",
    "fireblast": "fire-blast",
    "burningjealousy": "burning-jealousy",
    "burnup": "burn-up",
    "vcreate": "v-create",
    "extremespeed": "extreme-speed",
    "machpunch": "mach-punch",
    "drainpunch": "drain-punch",
    "focusblast": "focus-blast",
    "focuspunch": "focus-punch",
    "ironhead": "iron-head",
    "irondefense": "iron-defense",
    "bulletpunch": "bullet-punch",
    "sandsearstorm": "sandsear-storm",
    "wildboltstorm": "wildbolt-storm",
    "bleakwindstorm": "bleakwind-storm",
    "springtidestorm": "springtide-storm",
    "psychic": "psychic",
    "psyshock": "psyshock",
    "expandingforce": "expanding-force",
    "futuresight": "future-sight",
    "storedpower": "stored-power",
    "darkpulse": "dark-pulse",
    "knock": "knock-off",
    "suckerpunch": "sucker-punch",
    "wickedblow": "wicked-blow",
    "ruination": "ruination",
    "snarl": "snarl",
    "lashout": "lash-out",
    "throatchop": "throat-chop",
    "bittermalice": "bitter-malice",
    "spiritbreak": "spirit-break",
    "draconergy": "draco-meteor",
    "dracometeor": "draco-meteor",
    "dragonpulse": "dragon-pulse",
    "dragonclaw": "dragon-claw",
    "outrage": "outrage",
    "scaleshot": "scale-shot",
    "earthlypulse": "earth-power",
    "highhorsepower": "high-horsepower",
    "spikes": "spikes",
    "stealthrock": "stealth-rock",
    "ivycudgel": "ivy-cudgel",
    "matchacudgel": "matcha-cudgel",
    "syrupbomb": "syrup-bomb",
    "trickroom2": "trick-room",
    "calmmind": "calm-mind",
    "swordsdance": "swords-dance",
    "nastyplot": "nasty-plot",
    "dragondance": "dragon-dance",
    "tailglow": "tail-glow",
    "shellsmash": "shell-smash",
    "bodyslam": "body-slam",
    "doubleedge": "double-edge",
    "tripledive": "triple-dive",
    "headlongrush": "headlong-rush",
    "rockblast": "rock-blast",
    "rockwrecker": "rock-wrecker",
    "powerupperpunch": "power-up-punch",
    "ragefist": "rage-fist",
    "sappysneak": "sappy-sneak",
    "armorcannon": "armor-cannon",
    "torchsong": "torch-song",
    "kickofftherace": "kickoff",
    "skitterskat": "skitter-smack",
    "skitterhop": "skitter-smack",
    "tearfullook": "tearful-look",
    "tantrumstomp": "stomping-tantrum",
    "stompingtantrum": "stomping-tantrum",
    "voltdrive": "volt-tackle",
    "tachyoncutter": "tachyon-cutter",
    "tripleaxel": "triple-axel",
    "thousandwaves": "thousand-waves",
    "thousandarrows": "thousand-arrows",
    "spectralthief": "spectral-thief",
    "fierywrath": "fiery-wrath",
    "astralbarrage": "astral-barrage",
    "glaciallance": "glacial-lance",
    "blueflare": "blue-flare",
    "boltstrike": "bolt-strike",
    "secretpower": "secret-power",
    "ancientpower": "ancient-power",
    "weatherball": "weather-ball",
    "muddywater": "muddy-water",
    "originpulse": "origin-pulse",
    "precipiceblades": "precipice-blades",
    "freezedry": "freeze-dry",
    "tritreasure": "tri-attack",
    "triattack": "tri-attack",
    "hyperbeam": "hyper-beam",
    "gigaimpact": "giga-impact",
    "shellsidearm": "shell-side-arm",
    "icefang": "ice-fang",
    "firefang": "fire-fang",
    "thunderfang": "thunder-fang",
    "psychicfangs": "psychic-fangs",
    "powergem": "power-gem",
    "ironhead2": "iron-head",
    "headsmash": "head-smash",
    "filletaway": "filletaway",
    "trick": "trick",
    "switcheroo": "switcheroo",
    "encore": "encore",
    "taunt": "taunt",
    "disable": "disable",
    "haze": "haze",
    "topsyturvy": "topsy-turvy",
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


@lru_cache(maxsize=512)
def reorder_mega_prefix(name: str) -> str:
    """Rewrite a leading 'mega-<species>' into PokeAPI/Smogon's '<species>-mega'.

    PokeAPI keys and Smogon usage keys both order Mega forms with the 'Mega'
    suffix LAST ('manectric-mega', 'charizard-mega-y'), but users (and many
    tools) write the natural prefix order ('Mega Manectric', 'mega-charizard-y').
    This collapses that prefix order to the canonical suffix order, preserving a
    trailing '-x'/'-y' variant suffix. Names without a leading 'mega-' (including
    those already in '<species>-mega' order) pass through unchanged.

    Examples:
        "mega-manectric"   -> "manectric-mega"
        "mega-charizard-y" -> "charizard-mega-y"
        "manectric-mega"   -> "manectric-mega"  (unchanged)
        "manectric"        -> "manectric"       (unchanged)
    """
    if not name:
        return ""
    lower = name.lower().replace(" ", "-").replace("'", "").strip()
    if not lower.startswith("mega-"):
        return lower
    rest = lower[len("mega-"):]
    base = rest
    suffix = ""
    if rest.endswith(("-x", "-y")):
        base, suffix = rest[:-2], rest[-2:]
    return f"{base}-mega{suffix}"


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

    Handles three input shapes:
      - "Surging Strikes"    -> "surging-strikes"   (display)
      - "surgingstrikes"     -> "surging-strikes"   (Smogon concatenated)
      - "surging-strikes"    -> "surging-strikes"   (already canonical)

    Args:
        move: Move name in any common shape.

    Returns:
        Lowercase hyphenated form suitable for PokeAPI lookup.
    """
    if not move:
        return ""
    lower = move.lower().replace(" ", "-").replace("'", "").strip()
    # If already hyphenated, that's our canonical form. Otherwise the Smogon
    # concatenated variant might need an explicit alias.
    if "-" not in lower:
        return MOVE_ALIASES.get(lower, lower)
    return lower


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
