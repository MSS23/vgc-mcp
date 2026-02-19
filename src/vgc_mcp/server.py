"""VGC Team Builder MCP Server.

This server provides tools for VGC Pokemon team building:
- Stat calculations (level 50 VGC standard)
- Damage calculations with full modifier support
- Speed comparisons and tier analysis
- Team management with species clause
- Smogon usage data integration
- EV spread optimization
- Showdown paste import/export
- PokePaste URL fetching and analysis
- Speed control analysis (Trick Room, Tailwind)
- Matchup analysis against common threats
- Core building and team suggestions
- VGC format legality checking (restricted/banned Pokemon, item clause)
- Move legality and learnset validation
- Priority move and turn order analysis
- Ability synergy and interaction analysis
- Move-based coverage analysis
- Speed probability analysis using Smogon spread data
- Mathematical bulk optimization with diminishing returns
- Meta threat analysis with damage calculations
- Pokemon context persistence ("my Pokemon" references)

Usage:
    python -m vgc_mcp.server
    # or
    vgc-mcp (after pip install)
"""

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.cache import APICache
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.api.pokepaste import PokePasteClient
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.team.analysis import TeamAnalyzer
from vgc_mcp_core.state import BuildStateManager

from .tools.stats_tools import register_stats_tools
from .tools.damage_tools import register_damage_tools
from .tools.speed_analysis_tools import register_speed_analysis_tools
from .tools.team_tools import register_team_tools
from .tools.usage_tools import register_usage_tools
from .tools.spread_tools import register_spread_tools
from .tools.import_export_tools import register_import_export_tools
from .tools.matchup_tools import register_matchup_tools
from .tools.core_tools import register_core_tools
from .tools.legality_tools import register_legality_tools
from .tools.move_tools import register_move_tools
from .tools.priority_tools import register_priority_tools
from .tools.ability_tools import register_ability_tools
from .tools.coverage_tools import register_coverage_tools
from .tools.context_tools import register_context_tools
from .tools.speed_probability_tools import register_speed_probability_tools
from .tools.meta_threat_tools import register_meta_threat_tools
from .tools.workflow_tools import register_workflow_tools
from .tools.item_tools import register_item_tools
from .tools.chip_damage_tools import register_chip_damage_tools
from .tools.item_optimization_tools import register_item_optimization_tools
from .tools.multicalc_tools import register_multicalc_tools
from .tools.preset_tools import register_preset_tools
from .tools.sample_team_tools import register_sample_team_tools
from .tools.pokepaste_tools import register_pokepaste_tools
from .tools.build_tools import register_build_tools
from .tools.diff_tools import register_diff_tools
from .tools.report_tools import register_report_tools
from .tools.speed_tools import register_speed_tools
from .tools.tournament_tools import register_tournament_tools
from .tools.multi_threat_tools import register_multi_threat_tools
from .tools.team_matchup_tools import register_team_matchup_tools
from .tools.tera_tools import register_tera_tools
from .tools.lead_tools import register_lead_tools
from .tools.speed_viz_tools import register_speed_viz_tools
from .tools.readiness_tools import register_readiness_tools
from .tools.glossary_tools import register_glossary_tools
from .tools.education_tools import register_education_tools
from .tools.help_tools import register_help_tools
from .tools.build_checker_tools import register_build_checker_tools
from .tools.wizard_tools import register_wizard_tools
from .tools.type_tools import register_type_tools
from .tools.onboarding_tools import register_onboarding_tools
from .tools.game_plan_tools import register_game_plan_tools

# Note: MCP-UI is only enabled in vgc-mcp-lite for smaller footprint
# Full server focuses on tool completeness over visual components


# Initialize MCP server
mcp = FastMCP(
    "VGC Team Builder",
    instructions="""VGC Pokemon team building server with damage calc, usage stats, and team analysis.

IMPORTANT - For ALL damage calculations, ALWAYS show full spreads for BOTH Pokemon:
**Attacker:** [Nature] [HP]/[Atk]/[Def]/[SpA]/[SpD]/[Spe] [Pokemon] @ [Item]
**Defender:** [Nature] [HP]/[Atk]/[Def]/[SpA]/[SpD]/[Spe] [Pokemon] @ [Item]
**Result:** [damage]% ([verdict])

Example: "**Attacker:** Adamant 4/252/0/0/0/252 Urshifu @ Choice Scarf"
Users need EXACT spreads to verify calculations themselves."""
)


# ============================================================================
# MCP Prompts - Quick action buttons in Claude Desktop UI
# ============================================================================

@mcp.prompt()
def check_damage() -> str:
    """Check if a Pokemon can KO another"""
    return """I want to calculate damage between two Pokemon. Please help me by asking:
1. Which Pokemon is attacking? (e.g., Flutter Mane)
2. Which Pokemon is defending? (e.g., Incineroar)
3. What move are they using? (e.g., Moonblast)

Then use the damage calculator to show me the result with full transparency -
show both Pokemon's EVs, items, abilities, and the calculation breakdown."""


@mcp.prompt()
def build_team() -> str:
    """Help me build a VGC team"""
    return """I want to build a competitive VGC team. Please guide me through:
1. First, ask what playstyle I prefer (offensive, balanced, trick room, weather)
2. Help me pick a core Pokemon to build around
3. Suggest teammates that complement it with good type coverage
4. Show me recommended EV spreads for each Pokemon
5. Identify any weaknesses in the team composition

Let's start - what kind of team would I like to build?"""


@mcp.prompt()
def analyze_paste() -> str:
    """Analyze a Showdown team paste"""
    return """I have a team I want analyzed. I'll paste it in Pokemon Showdown format.

Please check for:
- Type weaknesses and defensive gaps
- Speed tier analysis (what outspeeds what)
- EV spread efficiency (are any EVs wasted?)
- Missing coverage or redundant moves
- Suggestions for improvement

I'll paste my team now..."""


@mcp.prompt()
def learn_vgc() -> str:
    """Learn VGC competitive basics"""
    return """I'm new to VGC (Video Game Championships) competitive Pokemon. Please explain:

1. What are EVs and how do they work?
2. What are common team archetypes (hyper offense, balance, trick room)?
3. What Pokemon are currently strong in the meta?
4. How do damage calculations work?

Start with the basics and I'll ask follow-up questions. Use the glossary and
education tools to help explain terms clearly."""


@mcp.prompt()
def optimize_spread() -> str:
    """Optimize a Pokemon's EV spread"""
    return """I want to optimize a Pokemon's EV spread. Please ask me:

1. Which Pokemon am I optimizing?
2. What threats should it survive? (e.g., "Flutter Mane Moonblast")
3. What speed tier should it hit? (e.g., "outspeed Landorus")
4. Is there a specific role? (attacker, support, tank)

Then calculate the most efficient spread that meets these benchmarks,
and suggest if a different nature could save EVs (like Showdown does)."""


@mcp.prompt()
def compare_speeds() -> str:
    """Compare speed tiers between Pokemon"""
    return """I want to compare speeds between Pokemon. Please help me understand:

1. Which Pokemon am I checking?
2. Do I want to include speed modifiers? (Tailwind, Trick Room, Choice Scarf)

Show me a speed tier chart with my Pokemon highlighted, and tell me what
outspeeds what under different conditions."""


@mcp.prompt()
def find_survival_spread() -> str:
    """Find EVs to survive a specific attack"""
    return """I want to find the EVs needed to survive a specific attack.

Please ask me:
1. What Pokemon is attacking? (e.g., Urshifu-Rapid-Strike)
2. What move are they using? (e.g., Surging Strikes)
3. What Pokemon needs to survive? (your Pokemon)
4. What nature do you want? (e.g., Jolly for speed, Impish for defense)

Use the find_survival_evs tool with the attacker's Smogon spread (auto-fetched).
IMPORTANT: Always show the EXACT attacker spread used (nature, EVs, item) and
the resulting survival percentage so I can verify the calculation."""


@mcp.prompt()
def check_survival() -> str:
    """Check if a spread survives an attack"""
    return """I want to check if my Pokemon's spread survives a specific attack.

Please ask me:
1. What Pokemon is attacking and with what move?
2. What is my Pokemon and its EXACT spread (HP/Def EVs, nature)?

Use calculate_damage_output and show:
- The damage range as a percentage
- Whether it survives (damage < 100%)
- The EXACT attacker spread used (so I can verify)"""


# ============================================================================
# Initialize shared state
# ============================================================================

# Initialize shared state
cache = APICache()
pokeapi = PokeAPIClient(cache)
smogon = SmogonStatsClient(cache)
pokepaste = PokePasteClient(cache)
team_manager = TeamManager()
analyzer = TeamAnalyzer()
build_manager = BuildStateManager()

# Register all tools
register_stats_tools(mcp, pokeapi)
register_damage_tools(mcp, pokeapi, smogon)  # Pass smogon for auto-fetching common spreads
register_speed_analysis_tools(mcp, pokeapi, team_manager, smogon)  # Combined speed + speed control tools
register_team_tools(mcp, pokeapi, team_manager, analyzer)
register_usage_tools(mcp, smogon)
register_spread_tools(mcp, pokeapi, smogon)  # Pass smogon for auto-fetching attacker spreads
register_import_export_tools(mcp, pokeapi, team_manager)
register_matchup_tools(mcp, team_manager)
register_core_tools(mcp, team_manager, smogon)

# Phase 3 tools
register_legality_tools(mcp, team_manager)
register_move_tools(mcp, pokeapi, smogon, team_manager)
register_priority_tools(mcp, team_manager)
register_ability_tools(mcp, team_manager)

# Phase 4 tools
register_coverage_tools(mcp, team_manager, pokeapi)

# Phase 6 tools - Meta-aware speed probability and optimization
register_context_tools(mcp, pokeapi, team_manager)
register_speed_probability_tools(mcp, smogon, pokeapi, team_manager)
register_meta_threat_tools(mcp, smogon, pokeapi, team_manager)

# Phase 7 tools - User experience improvements (workflow coordinators)
register_workflow_tools(mcp, pokeapi, smogon, team_manager, analyzer)

# Phase 9 tools - Advanced battle mechanics
register_item_tools(mcp, pokeapi)
register_chip_damage_tools(mcp, pokeapi)

# Life Orb Optimization & Multicalc tools
register_item_optimization_tools(mcp, pokeapi, smogon)
register_multicalc_tools(mcp, pokeapi, smogon)

# Phase 10 tools - Quality of life improvements
register_preset_tools(mcp, smogon)
register_sample_team_tools(mcp)
register_pokepaste_tools(mcp, pokepaste, pokeapi, smogon)

# Build state management (5 tools)
register_build_tools(mcp, build_manager, pokeapi)

# Team diff and reporting tools
register_diff_tools(mcp)
register_report_tools(mcp, pokeapi)

# Consolidated speed tools (complements speed_analysis and speed_probability)
register_speed_tools(mcp, pokeapi, smogon)

# Tournament matchup analysis tools
register_tournament_tools(mcp, pokepaste, pokeapi, smogon)

# New comprehensive tools (Part 2)
register_multi_threat_tools(mcp, pokeapi)
register_team_matchup_tools(mcp, pokeapi, smogon, team_manager)
register_tera_tools(mcp, pokeapi)
register_lead_tools(mcp, pokeapi)
register_speed_viz_tools(mcp, pokeapi, smogon)
register_readiness_tools(mcp, pokeapi)

# Beginner-friendly tools (Part 4)
register_glossary_tools(mcp)
register_education_tools(mcp, pokeapi)
register_help_tools(mcp)
register_build_checker_tools(mcp, pokeapi)
register_wizard_tools(mcp)
register_type_tools(mcp, pokeapi)

# Discoverability and onboarding tools (Part 0)
register_onboarding_tools(mcp)

# Game plan tools - opponent-aware strategy generation
register_game_plan_tools(mcp, pokeapi, team_manager, smogon)


def main():
    """Entry point for the MCP server (local stdio transport)."""
    logger.info("Starting VGC MCP server (stdio transport)")
    mcp.run()


def main_http(host: str = "0.0.0.0", port: int = None):
    """Entry point for HTTP/SSE transport (for remote/mobile access).

    Usage:
        python -c "from vgc_mcp.server import main_http; main_http()"
        # or with custom port:
        python -c "from vgc_mcp.server import main_http; main_http(port=3000)"

    Then add to Claude.ai connectors:
        URL: https://your-server.com/sse

    Note: Reads PORT from environment variable (for Render/Heroku deployment).
    """
    import os
    import uvicorn

    # Use PORT env var (Render sets this), fallback to 8000
    if port is None:
        port = int(os.environ.get("PORT", 8000))
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import JSONResponse, Response
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware

    # Create SSE transport - note the trailing slash for Mount compatibility
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp._mcp_server.run(
                streams[0], streams[1], mcp._mcp_server.create_initialization_options()
            )
        return Response()

    async def health_check(request):
        """Health check endpoint for monitoring."""
        tool_count = len(mcp._tool_manager._tools) if hasattr(mcp, '_tool_manager') else 0
        return JSONResponse({
            "status": "healthy",
            "service": "vgc-mcp",
            "tools": tool_count
        })

    async def root(request):
        """Root endpoint with server info."""
        tool_count = len(mcp._tool_manager._tools) if hasattr(mcp, '_tool_manager') else 0
        return JSONResponse({
            "name": "vgc-mcp",
            "version": "1.0.0",
            "description": "Pokemon VGC MCP Server - damage calcs, spreads, team building",
            "tools": tool_count,
            "endpoints": {
                "sse": "/sse",
                "health": "/health",
                "messages": "/messages/"
            }
        })

    app = Starlette(
        routes=[
            Route("/", endpoint=root, methods=["GET"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
                allow_credentials=True,
            )
        ]
    )

    logger.info(f"Starting VGC MCP server on http://{host}:{port}")
    logger.info(f"SSE endpoint: http://{host}:{port}/sse")
    logger.info(f"Health check: http://{host}:{port}/health")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
