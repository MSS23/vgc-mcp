"""Team diff module for comparing Pokemon team versions."""

from .change_reasons import (
    explain_ability_change,
    explain_ev_change,
    explain_item_change,
    explain_move_change,
    explain_nature_change,
    explain_tera_change,
)
from .models import ChangeType, FieldChange, FieldType, PokemonDiff, TeamDiff
from .team_diff import compare_pokemon, generate_team_diff, match_pokemon_by_species

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
