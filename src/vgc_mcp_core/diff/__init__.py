"""Team diff module for comparing Pokemon team versions."""

from .models import FieldChange, PokemonDiff, TeamDiff, ChangeType, FieldType
from .team_diff import generate_team_diff, compare_pokemon, match_pokemon_by_species
from .change_reasons import (
    explain_nature_change,
    explain_ev_change,
    explain_item_change,
    explain_move_change,
    explain_ability_change,
    explain_tera_change,
)

__all__ = [
    # Models
    "FieldChange",
    "PokemonDiff",
    "TeamDiff",
    "ChangeType",
    "FieldType",
    # Core functions
    "generate_team_diff",
    "compare_pokemon",
    "match_pokemon_by_species",
    # Reason generators
    "explain_nature_change",
    "explain_ev_change",
    "explain_item_change",
    "explain_move_change",
    "explain_ability_change",
    "explain_tera_change",
]
