"""Standardized error handling for VGC MCP tools.

This module provides consistent error responses across all tools,
making it easier for users to understand what went wrong and how to fix it.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolError:
    """Structured error information for tool responses."""

    code: str  # Machine-readable error code
    message: str  # Human-readable error message
    suggestions: list[str] = field(default_factory=list)  # Actionable next steps
    context: dict[str, Any] = field(default_factory=dict)  # Additional debug info


# Common error codes for consistency across tools
class ErrorCodes:
    """Standard error codes used across the MCP server."""

    # Input validation errors
    POKEMON_NOT_FOUND = "pokemon_not_found"
    MOVE_NOT_FOUND = "move_not_found"
    ITEM_NOT_FOUND = "item_not_found"
    ABILITY_NOT_FOUND = "ability_not_found"
    INVALID_NATURE = "invalid_nature"
    INVALID_EVS = "invalid_evs"
    INVALID_IVS = "invalid_ivs"
    INVALID_PARAMETER = "invalid_parameter"

    # Team errors
    TEAM_EMPTY = "team_empty"
    TEAM_FULL = "team_full"
    SPECIES_CLAUSE = "species_clause_violation"
    ITEM_CLAUSE = "item_clause_violation"
    RESTRICTED_LIMIT = "restricted_limit_exceeded"

    # API errors
    API_ERROR = "api_error"
    API_NOT_FOUND = "api_not_found"
    API_TIMEOUT = "api_timeout"
    API_RATE_LIMITED = "api_rate_limited"

    # Format errors
    PARSE_ERROR = "parse_error"
    INVALID_FORMAT = "invalid_format"

    # General
    INTERNAL_ERROR = "internal_error"
    NOT_IMPLEMENTED = "not_implemented"


def error_response(
    code: str,
    message: str,
    suggestions: Optional[list[str]] = None,
    **extra_fields
) -> dict:
    """
    Create a standardized error response.

    Args:
        code: Error code from ErrorCodes class
        message: Human-readable error message
        suggestions: List of actionable suggestions for the user
        **extra_fields: Additional fields to include in response

    Returns:
        Consistent error response dict

    Example:
        >>> error_response(
        ...     ErrorCodes.POKEMON_NOT_FOUND,
        ...     "Pokemon 'Charzard' not found",
        ...     suggestions=["Did you mean: Charizard, Charmeleon?"]
        ... )
        {'success': False, 'error': 'pokemon_not_found',
         'message': "Pokemon 'Charzard' not found",
         'suggestions': ['Did you mean: Charizard, Charmeleon?']}
    """
    response = {
        "success": False,
        "error": code,
        "message": message,
    }

    if suggestions:
        response["suggestions"] = suggestions

    # Add any extra fields (like valid_values, current_value, etc.)
    response.update(extra_fields)

    return response


def success_response(message: str, **data) -> dict:
    """
    Create a standardized success response.

    Args:
        message: Human-readable success message
        **data: Additional data fields to include

    Returns:
        Consistent success response dict

    Example:
        >>> success_response("Pokemon added to team", pokemon="Charizard", slot=3)
        {'success': True, 'message': 'Pokemon added to team',
         'pokemon': 'Charizard', 'slot': 3}
    """
    response = {
        "success": True,
        "message": message,
    }
    response.update(data)
    return response


def pokemon_not_found_error(name: str, suggestions: Optional[list[str]] = None) -> dict:
    """Create a Pokemon not found error with optional suggestions."""
    msg = f"Pokemon '{name}' not found"
    tips = suggestions or []

    if not tips:
        tips = [
            "Check spelling (use hyphens for forms: 'flutter-mane', 'urshifu-rapid-strike')",
            "Pokemon names are case-insensitive",
        ]

    return error_response(ErrorCodes.POKEMON_NOT_FOUND, msg, suggestions=tips)


def invalid_nature_error(nature: str, valid_natures: list[str]) -> dict:
    """Create an invalid nature error with valid options."""
    # Show a sample of valid natures, not all 25
    sample = valid_natures[:8]
    sample_str = ", ".join(sample)

    return error_response(
        ErrorCodes.INVALID_NATURE,
        f"Invalid nature: '{nature}'",
        suggestions=[
            f"Valid natures include: {sample_str}...",
            "Common competitive natures: Adamant, Jolly, Modest, Timid, Bold, Calm",
        ],
        valid_natures=valid_natures,
    )


def invalid_evs_error(
    stat: str,
    value: int,
    reason: str,
    total: Optional[int] = None
) -> dict:
    """Create an invalid EVs error."""
    suggestions = []

    if value > 252:
        suggestions.append(f"Maximum EVs per stat is 252 (you entered {value})")
    elif value < 0:
        suggestions.append("EVs cannot be negative")
    elif value % 4 != 0:
        wasted = value % 4
        suggestions.append(
            f"{wasted} EVs are wasted (not a multiple of 4). "
            f"Try {value - wasted} or {value + (4 - wasted)}"
        )

    if total and total > 508:
        suggestions.append(f"Total EVs ({total}) exceed maximum of 508")

    return error_response(
        ErrorCodes.INVALID_EVS,
        f"Invalid EVs for {stat}: {reason}",
        suggestions=suggestions,
    )


def team_empty_error() -> dict:
    """Create a team empty error with helpful suggestions."""
    return error_response(
        ErrorCodes.TEAM_EMPTY,
        "No Pokemon on team",
        suggestions=[
            "Use 'add_to_team' to add Pokemon to your team",
            "Use 'import_showdown_paste' to import a team from Pokemon Showdown",
            "Use 'add_pokemon_smart' for intelligent Pokemon suggestions",
        ],
    )


def team_full_error(current_pokemon: list[str]) -> dict:
    """Create a team full error with current team info."""
    return error_response(
        ErrorCodes.TEAM_FULL,
        "Team is full (6 Pokemon maximum)",
        suggestions=[
            "Use 'remove_from_team' to remove a Pokemon first",
            "Use 'swap_pokemon' to replace a specific slot",
        ],
        current_team=current_pokemon,
    )


def api_error(
    api_name: str,
    original_error: str,
    is_retryable: bool = False
) -> dict:
    """Create an API error with context."""
    suggestions = []

    if is_retryable:
        suggestions.append("This may be a temporary issue - try again in a moment")

    if "404" in original_error or "not found" in original_error.lower():
        suggestions.append("The requested resource may not exist")
    elif "timeout" in original_error.lower():
        suggestions.append("The API is slow to respond - try again later")
    elif "rate" in original_error.lower():
        suggestions.append("Too many requests - wait a moment before retrying")

    return error_response(
        ErrorCodes.API_ERROR,
        f"{api_name} error: {original_error}",
        suggestions=suggestions or ["Check your input and try again"],
    )
