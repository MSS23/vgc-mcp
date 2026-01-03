"""Utility modules for VGC MCP server."""

from .errors import error_response, success_response, ToolError
from .fuzzy import suggest_pokemon_name, suggest_nature, suggest_move_name
from .damage_verdicts import calculate_ko_verdict, format_matchup_verdict, DamageVerdict
from .synergies import (
    get_synergy_ability,
    has_item_ability_synergy,
    normalize_item_name,
    normalize_ability_name,
    ITEM_ABILITY_SYNERGIES,
)
from .normalize import (
    normalize_name,
    normalize_pokemon_name,
    normalize_ability,
    normalize_item,
    normalize_move,
    clear_caches,
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
    "clear_caches",
]
