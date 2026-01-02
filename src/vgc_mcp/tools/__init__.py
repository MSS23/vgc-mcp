"""MCP tool definitions."""

from .stats_tools import register_stats_tools
from .damage_tools import register_damage_tools
from .speed_analysis_tools import register_speed_analysis_tools
from .team_tools import register_team_tools
from .usage_tools import register_usage_tools
from .spread_tools import register_spread_tools
from .coverage_tools import register_coverage_tools

__all__ = [
    "register_stats_tools",
    "register_damage_tools",
    "register_speed_analysis_tools",
    "register_team_tools",
    "register_usage_tools",
    "register_spread_tools",
    "register_coverage_tools",
]
