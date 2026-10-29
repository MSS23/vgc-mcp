"""MCP tools for user onboarding and discoverability."""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.config import logger
from vgc_mcp_core.utils.errors import api_error

# Each category lists example questions plus the tools that answer them, in
# priority order. Tool titles and descriptions are read from the live registry
# at call time, so a renamed or removed tool drops out instead of going stale.
_CATEGORIES: dict[str, dict] = {
    "damage": {
        "title": "Damage calculations",
        "examples": [
            "Does Flutter Mane OHKO Incineroar with Moonblast?",
            "How much does Mega Garchomp Z's Earthquake do to Rillaboom?",
            "Show my Urshifu's damage against the top 10 meta threats",
        ],
        "tools": [
            "calculate_damage_output",
            "calc_damage_vs_smogon_sets",
            "calculate_bulk_offensive_calcs",
            "calculate_move_outcomes",
            "export_damage_report",
        ],
    },
    "team": {
        "title": "Team building and review",
        "examples": [
            "Get my team ready for a Regional (I'll paste it)",
            "Analyze this team: (paste)",
            "What are the most used Pokemon right now?",
        ],
        "tools": [
            "prepare_team",
            "import_and_analyze",
            "get_usage_stats",
            "validate_team_legality",
            "export_team_to_paste",
        ],
    },
    "evs": {
        "title": "Spreads (EVs or Champions Stat Points)",
        "examples": [
            "What does Incineroar need to survive Flutter Mane's Moonblast?",
            "Design a spread that outspeeds Tornadus and survives Urshifu",
            "Check this spread hits all my benchmarks",
        ],
        "tools": [
            "find_survival_evs",
            "design_spread_with_benchmarks",
            "optimize_multi_survival_spread",
            "verify_spread_benchmarks",
            "recommend_verified_spreads",
        ],
    },
    "speed": {
        "title": "Speed",
        "examples": [
            "Is my Landorus faster than Tornadus?",
            "How many points does Mega Lucario Z need to outspeed Dragapult?",
            "How often does my Incineroar outspeed the meta?",
        ],
        "tools": [
            "compare_speed",
            "find_speed_evs_to_outspeed",
            "analyze_outspeed_probability",
            "get_pokemon_stats",
        ],
    },
    "battle": {
        "title": "Live battle copilot",
        "examples": [
            "Start a battle: my team against theirs (I'll list both)",
            "Turn 1: they led Incineroar and Flutter Mane. What should I do?",
            "Explain what happened in this replay (I'll paste the link)",
        ],
        "tools": [
            "start_battle",
            "record_turn",
            "suggest_next_move",
            "end_battle",
            "analyze_replay",
        ],
    },
    "learn": {
        "title": "Learning VGC",
        "examples": [
            "Explain what Stat Points are in Champions",
            "What does spread move damage reduction mean?",
            "What are the common sets for Incineroar?",
        ],
        "tools": [
            "explain_vgc_term",
            "get_common_sets",
        ],
    },
}
_ALIASES = {
    "teambuilding": "team",
    "team building": "team",
    "ev": "evs",
    "sp": "evs",
    "sps": "evs",
    "spread": "evs",
    "spreads": "evs",
    "learning": "learn",
    "education": "learn",
    "copilot": "battle",
    "replay": "battle",
}
_MAX_TOOLS_PER_CATEGORY = 5

# Three questions a phone user can send as-is. There are no slash commands in
# the Claude apps, so onboarding never tells people to type one.
_STARTER_QUESTIONS = [
    "Does Flutter Mane OHKO Incineroar with Moonblast?",
    "Get my team ready for a tournament (I'll paste it)",
    "What does Incineroar need to survive Flutter Mane?",
]


def _first_sentence(text: Optional[str]) -> str:
    line = (text or "").strip().split("\n", 1)[0].strip()
    return line.rstrip(".")


def register_onboarding_tools(mcp: FastMCP):
    """Register onboarding and discoverability tools."""

    async def _registered_tools() -> dict:
        return {tool.name: tool for tool in await mcp.list_tools()}

    def _category_markdown(key: str, registered: dict) -> tuple[list[str], list[str]]:
        cat = _CATEGORIES[key]
        tools = [n for n in cat["tools"] if n in registered][:_MAX_TOOLS_PER_CATEGORY]
        lines = [f"## {cat['title']}", "", "**Try asking:**"]
        lines += [f'- "{q}"' for q in cat["examples"]]
        lines += ["", "**Tools behind it:**"]
        for name in tools:
            tool = registered[name]
            label = tool.title or name
            lines.append(f"- **{label}**: {_first_sentence(tool.description)}")
        return lines, tools

    @mcp.tool(
        title="Show Capabilities",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def show_capabilities(
        category: Annotated[Optional[str], Field(description="Filter by 'damage', 'team', 'evs', 'speed', 'battle', 'learn', or None for the full overview")] = None,
    ) -> dict:
        """Show what this server can do, with example prompts.

        Returns a capabilities overview (or a category-specific guide) as
        markdown, listing example prompts and the relevant tools.
        """
        try:
            registered = await _registered_tools()
            categories = list(_CATEGORIES)

            if category is None:
                lines = [
                    "## What can I do?",
                    "",
                    "Ask in plain words, or paste a Showdown team. Works for "
                    "mainline VGC (EVs) and Pokemon Champions (Stat Points).",
                    "",
                ]
                for key in categories:
                    cat = _CATEGORIES[key]
                    lines.append(f"**{cat['title']}**: \"{cat['examples'][0]}\"")
                lines += [
                    "",
                    "Ask \"what can you do for speed?\" (or damage, team, evs, "
                    "battle, learn) for more examples.",
                ]
                return {
                    "capabilities_type": "overview",
                    "markdown_summary": "\n".join(lines),
                    "categories": categories,
                    "tool_count": len(registered),
                }

            key = _ALIASES.get(category.lower().strip(), category.lower().strip())
            if key not in _CATEGORIES:
                return {
                    "capabilities_type": "unknown",
                    "category": category,
                    "message": f"Unknown category: {category}. Try: {', '.join(categories)}",
                    "available_categories": categories,
                }

            lines, tools = _category_markdown(key, registered)
            return {
                "capabilities_type": "category",
                "category": key,
                "markdown_summary": "\n".join(lines),
                "tools": tools,
                "example_prompts": _CATEGORIES[key]["examples"],
            }

        except Exception as e:
            logger.error(f"Error in show_capabilities: {e}", exc_info=True)
            return api_error(str(e))

    @mcp.tool(
        title="Welcome New User",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def welcome_new_user() -> dict:
        """Show the welcome message for first-time users.

        Call this when a user says hello or seems new to the tool. Returns a
        quick-start guide as markdown plus suggested starter prompts.
        """
        try:
            lines = [
                "# Welcome to VGC Team Builder",
                "",
                "I do damage calcs, spreads, speed checks and team reviews for "
                "VGC and Pokemon Champions. Just ask in plain words.",
                "",
                "**Try one of these:**",
            ]
            lines += [f"{i}. {q}" for i, q in enumerate(_STARTER_QUESTIONS, 1)]
            lines += [
                "",
                "You can also paste a Showdown team and I'll review it.",
            ]
            return {
                "welcome": True,
                "markdown_summary": "\n".join(lines),
                "suggested_prompts": list(_STARTER_QUESTIONS),
            }

        except Exception as e:
            logger.error(f"Error in welcome_new_user: {e}", exc_info=True)
            return api_error(str(e))

    @mcp.tool(
        title="Get Starter Prompts",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_starter_prompts() -> dict:
        """Get a list of starter prompts for UI integration.

        Returns prompts with titles, icons, and descriptions that can be shown
        as clickable buttons in chat interfaces.
        """
        try:
            prompts = [
                {
                    "title": "Build a Team",
                    "prompt": "Help me build a competitive VGC team",
                    "icon": "hammer",
                    "description": "Start building a team from scratch"
                },
                {
                    "title": "Check Damage",
                    "prompt": "Does Flutter Mane OHKO Incineroar with Moonblast?",
                    "icon": "zap",
                    "description": "Calculate damage between Pokemon"
                },
                {
                    "title": "Optimize EVs",
                    "prompt": "What EVs does Incineroar need to survive Flutter Mane?",
                    "icon": "bar-chart",
                    "description": "Find optimal EV spreads"
                },
                {
                    "title": "Analyze Team",
                    "prompt": "Analyze my team's weaknesses (I'll paste it)",
                    "icon": "search",
                    "description": "Find weaknesses in your team"
                },
                {
                    "title": "Learn VGC",
                    "prompt": "I'm new to VGC. What should I know?",
                    "icon": "book",
                    "description": "Learn competitive Pokemon basics"
                },
                {
                    "title": "What Can You Do?",
                    "prompt": "Show me what you can help with",
                    "icon": "help-circle",
                    "description": "See all available features"
                }
            ]

            return {
                "prompts": prompts,
                "count": len(prompts)
            }

        except Exception as e:
            logger.error(f"Error in get_starter_prompts: {e}", exc_info=True)
            return api_error(str(e))
