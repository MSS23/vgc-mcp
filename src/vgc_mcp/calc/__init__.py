"""Calculation engines for stats, damage, and speed."""

from .stats import calculate_hp, calculate_stat, calculate_all_stats, calculate_speed
from .damage import calculate_damage, DamageResult
from .modifiers import DamageModifiers, get_type_effectiveness, TYPE_CHART
from .speed import compare_speeds, find_speed_evs, SpeedComparison
from .coverage import (
    analyze_move_coverage,
    find_coverage_holes,
    check_quad_weaknesses,
    check_coverage_vs_pokemon,
    suggest_coverage_moves,
    get_coverage_summary,
    CoverageAnalysisResult,
)

__all__ = [
    "calculate_hp",
    "calculate_stat",
    "calculate_all_stats",
    "calculate_speed",
    "calculate_damage",
    "DamageResult",
    "DamageModifiers",
    "get_type_effectiveness",
    "TYPE_CHART",
    "compare_speeds",
    "find_speed_evs",
    "SpeedComparison",
    # Coverage
    "analyze_move_coverage",
    "find_coverage_holes",
    "check_quad_weaknesses",
    "check_coverage_vs_pokemon",
    "suggest_coverage_moves",
    "get_coverage_summary",
    "CoverageAnalysisResult",
]
