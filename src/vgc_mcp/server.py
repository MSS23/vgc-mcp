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
from .tools.speed_probability_tools import register_speed_probability_tools, register_visualize_outspeed_tool
from .tools.meta_threat_tools import register_meta_threat_tools
from .tools.workflow_tools import register_workflow_tools
from .tools.item_tools import register_item_tools
from .tools.chip_damage_tools import register_chip_damage_tools
from .tools.lead_tools import register_lead_tools
from .tools.preset_tools import register_preset_tools
from .tools.sample_team_tools import register_sample_team_tools
from .tools.pokepaste_tools import register_pokepaste_tools
from .tools.build_tools import register_build_tools
from .tools.diff_tools import register_diff_tools
from .tools.report_tools import register_report_tools
from .tools.speed_tools import register_speed_tools

# Note: MCP-UI is only enabled in vgc-mcp-lite for smaller footprint
# Full server focuses on tool completeness over visual components


# Initialize MCP server
mcp = FastMCP(
    "VGC Team Builder",
    instructions="MCP server for VGC Pokemon team building with damage calc, usage stats, and team analysis"
)

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
register_speed_analysis_tools(mcp, pokeapi, team_manager)  # Combined speed + speed control tools
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
register_visualize_outspeed_tool(mcp, smogon, pokeapi)  # Interactive UI for outspeed %
register_meta_threat_tools(mcp, smogon, pokeapi, team_manager)

# Phase 7 tools - User experience improvements (workflow coordinators)
register_workflow_tools(mcp, pokeapi, smogon, team_manager, analyzer)

# Phase 9 tools - Advanced battle mechanics
register_item_tools(mcp, pokeapi)
register_chip_damage_tools(mcp, pokeapi)
register_lead_tools(mcp, team_manager)

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

    app = Starlette(
        routes=[
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
