"""VGC rule validation."""

from typing import Optional

from ..models.pokemon import EVSpread
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

