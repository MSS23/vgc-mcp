# -*- coding: utf-8 -*-
"""VGC Team Builder MCP Server - Lite Version.

A lightweight version with ~49 essential tools optimized for smaller models
like Llama 3.3 70B. Full version has 157 tools which can overwhelm
models with limited context or tool selection capability.

Essential tools included:
- Team management (add, remove, view, analyze)
- Damage calculations
- Stats and speed analysis
- Import/export (Showdown paste)
- EV spread optimization
- Coverage analysis
- Matchup analysis
- Usage data

Usage:
    python -m vgc_mcp_lite
    # or
    vgc-mcp-lite (after pip install)
"""

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.cache import APICache
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.team.analysis import TeamAnalyzer

# Build state manager for bidirectional UI sync (from core)
from vgc_mcp_core.state import BuildStateManager

# Import only the essential tool modules
# Target: ~49 tools (well under Goose's 60 recommendation)
from .tools.stats_tools import register_stats_tools          # 2 tools
from .tools.damage_tools import register_damage_tools        # 3 tools
from .tools.speed_tools import register_speed_tools          # 7 tools
from .tools.team_tools import register_team_tools            # 9 tools
from .tools.usage_tools import register_usage_tools          # 6 tools
from .tools.spread_tools import register_spread_tools        # 6 tools
from .tools.import_export_tools import register_import_export_tools  # 5 tools
from .tools.coverage_tools import register_coverage_tools    # 6 tools
from .tools.matchup_tools import register_matchup_tools      # 6 tools
from .tools.report_tools import register_report_tools        # 1 tool
from .tools.build_tools import register_build_tools          # 5 tools
from .tools.diff_tools import register_diff_tools            # 1 tool
# Total: ~57 tools

# MCP-UI support
from .ui import register_ui_resources


# Initialize MCP server
mcp = FastMCP(
    "VGC Team Builder Lite",
    instructions="Lite MCP server for VGC Pokemon team building (~49 essential tools)"
)

# Initialize shared state
cache = APICache()
pokeapi = PokeAPIClient(cache)
smogon = SmogonStatsClient(cache)
team_manager = TeamManager()
analyzer = TeamAnalyzer()
build_manager = BuildStateManager()

# Register ONLY essential tools (targeting ~49 total, under Goose's 60 limit)

# Core team management (9 tools)
register_team_tools(mcp, pokeapi, team_manager, analyzer)

# Damage calculations (3 tools)
register_damage_tools(mcp, pokeapi, smogon)

# Stats (2 tools)
register_stats_tools(mcp, pokeapi)

# Speed analysis (7 tools)
register_speed_tools(mcp, pokeapi, smogon)

# Import/export (4 tools)
register_import_export_tools(mcp, pokeapi, team_manager)

# EV spreads (6 tools)
register_spread_tools(mcp, pokeapi, smogon)

# Coverage (6 tools)
register_coverage_tools(mcp, team_manager, pokeapi)

# Matchup (6 tools)
register_matchup_tools(mcp, team_manager)

# Usage data (6 tools)
register_usage_tools(mcp, smogon)

# Report generation (1 tool)
register_report_tools(mcp, pokeapi)

# Build state management (5 tools)
register_build_tools(mcp, build_manager, pokeapi)

# Team diff comparison (1 tool)
register_diff_tools(mcp)

# Register MCP-UI resources
register_ui_resources(mcp)


def main():
    """Entry point for the lite MCP server (local stdio transport)."""
    logger.info("Starting VGC MCP Lite server (stdio transport)")
    mcp.run()


def main_http(host: str = "0.0.0.0", port: int = 8000):
    """Entry point for HTTP/SSE transport (for remote/mobile access).

    Usage:
        python -c "from vgc_mcp_lite.server import main_http; main_http()"
        # or with custom port:
        python -c "from vgc_mcp_lite.server import main_http; main_http(port=3000)"

    Then add to Goose/Claude.ai:
        URL: https://your-server.com/sse
    """
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import JSONResponse, Response

    # Create SSE transport
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
            "service": "vgc-mcp-lite",
            "tools": tool_count,
            "version": "lite"
        })

    app = Starlette(
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )

    logger.info(f"Starting VGC MCP Lite server on http://{host}:{port}")
    logger.info(f"SSE endpoint: http://{host}:{port}/sse")
    logger.info(f"Health check: http://{host}:{port}/health")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
