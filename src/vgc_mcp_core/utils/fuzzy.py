"""Fuzzy matching utilities for Pokemon names, moves, and natures.

Provides "Did you mean...?" suggestions for typos and misspellings.
"""

from difflib import get_close_matches
from typing import Optional

from ..models.pokemon import Nature


# Common Pokemon names for fuzzy matching
# This is a subset of popular VGC Pokemon - can be expanded
COMMON_POKEMON = [
    # Restricted Pokemon
    "koraidon", "miraidon", "calyrex-shadow", "calyrex-ice", "zacian",
    "kyogre", "groudon", "rayquaza", "dialga", "palkia", "giratina",
    "reshiram", "zekrom", "kyurem", "xerneas", "yveltal", "lunala",
    "solgaleo", "necrozma", "eternatus", "terapagos",

    # Common VGC Pokemon (Reg F-H meta)
    "flutter-mane", "iron-hands", "iron-bundle", "iron-valiant", "iron-moth",
    "roaring-moon", "great-tusk", "iron-treads", "chi-yu", "chien-pao",
    "ting-lu", "wo-chien", "landorus-therian", "landorus", "incineroar",
    "rillaboom", "urshifu-rapid-strike", "urshifu-single-strike", "urshifu",
    "tornadus", "thundurus", "amoonguss", "grimmsnarl", "whimsicott",
    "dragapult", "garchomp", "tyranitar", "excadrill", "pelipper",
    "politoed", "kingambit", "gholdengo", "annihilape", "palafin",
    "arcanine", "arcanine-hisui", "ninetales-alola", "talonflame",
    "murkrow", "dondozo", "tatsugiri", "farigiraf", "indeedee-female",
    "indeedee", "gothitelle", "oranguru", "porygon2", "dusclops",
    "hatterene", "torkoal", "lilligant-hisui", "bronzong", "cresselia",
    "regieleki", "raging-bolt", "gouging-fire", "iron-crown", "iron-boulder",

    # Other common Pokemon
    "charizard", "venusaur", "blastoise", "pikachu", "mewtwo",
    "dragonite", "gyarados", "snorlax", "gengar", "alakazam",
    "machamp", "golem", "lapras", "eevee", "vaporeon", "jolteon",
    "flareon", "espeon", "umbreon", "sylveon", "leafeon", "glaceon",
    "salamence", "metagross", "lucario", "togekiss", "hydreigon",
    "volcarona", "mimikyu", "toxapex", "ferrothorn", "rotom-wash",
    "rotom-heat", "rotom", "clefable", "ditto", "smeargle",
]

# Common move names for fuzzy matching
COMMON_MOVES = [
    # Physical
    "close-combat", "earthquake", "rock-slide", "iron-head", "play-rough",
    "crunch", "knock-off", "u-turn", "fake-out", "sucker-punch",
    "extreme-speed", "aqua-jet", "ice-shard", "mach-punch", "bullet-punch",
    "brave-bird", "flare-blitz", "wild-charge", "wood-hammer", "head-smash",
    "stone-edge", "sacred-sword", "wicked-blow", "surging-strikes",

    # Special
    "moonblast", "dazzling-gleam", "shadow-ball", "psychic", "thunderbolt",
    "ice-beam", "flamethrower", "hydro-pump", "energy-ball", "earth-power",
    "sludge-bomb", "dark-pulse", "aura-sphere", "flash-cannon", "draco-meteor",
    "overheat", "leaf-storm", "volt-switch", "scald", "heat-wave",
    "muddy-water", "icy-wind", "snarl", "electroweb",

    # Status/Support
    "protect", "detect", "follow-me", "rage-powder", "ally-switch",
    "trick-room", "tailwind", "helping-hand", "fake-out", "spore",
    "sleep-powder", "thunder-wave", "will-o-wisp", "taunt", "encore",
    "disable", "imprison", "safeguard", "light-screen", "reflect",
    "aurora-veil", "stealth-rock", "spikes", "toxic-spikes", "sticky-web",
    "swords-dance", "dragon-dance", "calm-mind", "nasty-plot", "quiver-dance",
    "substitute", "endure", "wide-guard", "quick-guard", "crafty-shield",
]


def suggest_pokemon_name(
    input_name: str,
    max_suggestions: int = 3,
    cutoff: float = 0.6
) -> list[str]:
    """
    Find similar Pokemon names for typo correction.

    Args:
        input_name: The misspelled/unknown Pokemon name
        max_suggestions: Maximum number of suggestions to return
        cutoff: Minimum similarity threshold (0-1)

    Returns:
        List of similar Pokemon names, ordered by similarity

    Example:
        >>> suggest_pokemon_name("Charzard")
        ['charizard']
        >>> suggest_pokemon_name("flutter mane")
        ['flutter-mane']
        >>> suggest_pokemon_name("landorus therian")
        ['landorus-therian']
    """
    # Normalize input
    normalized = input_name.lower().strip()

    # Try direct normalization first (spaces -> hyphens)
    hyphenated = normalized.replace(" ", "-")
    if hyphenated in COMMON_POKEMON:
        return [hyphenated]

    # Try without hyphens
    dehyphenated = normalized.replace("-", "")
    for pokemon in COMMON_POKEMON:
        if pokemon.replace("-", "") == dehyphenated:
            return [pokemon]

    # Use fuzzy matching
    matches = get_close_matches(
        normalized,
        COMMON_POKEMON,
        n=max_suggestions,
        cutoff=cutoff
    )

    # Also try matching against hyphenated version
    if not matches:
        matches = get_close_matches(
            hyphenated,
            COMMON_POKEMON,
            n=max_suggestions,
            cutoff=cutoff
        )

    return matches


def suggest_nature(
    input_nature: str,
    max_suggestions: int = 3
) -> list[str]:
    """
    Find similar nature names for typo correction.

    Args:
        input_nature: The misspelled nature name
        max_suggestions: Maximum number of suggestions

    Returns:
        List of similar nature names

    Example:
        >>> suggest_nature("Adament")
        ['adamant']
        >>> suggest_nature("timmid")
        ['timid']
    """
    valid_natures = [n.value for n in Nature]
    normalized = input_nature.lower().strip()

    # Direct match check
    if normalized in valid_natures:
        return [normalized]

    return get_close_matches(
        normalized,
        valid_natures,
        n=max_suggestions,
        cutoff=0.6
    )


def suggest_move_name(
    input_move: str,
    max_suggestions: int = 3,
    cutoff: float = 0.6
) -> list[str]:
    """
    Find similar move names for typo correction.

    Args:
        input_move: The misspelled move name
        max_suggestions: Maximum number of suggestions
        cutoff: Minimum similarity threshold

    Returns:
        List of similar move names

    Example:
        >>> suggest_move_name("earthquack")
        ['earthquake']
        >>> suggest_move_name("close combat")
        ['close-combat']
    """
    normalized = input_move.lower().strip()

    # Try hyphenated version first
    hyphenated = normalized.replace(" ", "-")
    if hyphenated in COMMON_MOVES:
        return [hyphenated]

    # Try without hyphens
    dehyphenated = normalized.replace("-", "").replace(" ", "")
    for move in COMMON_MOVES:
        if move.replace("-", "") == dehyphenated:
            return [move]

    # Fuzzy match
    matches = get_close_matches(
        normalized,
        COMMON_MOVES,
        n=max_suggestions,
        cutoff=cutoff
    )

    if not matches:
        matches = get_close_matches(
            hyphenated,
            COMMON_MOVES,
            n=max_suggestions,
            cutoff=cutoff
        )

    return matches


def format_suggestions(suggestions: list[str], prefix: str = "Did you mean") -> str:
    """
    Format a list of suggestions into a readable string.

    Args:
        suggestions: List of suggested values
        prefix: Prefix for the suggestion message

    Returns:
        Formatted suggestion string

    Example:
        >>> format_suggestions(["charizard", "charmeleon"])
        "Did you mean: charizard, charmeleon?"
    """
    if not suggestions:
        return ""

    if len(suggestions) == 1:
        return f"{prefix}: {suggestions[0]}?"

    return f"{prefix}: {', '.join(suggestions)}?"
