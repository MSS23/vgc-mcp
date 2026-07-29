"""Input parsing helpers that return structured errors on failure.

Each helper returns either a *parsed value* on success or an *error response
dict* on failure. Tool functions can:

    parsed_or_err = parse_nature(nature_str)
    if isinstance(parsed_or_err, dict):
        return parsed_or_err  # already a structured error_response
    nature = parsed_or_err

This avoids the repeated try/except + invalid_nature_error pattern across
dozens of tools.
"""

from __future__ import annotations

from typing import Union

from ..models.pokemon import Nature
from ..utils.errors import (
    ErrorCodes,
    error_response,
    invalid_evs_error,
    invalid_nature_error,
)

# parse_nature returns a Nature; parse_ev_total returns an int total.
# Either may instead return an error_response dict.
ParsedOrError = Union["Nature", int, dict]


def parse_nature(nature_str: str) -> ParsedOrError:
    """Parse a nature string into a Nature enum.

    Returns the Nature on success, or an error_response dict on failure.
    Treats common synonyms ("hardy" / "serious" / "docile" / etc.) the same
    as the enum names — Nature() already does case-insensitive matching.
    """
    try:
        return Nature(nature_str.lower())
    except ValueError:
        return invalid_nature_error(
            nature_str, valid_natures=[n.value for n in Nature]
        )


def parse_ev_total(
    *, hp: int = 0, atk: int = 0, df: int = 0, spa: int = 0, spd: int = 0, spe: int = 0
) -> ParsedOrError:
    """Validate that the total of the supplied EVs ≤ 508 and each ≤ 252.

    Returns the int total on success, or an error_response dict on failure.
    Accepts `df` (not `def`) since `def` is a Python keyword.
    """
    parts = {"hp": hp, "attack": atk, "defense": df, "special_attack": spa, "special_defense": spd, "speed": spe}
    for stat, value in parts.items():
        if value < 0 or value > 252:
            return invalid_evs_error(stat, value, "must be between 0 and 252")
    total = sum(parts.values())
    if total > 508:
        return error_response(
            ErrorCodes.INVALID_EVS,
            f"Total EVs ({total}) exceed maximum of 508",
            suggestions=[f"Reduce by {total - 508} EVs"],
            total=total,
        )
    return total
