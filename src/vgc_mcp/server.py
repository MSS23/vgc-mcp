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

from vgc_mcp_core.api.cache import APICache
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.pokepaste import PokePasteClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.config import logger
from vgc_mcp_core.presentation import PRESENTATION_INSTRUCTIONS
from vgc_mcp_core.state import BattleStateManager, BuildStateManager
from vgc_mcp_core.team.analysis import TeamAnalyzer
from vgc_mcp_core.team.manager import TeamManager

from .tools import register_all as register_all_tools

# This is the plain-MCP server. It does NOT depend on mcp-ui-server. Any
# MCP-UI version of these tools lives in a sibling project so this one
# stays client-agnostic (Claude Desktop, Claude.ai, ChatGPT, etc).


# Initialize MCP server — shared presentation rules in vgc_mcp_core.presentation
mcp = FastMCP("VGC Team Builder", instructions=PRESENTATION_INSTRUCTIONS)


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
battle_manager = BattleStateManager()

# Auto-discover and register every `*_tools.py` module in tools/.
# Each register_*_tools function is introspected and given the deps it asks for.
# To add a new tool category: drop a `<area>_tools.py` file in tools/ exposing
# `register_<area>_tools(mcp, ...)` — no edit to this file required.
register_all_tools(
    mcp,
    pokeapi=pokeapi,
    smogon=smogon,
    pokepaste=pokepaste,
    team_manager=team_manager,
    analyzer=analyzer,
    build_manager=build_manager,
    battle_manager=battle_manager,
)


def main():
    """Entry point for the MCP server (local stdio transport)."""
    logger.info("Starting VGC MCP server (stdio transport)")
    mcp.run()


def main_http(host: str = "0.0.0.0", port: int = None):
    """Entry point for remote HTTP transports.

    Serves BOTH remote MCP transports side by side:
    - /mcp — Streamable HTTP (modern; what Claude.ai custom connectors and
      current MCP clients expect)
    - /sse + /messages/ — legacy HTTP+SSE (older clients, mcp-remote bridge)

    Usage:
        python -c "from vgc_mcp.server import main_http; main_http()"
        # or with custom port:
        python -c "from vgc_mcp.server import main_http; main_http(port=3000)"

    Then add to Claude.ai connectors:
        URL: https://your-server.com/mcp   (fallback: /sse for legacy clients)

    Note: Reads PORT from environment variable (for Render/Heroku deployment).
    """
    import os

    import uvicorn

    # Use PORT env var (Render sets this), fallback to 8000
    if port is None:
        port = int(os.environ.get("PORT", 8000))
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Mount, Route

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
                "mcp": "/mcp",
                "sse": "/sse",
                "health": "/health",
                "messages": "/messages/"
            }
        })

    # Streamable HTTP (modern MCP transport). streamable_http_app() lazily
    # creates the session manager and returns a Starlette app whose only
    # route is /mcp — we reuse that route in our combined app and run the
    # session manager via the outer app's lifespan (mounted sub-app
    # lifespans do NOT propagate in Starlette, so this must be explicit).
    streamable_app = mcp.streamable_http_app()

    app = Starlette(
        routes=[
            Route("/", endpoint=root, methods=["GET"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
            *streamable_app.routes,  # /mcp
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
                allow_credentials=True,
                expose_headers=["Mcp-Session-Id"],
            )
        ],
        lifespan=lambda app: mcp.session_manager.run(),
    )

    logger.info(f"Starting VGC MCP server on http://{host}:{port}")
    logger.info(f"Streamable HTTP endpoint: http://{host}:{port}/mcp")
    logger.info(f"SSE endpoint (legacy): http://{host}:{port}/sse")
    logger.info(f"Health check: http://{host}:{port}/health")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
