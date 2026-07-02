"""Utility modules for VGC MCP server."""

from .damage_verdicts import DamageVerdict, calculate_ko_verdict, format_matchup_verdict
from .errors import ToolError, error_response, success_response
from .fuzzy import suggest_move_name, suggest_nature, suggest_pokemon_name
from .normalize import (
    ABILITY_ALIASES,
    ITEM_ALIASES,
    MOVE_ALIASES,
    clear_caches,
    normalize_ability,
    normalize_item,
    normalize_move,
    normalize_move_name,
    normalize_name,
    normalize_pokemon_name,
    normalize_smogon_name,
)
from .synergies import (
    ITEM_ABILITY_SYNERGIES,
    get_synergy_ability,
    has_item_ability_synergy,
    normalize_ability_name,
    normalize_item_name,
)

__all__ = [
    "error_response",
    "success_response",
    "ToolError",
    "suggest_pokemon_name",
    "suggest_nature",
    "suggest_move_name",
    "calculate_ko_verdict",
    "format_matchup_verdict",
    "DamageVerdict",
    "get_synergy_ability",
    "has_item_ability_synergy",
    "normalize_item_name",
    "normalize_ability_name",
    "ITEM_ABILITY_SYNERGIES",
    "normalize_name",
    "normalize_pokemon_name",
    "normalize_ability",
    "normalize_item",
    "normalize_move",
    "normalize_move_name",
    "normalize_smogon_name",
    "clear_caches",
    "ITEM_ALIASES",
    "ABILITY_ALIASES",
    "MOVE_ALIASES",
]
