"""VGC rule validation."""

from typing import Optional

from ..models.pokemon import PokemonBuild, EVSpread
from ..models.team import Team


class ValidationError(Exception):
    """Validation error with details."""
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(message)


def validate_ev_spread(evs: EVSpread) -> tuple[bool, list[str]]:
    """
    Validate an EV spread according to VGC rules.

    Rules:
    - Maximum 508 total EVs
    - Maximum 252 EVs per stat
    - EVs should be multiples of 4 for efficiency

    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []

    # Check total
    if evs.total > 508:
        issues.append(f"Total EVs ({evs.total}) exceed maximum of 508")

    # Check individual stats
    stats = {
        "HP": evs.hp,
        "Attack": evs.attack,
        "Defense": evs.defense,
        "Sp. Atk": evs.special_attack,
        "Sp. Def": evs.special_defense,
        "Speed": evs.speed,
    }

    for stat_name, value in stats.items():
        if value > 252:
            issues.append(f"{stat_name} EVs ({value}) exceed maximum of 252")
        if value % 4 != 0 and value != 0:
            issues.append(f"{stat_name} EVs ({value}) not a multiple of 4 - {value % 4} wasted")

    return len(issues) == 0, issues


def validate_pokemon_build(pokemon: PokemonBuild) -> tuple[bool, list[str]]:
    """
    Validate a complete Pokemon build.

    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []

    # Validate EVs
    ev_valid, ev_issues = validate_ev_spread(pokemon.evs)
    issues.extend(ev_issues)

    # Validate IVs
    iv_stats = {
        "HP": pokemon.ivs.hp,
        "Attack": pokemon.ivs.attack,
        "Defense": pokemon.ivs.defense,
        "Sp. Atk": pokemon.ivs.special_attack,
        "Sp. Def": pokemon.ivs.special_defense,
        "Speed": pokemon.ivs.speed,
    }

    for stat_name, value in iv_stats.items():
        if value < 0 or value > 31:
            issues.append(f"{stat_name} IV ({value}) must be between 0 and 31")

    # Validate move count
    if len(pokemon.moves) > 4:
        issues.append(f"Pokemon has {len(pokemon.moves)} moves, maximum is 4")

    # Validate level
    if pokemon.level < 1 or pokemon.level > 100:
        issues.append(f"Level ({pokemon.level}) must be between 1 and 100")

    return len(issues) == 0, issues


def validate_team(team: Team) -> tuple[bool, list[str]]:
    """
    Validate a complete team according to VGC rules.

    Rules:
    - Maximum 6 Pokemon
    - Species Clause: No duplicate base species
    - Each Pokemon must be valid

    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []

    # Check team size
    if team.size > 6:
        issues.append(f"Team has {team.size} Pokemon, maximum is 6")

    # Check species clause
    species_seen = {}
    for slot in team.slots:
        species = slot.pokemon.species.lower()
        if species in species_seen:
            issues.append(
                f"Species Clause: {slot.pokemon.name} duplicates "
                f"{species_seen[species]} (same base species: {species})"
            )
        else:
            species_seen[species] = slot.pokemon.name

    # Validate each Pokemon
    for slot in team.slots:
        valid, pokemon_issues = validate_pokemon_build(slot.pokemon)
        for issue in pokemon_issues:
            issues.append(f"Slot {slot.slot_index + 1} ({slot.pokemon.name}): {issue}")

    return len(issues) == 0, issues


# Common VGC legality checks (simplified)
RESTRICTED_POKEMON = [
    "mewtwo", "lugia", "ho-oh", "kyogre", "groudon", "rayquaza",
    "dialga", "palkia", "giratina", "reshiram", "zekrom", "kyurem",
    "xerneas", "yveltal", "zygarde", "cosmog", "cosmoem", "solgaleo",
    "lunala", "necrozma", "zacian", "zamazenta", "eternatus",
    "calyrex", "koraidon", "miraidon", "terapagos",
]


def is_restricted(pokemon_name: str) -> bool:
    """Check if a Pokemon is restricted (limited to 1-2 per team in some formats)."""
    name = pokemon_name.lower().split("-")[0]
    return name in RESTRICTED_POKEMON


def count_restricted(team: Team) -> int:
    """Count restricted Pokemon on a team."""
    return sum(1 for slot in team.slots if is_restricted(slot.pokemon.name))


def validate_restricted_count(team: Team, max_restricted: int = 2) -> tuple[bool, str]:
    """
    Validate restricted Pokemon count.

    Args:
        team: Team to validate
        max_restricted: Maximum allowed restricted Pokemon (usually 1 or 2)

    Returns:
        Tuple of (is_valid, message)
    """
    count = count_restricted(team)
    if count > max_restricted:
        restricted_names = [
            slot.pokemon.name for slot in team.slots
            if is_restricted(slot.pokemon.name)
        ]
        return False, f"Too many restricted Pokemon ({count}/{max_restricted}): {restricted_names}"
    return True, f"Restricted count OK ({count}/{max_restricted})"
