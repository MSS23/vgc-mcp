"""Calculation engines for stats, damage, and speed."""

from .coverage import (
    CoverageAnalysisResult,
    analyze_move_coverage,
    check_coverage_vs_pokemon,
    check_quad_weaknesses,
    find_coverage_holes,
    get_coverage_summary,
    suggest_coverage_moves,
)
from .damage import DamageResult, calculate_damage
from .modifiers import TYPE_CHART, DamageModifiers, get_type_effectiveness
from .nature_optimization import (
    NatureOptimizationResult,
    calculate_evs_for_benchmarks,
    calculate_nature_score,
    find_optimal_nature_for_benchmarks,
    get_relevant_natures,
)
from .speed import SpeedComparison, compare_speeds, find_speed_evs
from .stats import calculate_all_stats, calculate_hp, calculate_speed, calculate_stat

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
    # Nature Optimization
    "find_optimal_nature_for_benchmarks",
    "NatureOptimizationResult",
    "get_relevant_natures",
    "calculate_evs_for_benchmarks",
    "calculate_nature_score",
]
