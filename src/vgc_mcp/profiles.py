"""Tool profiles: which registered tools a client sees.

Every tool module is always registered on the full server. Clients get the
**core** profile by default: the tools that answer what people actually ask
(damage, survival, speed, spreads, team prep, usage, legality, the battle
copilot, onboarding and export). A long tool list costs the model tokens and
makes it pick the wrong tool, which hurts most on phones.

- HTTP: ``/mcp`` serves the default profile, ``/mcp/full`` always serves
  every tool.
- Both transports: ``VGC_MCP_PROFILE=full`` makes the full set the default.

``FULL_TOOL_COUNT`` is the one place the total is pinned. Tests check the
registry, the README and CLAUDE.md against it, so a new tool means updating
this number and nothing else by hand.
"""

from __future__ import annotations

import os

FULL_TOOL_COUNT = 213

CORE_TOOLS: frozenset[str] = frozenset(
    {
        # Damage
        "calculate_damage_output",
        "calc_damage_vs_smogon_sets",
        "calculate_bulk_offensive_calcs",
        "calculate_move_outcomes",
        "export_damage_report",
        # Survival and spreads (EVs or Champions Stat Points)
        "find_survival_evs",
        "optimize_dual_survival_spread",
        "optimize_multi_survival_spread",
        "design_spread_with_benchmarks",
        "verify_spread_benchmarks",
        "recommend_verified_spreads",
        # Speed and stats
        "compare_speed",
        "find_speed_evs_to_outspeed",
        "analyze_outspeed_probability",
        "get_pokemon_stats",
        # Teams
        "prepare_team",
        "import_and_analyze",
        "import_showdown_team",
        "import_reference_team",
        "add_pokemon_smart",
        "export_team_to_paste",
        # Usage data
        "get_usage_stats",
        "get_common_sets",
        # Format and legality
        "auto_detect_regulation_from_pokemon",
        "set_session_regulation",
        "validate_team_legality",
        # Live battle copilot
        "start_battle",
        "record_turn",
        "suggest_next_move",
        "end_battle",
        # Onboarding and learning
        "welcome_new_user",
        "show_capabilities",
        "explain_vgc_term",
        "analyze_replay",
    }
)

PROFILES = ("core", "full")


def resolve_profile(value: str | None = None) -> str:
    """Return the default profile name from ``value`` or ``VGC_MCP_PROFILE``.

    Unknown values fall back to ``core`` so a typo never exposes nothing.
    """
    raw = (value if value is not None else os.environ.get("VGC_MCP_PROFILE", "core"))
    name = raw.strip().lower()
    return name if name in PROFILES else "core"
