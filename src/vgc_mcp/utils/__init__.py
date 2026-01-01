"""Utility modules for VGC MCP server."""

from .errors import error_response, success_response, ToolError
from .fuzzy import suggest_pokemon_name, suggest_nature, suggest_move_name
from .damage_verdicts import calculate_ko_verdict, format_matchup_verdict, DamageVerdict

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
]
