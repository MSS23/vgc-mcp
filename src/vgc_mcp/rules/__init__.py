"""VGC format rules and legality checking."""

from .regulation_loader import get_regulation_config, RegulationConfig, reset_regulation_config
from .vgc_rules import get_regulation, list_regulations, validate_team_rules, get_current_regulation
from .restricted import is_restricted, is_banned, get_restricted_status, find_banned, find_restricted
from .item_clause import check_item_clause, get_duplicate_items

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
