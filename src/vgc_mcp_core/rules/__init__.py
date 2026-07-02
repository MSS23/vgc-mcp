"""VGC format rules and legality checking."""

from .item_clause import check_item_clause, get_duplicate_items
from .regulation_loader import RegulationConfig, get_regulation_config, reset_regulation_config
from .restricted import (
    find_banned,
    find_restricted,
    get_restricted_status,
    is_banned,
    is_restricted,
)
from .vgc_rules import get_current_regulation, get_regulation, list_regulations, validate_team_rules

__all__ = [
    # Regulation config
    "get_regulation_config",
    "RegulationConfig",
    "reset_regulation_config",
    # VGC rules
    "get_regulation",
    "list_regulations",
    "validate_team_rules",
    "get_current_regulation",
    # Restricted/banned
    "is_restricted",
    "is_banned",
    "get_restricted_status",
    "find_banned",
    "find_restricted",
    # Item clause
    "check_item_clause",
    "get_duplicate_items",
]
