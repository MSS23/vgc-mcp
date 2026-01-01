"""MCP-UI support for VGC Team Builder.

This module provides interactive UI components for:
- Damage Calculator with visual damage bars
- Team Roster with Pokemon cards
- Speed Tier Analyzer with interactive charts
- Coverage Analysis grid
- Matchup Summary with threat indicators
"""

from .resources import register_ui_resources
from .components import (
    create_damage_calc_ui,
    create_team_roster_ui,
    create_speed_tier_ui,
    create_coverage_ui,
)

__all__ = [
    "register_ui_resources",
    "create_damage_calc_ui",
    "create_team_roster_ui",
    "create_speed_tier_ui",
    "create_coverage_ui",
]
