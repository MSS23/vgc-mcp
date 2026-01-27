"""Pokemon Showdown paste format parser and exporter.

Showdown paste format example:
```
Nickname (Urshifu-Rapid-Strike) (M) @ Choice Scarf
Ability: Unseen Fist
Level: 50
Shiny: Yes
Tera Type: Water
EVs: 4 HP / 252 Atk / 252 Spe
Jolly Nature
IVs: 0 SpA
- Surging Strikes
- Close Combat
- U-turn
- Aqua Jet
```

Minimal format:
```
Urshifu-Rapid-Strike @ Choice Scarf
Ability: Unseen Fist
EVs: 252 Atk / 252 Spe
Jolly Nature
- Surging Strikes
- Close Combat
- U-turn
- Aqua Jet
```
"""

import re
from typing import Optional
from dataclasses import dataclass, field

from ..models.pokemon import Nature, EVSpread, IVSpread, PokemonBuild


class ShowdownParseError(Exception):
    """Error parsing Showdown paste."""
    pass


@dataclass
class ParsedPokemon:
    """Parsed Pokemon data from Showdown format."""
    species: str
    nickname: Optional[str] = None
    gender: Optional[str] = None  # "M" or "F"
    item: Optional[str] = None
    ability: Optional[str] = None
    level: int = 50
    shiny: bool = False
    tera_type: Optional[str] = None
    evs: dict = field(default_factory=lambda: {
        "hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0
    })
    ivs: dict = field(default_factory=lambda: {
        "hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31
    })
    nature: str = "Serious"
    moves: list = field(default_factory=list)
    happiness: int = 255
    pokeball: Optional[str] = None
    hidden_power_type: Optional[str] = None


# Stat name mappings
STAT_NAMES = {
    "hp": "hp", "HP": "hp",
    "atk": "atk", "Atk": "atk", "attack": "atk", "Attack": "atk",
    "def": "def", "Def": "def", "defense": "def", "Defense": "def",
    "spa": "spa", "SpA": "spa", "spatk": "spa", "Sp. Atk": "spa",
    "special attack": "spa", "Special Attack": "spa",
    "spd": "spd", "SpD": "spd", "spdef": "spd", "Sp. Def": "spd",
    "special defense": "spd", "Special Defense": "spd",
    "spe": "spe", "Spe": "spe", "speed": "spe", "Speed": "spe",
}

# Reverse mapping for export
STAT_EXPORT_NAMES = {
    "hp": "HP", "atk": "Atk", "def": "Def",
    "spa": "SpA", "spd": "SpD", "spe": "Spe"
}


def parse_showdown_pokemon(paste: str) -> ParsedPokemon:
    """
    Parse a single Pokemon from Showdown paste format.

    Args:
        paste: The paste text for one Pokemon

    Returns:
        ParsedPokemon with all parsed fields

    Raises:
        ShowdownParseError: If parsing fails
    """
    lines = [line.strip() for line in paste.strip().split("\n") if line.strip()]

    if not lines:
        raise ShowdownParseError("Empty paste")

    pokemon = ParsedPokemon(species="")

    # Parse first line: [Nickname] (Species) [(Gender)] @ Item
    # Or just: Species @ Item
    first_line = lines[0]

    # Check for item
    if " @ " in first_line:
        name_part, pokemon.item = first_line.rsplit(" @ ", 1)
    else:
        name_part = first_line

    # Parse name/nickname/gender
    # Patterns:
    # "Nickname (Species) (M)" - nickname with gender
    # "Nickname (Species)" - nickname without gender
    # "Species (M)" - species with gender
    # "Species" - just species

    # Check for gender at end
    gender_match = re.search(r'\s+\(([MF])\)\s*$', name_part)
    if gender_match:
        pokemon.gender = gender_match.group(1)
        name_part = name_part[:gender_match.start()].strip()

    # Check for nickname (Species) pattern
    nickname_match = re.match(r'^(.+?)\s+\(([^)]+)\)\s*$', name_part)
    if nickname_match:
        pokemon.nickname = nickname_match.group(1).strip()
        pokemon.species = nickname_match.group(2).strip()
    else:
        pokemon.species = name_part.strip()

    # Parse remaining lines
    for line in lines[1:]:
        line_lower = line.lower()

        if line_lower.startswith("ability:"):
            pokemon.ability = line.split(":", 1)[1].strip()

        elif line_lower.startswith("level:"):
            try:
                pokemon.level = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass

        elif line_lower.startswith("shiny:"):
            pokemon.shiny = line.split(":", 1)[1].strip().lower() == "yes"

        elif line_lower.startswith("tera type:"):
            pokemon.tera_type = line.split(":", 1)[1].strip()

        elif line_lower.startswith("happiness:"):
            try:
                pokemon.happiness = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass

        elif line_lower.startswith("pokeball:"):
            pokemon.pokeball = line.split(":", 1)[1].strip()

        elif line_lower.startswith("hidden power:"):
            pokemon.hidden_power_type = line.split(":", 1)[1].strip()

        elif line_lower.startswith("evs:"):
            pokemon.evs = _parse_stat_spread(line.split(":", 1)[1])

        elif line_lower.startswith("ivs:"):
            # IVs default to 31, only override stats that are explicitly specified
            iv_spread = _parse_stat_spread_sparse(line.split(":", 1)[1])
            for stat, value in iv_spread.items():
                pokemon.ivs[stat] = value

        elif line_lower.endswith(" nature"):
            pokemon.nature = line.rsplit(" ", 1)[0].strip()

        elif line.startswith("-") or line.startswith("–"):
            move = line.lstrip("-–").strip()
            if move and len(pokemon.moves) < 4:
                pokemon.moves.append(move)

    if not pokemon.species:
        raise ShowdownParseError("Could not parse Pokemon species")

    return pokemon


def _parse_stat_spread(spread_str: str) -> dict:
    """Parse stat spread string like '252 Atk / 252 Spe / 4 HP'.

    Returns a dict with all stats, defaulting unspecified ones to 0.
    """
    stats = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}

    parts = spread_str.split("/")
    for part in parts:
        part = part.strip()
        if not part:
            continue

        match = re.match(r'(\d+)\s+(.+)', part)
        if match:
            value = int(match.group(1))
            stat_name = match.group(2).strip()

            # Normalize stat name
            normalized = STAT_NAMES.get(stat_name)
            if normalized:
                stats[normalized] = value

    return stats


def _parse_stat_spread_sparse(spread_str: str) -> dict:
    """Parse stat spread string, returning only specified stats.

    Unlike _parse_stat_spread, this doesn't fill in defaults.
    Used for IVs where unspecified stats should keep their default of 31.
    """
    stats = {}

    parts = spread_str.split("/")
    for part in parts:
        part = part.strip()
        if not part:
            continue

        match = re.match(r'(\d+)\s+(.+)', part)
        if match:
            value = int(match.group(1))
            stat_name = match.group(2).strip()

            # Normalize stat name
            normalized = STAT_NAMES.get(stat_name)
            if normalized:
                stats[normalized] = value

    return stats


def parse_showdown_team(paste: str) -> list[ParsedPokemon]:
    """
    Parse a full team from Showdown paste format.

    Pokemon are separated by blank lines.

    Args:
        paste: The full team paste

    Returns:
        List of ParsedPokemon (up to 6)

    Raises:
        ShowdownParseError: If parsing fails
    """
    # Split by double newlines (blank lines between Pokemon)
    pokemon_blocks = re.split(r'\n\s*\n', paste.strip())

    team = []
    for block in pokemon_blocks:
        block = block.strip()
        if not block:
            continue

        try:
            pokemon = parse_showdown_pokemon(block)
            team.append(pokemon)

            if len(team) >= 6:
                break
        except ShowdownParseError:
            # Skip unparseable blocks
            continue

    return team


def export_pokemon_to_showdown(
    species: str,
    nickname: Optional[str] = None,
    gender: Optional[str] = None,
    item: Optional[str] = None,
    ability: Optional[str] = None,
    level: int = 50,
    shiny: bool = False,
    tera_type: Optional[str] = None,
    evs: Optional[dict] = None,
    ivs: Optional[dict] = None,
    nature: str = "Serious",
    moves: Optional[list] = None,
) -> str:
    """
    Export a Pokemon to Showdown paste format.

    Args:
        species: Pokemon species name
        nickname: Optional nickname
        gender: Optional gender ("M" or "F")
        item: Held item
        ability: Pokemon ability
        level: Pokemon level
        shiny: Whether shiny
        tera_type: Tera type
        evs: EV spread dict
        ivs: IV spread dict
        nature: Nature name
        moves: List of move names

    Returns:
        Showdown paste format string
    """
    lines = []

    # First line: [Nickname (]Species[)] [(Gender)] [@ Item]
    first_line = ""

    if nickname:
        first_line = f"{nickname} ({species})"
    else:
        first_line = species

    if gender:
        first_line += f" ({gender})"

    if item:
        first_line += f" @ {item}"

    lines.append(first_line)

    # Ability
    if ability:
        lines.append(f"Ability: {ability}")

    # Level (only if not 50)
    if level != 50:
        lines.append(f"Level: {level}")

    # Shiny
    if shiny:
        lines.append("Shiny: Yes")

    # Tera Type
    if tera_type:
        lines.append(f"Tera Type: {tera_type}")

    # EVs
    if evs:
        ev_parts = []
        for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
            if evs.get(stat, 0) > 0:
                ev_parts.append(f"{evs[stat]} {STAT_EXPORT_NAMES[stat]}")

        if ev_parts:
            lines.append(f"EVs: {' / '.join(ev_parts)}")

    # Nature
    lines.append(f"{nature} Nature")

    # IVs (only non-31 values)
    if ivs:
        iv_parts = []
        for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
            if ivs.get(stat, 31) != 31:
                iv_parts.append(f"{ivs[stat]} {STAT_EXPORT_NAMES[stat]}")

        if iv_parts:
            lines.append(f"IVs: {' / '.join(iv_parts)}")

    # Moves
    if moves:
        for move in moves[:4]:
            lines.append(f"- {move}")

    return "\n".join(lines)


def export_team_to_showdown(team: list[dict]) -> str:
    """
    Export a full team to Showdown paste format.

    Args:
        team: List of Pokemon dicts with keys matching export_pokemon_to_showdown args

    Returns:
        Full team paste with blank lines between Pokemon
    """
    pokemon_pastes = []

    for pokemon in team[:6]:
        paste = export_pokemon_to_showdown(**pokemon)
        pokemon_pastes.append(paste)

    return "\n\n".join(pokemon_pastes)


def parsed_to_ev_spread(parsed: ParsedPokemon) -> EVSpread:
    """Convert ParsedPokemon EVs to EVSpread model."""
    return EVSpread(
        hp=parsed.evs.get("hp", 0),
        attack=parsed.evs.get("atk", 0),
        defense=parsed.evs.get("def", 0),
        special_attack=parsed.evs.get("spa", 0),
        special_defense=parsed.evs.get("spd", 0),
        speed=parsed.evs.get("spe", 0),
    )


def parsed_to_iv_spread(parsed: ParsedPokemon) -> IVSpread:
    """Convert ParsedPokemon IVs to IVSpread model."""
    return IVSpread(
        hp=parsed.ivs.get("hp", 31),
        attack=parsed.ivs.get("atk", 31),
        defense=parsed.ivs.get("def", 31),
        special_attack=parsed.ivs.get("spa", 31),
        special_defense=parsed.ivs.get("spd", 31),
        speed=parsed.ivs.get("spe", 31),
    )


def parsed_to_nature(parsed: ParsedPokemon) -> Nature:
    """Convert ParsedPokemon nature string to Nature enum."""
    try:
        return Nature(parsed.nature.lower())
    except ValueError:
        return Nature.SERIOUS


def pokemon_build_to_showdown(pokemon: PokemonBuild) -> str:
    """
    Convert a PokemonBuild model to Showdown paste format.
    
    Args:
        pokemon: PokemonBuild instance
        
    Returns:
        Showdown paste format string
    """
    # Convert PokemonBuild to dict format for export_pokemon_to_showdown
    species = pokemon.name.replace("-", " ").title()
    
    # Convert EVSpread to dict
    evs_dict = {
        "hp": pokemon.evs.hp,
        "atk": pokemon.evs.attack,
        "def": pokemon.evs.defense,
        "spa": pokemon.evs.special_attack,
        "spd": pokemon.evs.special_defense,
        "spe": pokemon.evs.speed,
    }
    
    # Convert IVSpread to dict (only include non-31 values)
    ivs_dict = {}
    if pokemon.ivs.hp != 31:
        ivs_dict["hp"] = pokemon.ivs.hp
    if pokemon.ivs.attack != 31:
        ivs_dict["atk"] = pokemon.ivs.attack
    if pokemon.ivs.defense != 31:
        ivs_dict["def"] = pokemon.ivs.defense
    if pokemon.ivs.special_attack != 31:
        ivs_dict["spa"] = pokemon.ivs.special_attack
    if pokemon.ivs.special_defense != 31:
        ivs_dict["spd"] = pokemon.ivs.special_defense
    if pokemon.ivs.speed != 31:
        ivs_dict["spe"] = pokemon.ivs.speed
    
    # Convert item name (hyphenated to spaced title case)
    item = pokemon.item.replace("-", " ").title() if pokemon.item else None
    
    # Convert ability name
    ability = pokemon.ability.replace("-", " ").title() if pokemon.ability else None
    
    # Convert tera type
    tera_type = pokemon.tera_type.replace("-", " ").title() if pokemon.tera_type else None
    
    # Convert nature
    nature = pokemon.nature.value.title()
    
    return export_pokemon_to_showdown(
        species=species,
        item=item,
        ability=ability,
        level=pokemon.level,
        tera_type=tera_type,
        evs=evs_dict,
        ivs=ivs_dict if ivs_dict else None,
        nature=nature,
        moves=pokemon.moves if pokemon.moves else None,
    )
