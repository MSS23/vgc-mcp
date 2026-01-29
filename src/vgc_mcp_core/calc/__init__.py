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
from .nature_optimization import (
    find_optimal_nature_for_benchmarks,
    NatureOptimizationResult,
    get_relevant_natures,
    calculate_evs_for_benchmarks,
    calculate_nature_score,
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
    # Nature Optimization
    "find_optimal_nature_for_benchmarks",
    "NatureOptimizationResult",
    "get_relevant_natures",
    "calculate_evs_for_benchmarks",
    "calculate_nature_score",
]
