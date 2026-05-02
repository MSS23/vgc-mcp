"""Mega Evolution form lookup — base ability vs. mega ability swap.

When a base species mega-evolves it switches to a single fixed ability
(e.g. Manectric → Mega Manectric is Static/Lightning Rod → Intimidate).
The damage calc must use the post-mega ability when computing matchups
or it silently misses Intimidate's -1 Atk drop.

This is the canonical lookup. Use `get_mega_ability(name)` whenever you
have a Mega-form Pokemon and need its battle ability.
"""

from __future__ import annotations

# Mega form -> the single ability the form has after mega-evolving.
# Source: Bulbapedia / official Pokémon data, normalised to lowercase
# hyphen-form. Names match `pokeapi._normalize_name()` output.
MEGA_FORM_ABILITY: dict[str, str] = {
    "venusaur-mega": "Thick Fat",
    "charizard-mega-x": "Tough Claws",
    "charizard-mega-y": "Drought",
    "blastoise-mega": "Mega Launcher",
    "beedrill-mega": "Adaptability",
    "pidgeot-mega": "No Guard",
    "alakazam-mega": "Trace",
    "slowbro-mega": "Shell Armor",
    "gengar-mega": "Shadow Tag",
    "kangaskhan-mega": "Parental Bond",
    "pinsir-mega": "Aerilate",
    "gyarados-mega": "Mold Breaker",
    "aerodactyl-mega": "Tough Claws",
    "mewtwo-mega-x": "Steadfast",
    "mewtwo-mega-y": "Insomnia",
    "mewtwo-mega": "Insomnia",  # default Mega Y if unspecified
    "ampharos-mega": "Mold Breaker",
    "steelix-mega": "Sand Force",
    "scizor-mega": "Technician",
    "heracross-mega": "Skill Link",
    "houndoom-mega": "Solar Power",
    "tyranitar-mega": "Sand Stream",
    "sceptile-mega": "Lightning Rod",
    "blaziken-mega": "Speed Boost",
    "swampert-mega": "Swift Swim",
    "gardevoir-mega": "Pixilate",
    "sableye-mega": "Magic Bounce",
    "mawile-mega": "Huge Power",
    "aggron-mega": "Filter",
    "medicham-mega": "Pure Power",
    "manectric-mega": "Intimidate",
    "sharpedo-mega": "Strong Jaw",
    "camerupt-mega": "Sheer Force",
    "altaria-mega": "Pixilate",
    "banette-mega": "Prankster",
    "absol-mega": "Magic Bounce",
    "glalie-mega": "Refrigerate",
    "salamence-mega": "Aerilate",
    "metagross-mega": "Tough Claws",
    "latias-mega": "Levitate",
    "latios-mega": "Levitate",
    "rayquaza-mega": "Delta Stream",
    "lopunny-mega": "Scrappy",
    "garchomp-mega": "Sand Force",
    "lucario-mega": "Adaptability",
    "abomasnow-mega": "Snow Warning",
    "gallade-mega": "Inner Focus",
    "audino-mega": "Healer",
    "diancie-mega": "Magic Bounce",
}


def get_mega_ability(pokemon_name: str) -> str | None:
    """Return the ability of a Mega form, or None if not a Mega.

    `pokemon_name` should be the canonical hyphen-form (e.g.
    `manectric-mega`, `charizard-mega-y`). Match is case-insensitive
    and tolerates the `mega-` prefix shape too.
    """
    if not pokemon_name:
        return None
    n = pokemon_name.lower().strip().replace(" ", "-")
    if n in MEGA_FORM_ABILITY:
        return MEGA_FORM_ABILITY[n]
    if n.startswith("mega-"):
        rest = n[len("mega-"):]
        # Mega Charizard X / Mega Mewtwo Y -> charizard-mega-x
        suffix = ""
        base = rest
        if rest.endswith(("-x", "-y")):
            base, suffix = rest[:-2], rest[-2:]
        canonical = f"{base}-mega{suffix}"
        if canonical in MEGA_FORM_ABILITY:
            return MEGA_FORM_ABILITY[canonical]
    return None


def is_mega_form(pokemon_name: str) -> bool:
    """True if the name resolves to a Mega-form species."""
    return get_mega_ability(pokemon_name) is not None
