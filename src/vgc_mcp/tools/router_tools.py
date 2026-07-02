"""Tool router — `what_tool_should_i_use(question)`.

With ~200 tools registered, even Claude can pick the wrong one. This
router takes a free-text question and returns the top 3-5 candidate
tools with rationale, so the agent can route deterministically.

It's pure regex / keyword matching — no LLM calls — and ranked by
specificity. Augments the agent's natural tool selection without
overriding it.
"""

from __future__ import annotations

import re

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.utils.errors import ErrorCodes, error_response

# Each rule: (regex pattern, list of suggested tool names, rationale)
ROUTING_RULES: list[tuple[re.Pattern, list[str], str]] = [
    # Damage calculations
    (re.compile(r"\b(?:OHKO|2HKO|3HKO|guaranteed\s+KO|2[-\s]?hit\s+KO)\b", re.I),
     ["calculate_damage_output", "find_ko_evs", "find_breakpoint"],
     "Direct KO question — start with calculate_damage_output."),

    (re.compile(r"\bdamage\s+(?:vs|against|to)\s+\w+", re.I),
     ["calculate_damage_output", "calculate_bulk_offensive_calcs"],
     "Damage-against-target question."),

    (re.compile(r"\b(?:bulk|multi[-\s]?(?:def|target))\s+(?:calc|damage)", re.I),
     ["calculate_bulk_offensive_calcs", "export_damage_report"],
     "Multi-defender or bulk damage analysis."),

    # Survival
    (re.compile(r"\bwhat\s+EVs?\s+(?:to|do\s+I\s+need\s+to)\s+survive\b", re.I),
     ["find_survival_evs", "find_breakpoint", "optimize_multi_survival_spread"],
     "Survival-EVs question — `find_survival_evs` for one threat, "
     "`optimize_multi_survival_spread` for 3+ threats, "
     "`find_breakpoint` for the cheapest spread option."),

    (re.compile(r"\bsurvive\s+(?:both|all|multiple|two|three|four)\b", re.I),
     ["optimize_dual_survival_spread", "optimize_multi_survival_spread"],
     "Multi-threat survival — use `optimize_multi_survival_spread` for 3+ threats, "
     "`optimize_dual_survival_spread` for exactly 2."),

    # Speed
    (re.compile(r"\b(?:outspeed|faster\s+than|out[-\s]?speed)\b", re.I),
     ["find_speed_evs_to_outspeed", "find_breakpoint", "compare_speed", "outspeed_probability"],
     "Outspeed question — `find_breakpoint` with benchmark_type='outspeed' is the "
     "richest answer; `outspeed_probability` for usage-weighted answers."),

    (re.compile(r"\bspeed\s+tier", re.I),
     ["get_speed_tiers", "visualize_speed_tiers", "find_speed_benchmark"],
     "Speed-tier landscape question."),

    # Spread / build
    (re.compile(r"\boptimize|optimal\s+(?:spread|EVs?)\b", re.I),
     ["optimize_spread", "design_spread_with_benchmarks", "suggest_nature_optimization"],
     "Spread optimization."),

    (re.compile(r"\bnature\s+(?:save|optim)", re.I),
     ["suggest_nature_optimization"],
     "Nature optimization saves wasted EVs."),

    (re.compile(r"\bspread\s+for\s+\w+", re.I),
     ["suggest_spread", "suggest_spread_for_role", "design_spread_with_benchmarks"],
     "Role-based spread suggestion."),

    # Iteration / deltas
    (re.compile(r"\bcompare\s+(?:builds?|spreads?|items?)|what\s+changed", re.I),
     ["compare_build_changes", "compare_pokemon_options", "compare_item_damage_output"],
     "Comparison / delta question — `compare_build_changes` for spread iteration."),

    (re.compile(r"\bbreakpoint|cheapest|minimum\s+EVs?", re.I),
     ["find_breakpoint"],
     "Cheapest spread to clear a benchmark."),

    # Team / paste analysis
    (re.compile(r"\b(?:analy[sz]e|review|check)\s+(?:my|this|the)\s+team", re.I),
     ["analyze_team", "full_team_check", "import_and_analyze", "classify_team_archetype"],
     "Team-level analysis."),

    (re.compile(r"\bpokepaste|showdown\s+paste\b|^https?://pokepast\.es", re.I),
     ["import_showdown_team", "fetch_pokepaste", "import_and_analyze"],
     "Paste import."),

    (re.compile(r"\barchetype|playstyle|what\s+kind\s+of\s+team\b", re.I),
     ["classify_team_archetype"],
     "Team archetype classification."),

    # Live battle
    (re.compile(r"\b(?:in[-\s]?game|live\s+battle|currently\s+battling|next\s+turn)\b", re.I),
     ["start_battle", "record_turn", "suggest_next_move", "get_battle_state"],
     "Live battle copilot — call start_battle first if no battle is active."),

    (re.compile(r"\bgame\s+plan|how\s+to\s+(?:beat|play\s+against)\b", re.I),
     ["generate_game_plan", "analyze_team_matchup", "find_counter_for"],
     "Pre-game plan / matchup planning."),

    # Replay
    (re.compile(r"\breplay|replay\.pokemonshowdown\.com|game\s+log", re.I),
     ["analyze_replay"],
     "Replay analysis from a Showdown URL."),

    # Lead / bring
    (re.compile(r"\b(?:lead|bring\s+\d+|leave\s+\d+|team\s+preview)\b", re.I),
     ["analyze_lead_pairs", "generate_game_plan"],
     "Lead pair / bring-4 analysis."),

    # Coverage / threats
    (re.compile(r"\bcoverage|weak\s+to|resist|type\s+matchup\b", re.I),
     ["check_team_quad_weaknesses", "find_team_coverage_holes",
      "analyze_team_move_coverage", "explain_type_matchup"],
     "Coverage / weakness analysis."),

    (re.compile(r"\bcounter\s+(?:to|for)\s+|what\s+(?:beats|counters)\b", re.I),
     ["find_counter_for", "find_threats_to_team"],
     "Counter / threat finding."),

    # Tera
    (re.compile(r"\btera\s+type|terastall", re.I),
     ["optimize_tera_type", "calculate_damage_output"],
     "Tera-type analysis."),

    # Item-specific
    (re.compile(r"\b(?:life\s+orb|choice\s+(?:band|specs|scarf)|assault\s+vest|booster\s+energy)\b", re.I),
     ["calculate_choice_item", "calculate_assault_vest", "calculate_life_orb_damage",
      "calculate_booster_energy", "optimize_life_orb_sustainability"],
     "Item-specific damage helper."),

    # Meta usage
    (re.compile(r"\b(?:meta|usage|popular|top\s+\d+|tournament)\b", re.I),
     ["get_top_pokemon", "get_meta_teams", "get_usage_stats", "get_meta_speed_tiers"],
     "Meta / usage question."),

    # Education / explanation
    (re.compile(r"\b(?:what\s+is|explain|how\s+does)\b", re.I),
     ["explain_vgc_term", "explain_pokemon", "explain_type_matchup", "get_help"],
     "Definition / explanation."),
]


def register_router_tools(mcp: FastMCP):

    @mcp.tool()
    async def what_tool_should_i_use(question: str, max_suggestions: int = 5) -> dict:
        """Suggest the right tools for a free-text VGC question.

        Use this when:
            - The user's question is broad ("help me with my team")
            - You're unsure which of several similar tools to call
            - You want a deterministic shortlist before reasoning

        Returns a ranked list of {tool, rationale, priority} entries. Call
        the top suggestion first; fall back to alternatives if it doesn't
        accept the inputs you have.
        """
        if not question or not question.strip():
            return error_response(ErrorCodes.INVALID_PARAMETER,
                                  "Provide a question to route.")

        suggestions: list[dict] = []
        seen: set[str] = set()
        for pattern, tool_list, rationale in ROUTING_RULES:
            if pattern.search(question):
                for tool in tool_list:
                    if tool in seen:
                        continue
                    seen.add(tool)
                    suggestions.append({
                        "tool": tool,
                        "rationale": rationale,
                        "priority": len(suggestions) + 1,
                    })
                    if len(suggestions) >= max_suggestions:
                        break
            if len(suggestions) >= max_suggestions:
                break

        if not suggestions:
            # Generic fallback
            suggestions = [
                {"tool": "get_starter_prompts",
                 "rationale": "Couldn't match the question to a specific tool — start with starter prompts.",
                 "priority": 1},
                {"tool": "show_capabilities",
                 "rationale": "Show all capability categories the user can ask about.",
                 "priority": 2},
            ]

        return {
            "success": True,
            "question": question,
            "suggestions": suggestions,
            "agent_instruction": (
                "Use the highest-priority tool first. If it errors or returns "
                "incomplete data, fall through to the next. Only call multiple "
                "of these in parallel if they answer different sub-questions."
            ),
        }
