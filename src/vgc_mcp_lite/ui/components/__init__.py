# -*- coding: utf-8 -*-
"""UI component builders for VGC Team Builder.

This package provides HTML string builders for various UI components
that can be embedded in MCP UI resources.

Components are organized by category:
- styles: Shared CSS styles
- sprites: Pokemon sprite URLs and type colors
- (main module): All UI component builders

Usage:
    from vgc_mcp_lite.ui.components import (
        create_damage_calc_ui,
        create_pokemon_build_card_ui,
        get_sprite_html,
        get_type_color,
    )
"""

# Re-export utilities from submodules
from .styles import get_shared_styles
from .sprites import (
    get_sprite_url,
    get_sprite_html,
    get_type_color,
    SPRITE_PLACEHOLDER,
    TYPE_COLORS,
)

# Import all component builders from the main module
# These will be migrated to submodules in future refactors
from .main import (
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

__all__ = [
    # Styles
    "get_shared_styles",
    # Sprites
    "get_sprite_url",
    "get_sprite_html",
    "get_type_color",
    "SPRITE_PLACEHOLDER",
    "TYPE_COLORS",
    # Damage components
    "create_damage_calc_ui",
    "create_damage_calc_table_ui",
    # Team components
    "create_team_roster_ui",
    "create_pokepaste_team_grid_ui",
    "create_team_diff_ui",
    # Speed components
    "create_speed_tier_ui",
    "create_speed_histogram_ui",
    "create_interactive_speed_histogram_ui",
    # Usage components
    "create_usage_stats_ui",
    "create_spread_cards_ui",
    # Stats components
    "create_stats_card_ui",
    "create_calc_history_ui",
    # Build components
    "create_pokemon_build_card_ui",
    "create_build_report_ui",
]
