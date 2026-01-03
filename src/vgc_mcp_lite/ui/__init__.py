"""MCP-UI support for VGC Team Builder.

This module provides interactive UI components for:
- Damage Calculator with visual damage bars
- Team Roster with Pokemon cards
- Speed Tier Analyzer with interactive charts
- Matchup Summary with threat indicators
- Threat Analysis with detailed matchup breakdown
- Speed Outspeed Percentage with interactive slider
- Stats Card with bar visualization
- Threat Matchup Matrix for damage analysis
- Turn Order Timeline with priority/speed
- Bring/Leave Selector for team preview
- Ability Synergy Network visualization
- Team Report Card with grades
- Summary Table for structured data display
- Speed Outspeed Graph for cumulative distribution
- Multi-Hit Survival visualization
"""

from .resources import (
    register_ui_resources,
    create_speed_outspeed_resource,
    create_stats_card_resource,
    create_threat_matrix_resource,
    create_turn_order_resource,
    create_bring_selector_resource,
    create_ability_synergy_resource,
    create_team_report_resource,
    create_summary_table_resource,
    create_speed_outspeed_graph_resource,
    create_multi_hit_survival_resource,
)
from .components import (
    create_damage_calc_ui,
    create_team_roster_ui,
    create_speed_tier_ui,
    create_matchup_summary_ui,
    create_threat_analysis_ui,
    create_usage_stats_ui,
    create_speed_outspeed_ui,
    create_stats_card_ui,
    create_threat_matrix_ui,
    create_turn_order_ui,
    create_bring_selector_ui,
    create_ability_synergy_ui,
    create_team_report_ui,
    create_summary_table_ui,
    create_speed_outspeed_graph_ui,
    create_multi_hit_survival_ui,
)

__all__ = [
    "register_ui_resources",
    # Original components
    "create_damage_calc_ui",  # Use interactive=True for editable version
    "create_team_roster_ui",
    "create_speed_tier_ui",
    "create_matchup_summary_ui",
    "create_threat_analysis_ui",
    "create_usage_stats_ui",
    "create_speed_outspeed_ui",
    "create_speed_outspeed_resource",
    # Stats and visualization components
    "create_stats_card_ui",
    "create_threat_matrix_ui",
    "create_turn_order_ui",
    "create_bring_selector_ui",
    "create_ability_synergy_ui",
    "create_team_report_ui",
    "create_summary_table_ui",
    "create_speed_outspeed_graph_ui",
    "create_multi_hit_survival_ui",
    # Resource wrappers
    "create_stats_card_resource",
    "create_threat_matrix_resource",
    "create_turn_order_resource",
    "create_bring_selector_resource",
    "create_ability_synergy_resource",
    "create_team_report_resource",
    "create_summary_table_resource",
    "create_speed_outspeed_graph_resource",
    "create_multi_hit_survival_resource",
]
