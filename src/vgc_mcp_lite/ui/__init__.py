"""MCP-UI support for VGC Team Builder.

This module provides interactive UI components for:
- Damage Calculator with visual damage bars
- Team Roster with Pokemon cards
- Speed Tier Analyzer with interactive charts
- Usage Statistics display
- Stats Card with bar visualization
- Calculation History
- Interactive Speed Histogram with dropdown
- Spread Cards for EV spread display
- Pokemon Build Card for team building
- Pokepaste Team Grid for team display
- Build Report for team analysis
- Team Diff for comparing team versions
"""

from .components import (
    create_damage_calc_ui,
    create_damage_calc_table_ui,
    create_team_roster_ui,
    create_speed_tier_ui,
    create_usage_stats_ui,
    create_stats_card_ui,
    create_calc_history_ui,
    create_speed_histogram_ui,
    create_interactive_speed_histogram_ui,
    create_spread_cards_ui,
    create_pokemon_build_card_ui,
    create_pokepaste_team_grid_ui,
    create_build_report_ui,
    create_team_diff_ui,
)

from .resources import register_ui_resources

__all__ = [
    # Core components
    "create_damage_calc_ui",
    "create_damage_calc_table_ui",
    "create_team_roster_ui",
    "create_speed_tier_ui",
    "create_usage_stats_ui",
    "create_stats_card_ui",
    "create_calc_history_ui",
    "create_speed_histogram_ui",
    "create_interactive_speed_histogram_ui",
    "create_spread_cards_ui",
    "create_pokemon_build_card_ui",
    "create_pokepaste_team_grid_ui",
    "create_build_report_ui",
    "create_team_diff_ui",
    # Resources
    "register_ui_resources",
]
