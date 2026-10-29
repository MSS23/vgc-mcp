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

import os

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.cache import APICache
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.pokepaste import PokePasteClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.config import logger
from vgc_mcp_core.presentation import PRESENTATION_INSTRUCTIONS
from vgc_mcp_core.state.session_registry import make_scoped_managers
from vgc_mcp_core.team.analysis import TeamAnalyzer

from .profiles import CORE_TOOLS, resolve_profile
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


@mcp.prompt()
def prepare_for_tournament() -> str:
    """Get a team ready for a Regional or other event"""
    return """I'm taking a team to a tournament and want it checked end to end.

I'll paste my team in Showdown format. Then please:
1. Run prepare_team on it and tell me which regulation and usage month you used.
2. Lead with the three most important fixes, one line each.
3. Show any spread changes as Showdown pastes I can copy.
4. List the meta threats my team struggles with and how to play around them.
5. Offer the full report as an Excel or PDF export.

I'll paste my team now..."""


@mcp.prompt()
def explain_replay() -> str:
    """Explain what happened in a Showdown replay"""
    return """I want to understand a battle I played. I'll share a Pokemon Showdown
replay link.

Please run analyze_replay on it and then explain:
1. The turn where the game was won or lost, in one or two sentences.
2. Each side's leads and what they were trying to do.
3. Two or three decisions I could have made differently, with the reason.
4. Any damage roll or speed tie that decided a key turn.

Keep it short and lead with the answer. Here's the replay link..."""


# ============================================================================
# Initialize shared state
# ============================================================================

# Initialize shared state. API clients and the stateless analyzer are safely
# shared across all sessions (read-only / cache-backed). The three MUTABLE
# managers (team, build, battle) are session-scoped: `make_scoped_managers`
# returns proxies that transparently resolve to the calling MCP session's own
# manager set, so concurrent HTTP users can't clobber each other's teams,
# builds, or battles. In stdio mode everything resolves to one "default"
# session — identical to the previous single-user behavior.
cache = APICache()
pokeapi = PokeAPIClient(cache)
smogon = SmogonStatsClient(cache)
pokepaste = PokePasteClient(cache)
analyzer = TeamAnalyzer()
session_registry, team_manager, build_manager, battle_manager = make_scoped_managers()

# Auto-discover and register every `*_tools.py` module in tools/.
# Each register_*_tools function is introspected and given the deps it asks for.
# To add a new tool category: drop a `<area>_tools.py` file in tools/ exposing
# `register_<area>_tools(mcp, ...)` — no edit to this file required.
REGISTERED_TOOL_MODULE_COUNT = register_all_tools(
    mcp,
    pokeapi=pokeapi,
    smogon=smogon,
    pokepaste=pokepaste,
    team_manager=team_manager,
    analyzer=analyzer,
    build_manager=build_manager,
    battle_manager=battle_manager,
)
REGISTERED_TOOL_COUNT = len(mcp._tool_manager._tools)


def _build_core_server(full: FastMCP) -> FastMCP:
    """Second server over the same registered tools, limited to CORE_TOOLS.

    Tool and prompt objects are shared, not re-registered, so both servers run
    the same code and per-session state (keyed by the MCP request context)
    behaves identically on either endpoint.
    """
    missing = sorted(CORE_TOOLS - set(full._tool_manager._tools))
    if missing:
        raise RuntimeError(f"Core profile names unregistered tools: {missing}")
    core = FastMCP(full.name, instructions=PRESENTATION_INSTRUCTIONS)
    for name in sorted(CORE_TOOLS):
        core._tool_manager._tools[name] = full._tool_manager._tools[name]
    core._prompt_manager._prompts.update(full._prompt_manager._prompts)
    return core


mcp_core = _build_core_server(mcp)
CORE_TOOL_COUNT = len(mcp_core._tool_manager._tools)
DEFAULT_PROFILE = resolve_profile()
served_mcp = mcp_core if DEFAULT_PROFILE == "core" else mcp


def _build_middleware(cors_cls, middleware_wrapper):
    """Assemble the ASGI middleware stack for the HTTP app.

    Order (outermost first): CORS → rate-limit → auth. Auth and rate-limiting
    are opt-in via env vars so local/existing deployments are unaffected:
    - VGC_MCP_API_KEY: require `Authorization: Bearer <key>` when set.
    - VGC_MCP_RATE_LIMIT: max requests/IP per VGC_MCP_RATE_WINDOW seconds
      (default window 60s). Unset or 0 disables limiting.
    - VGC_MCP_TRUSTED_PROXY_HOPS: how many proxies in front of the app append
      to X-Forwarded-For (default 1, Render's load balancer). The limiter keys
      on that hop, never the client-supplied leftmost entry. 0 = socket peer.
    """
    import os

    from .http_middleware import BearerAuthMiddleware, RateLimitMiddleware

    stack = [
        middleware_wrapper(
            cors_cls,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            # Token-less MCP needs no credentials, and the
            # `allow_origins=["*"]` + `allow_credentials=True` combination is
            # rejected by browsers per the Fetch spec. Drop credentials.
            allow_credentials=False,
            expose_headers=["Mcp-Session-Id"],
        ),
    ]

    try:
        rate_limit = int(os.environ.get("VGC_MCP_RATE_LIMIT", "0"))
    except ValueError:
        rate_limit = 0
    try:
        rate_window = float(os.environ.get("VGC_MCP_RATE_WINDOW", "60"))
    except ValueError:
        rate_window = 60.0
    try:
        proxy_hops = int(os.environ.get("VGC_MCP_TRUSTED_PROXY_HOPS", "1"))
    except ValueError:
        proxy_hops = 1
    if rate_limit > 0:
        stack.append(
            middleware_wrapper(
                RateLimitMiddleware,
                limit=rate_limit,
                window=rate_window,
                trusted_proxy_hops=proxy_hops,
            )
        )
        logger.info(f"Rate limiting enabled: {rate_limit} req / {rate_window:g}s per IP")

    api_key = os.environ.get("VGC_MCP_API_KEY") or None
    if api_key:
        stack.append(middleware_wrapper(BearerAuthMiddleware, api_key=api_key))
        logger.info("Bearer-token auth enabled on MCP endpoints")

    return stack


def main():
    """Entry point for the MCP server (local stdio transport)."""
    logger.info(
        "Starting VGC MCP server (stdio transport, %s profile, %d tools)",
        DEFAULT_PROFILE,
        len(served_mcp._tool_manager._tools),
    )
    served_mcp.run()


def main_http(host: str = "0.0.0.0", port: int = None):
    """Entry point for remote HTTP transports.

    Serves BOTH remote MCP transports side by side:
    - /mcp — Streamable HTTP (modern; what Claude.ai custom connectors and
      current MCP clients expect), default tool profile (core unless
      VGC_MCP_PROFILE=full)
    - /mcp/full — Streamable HTTP with every registered tool
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

    app = create_http_app()

    logger.info(f"Starting VGC MCP server on http://{host}:{port}")
    logger.info(f"Streamable HTTP endpoint: http://{host}:{port}/mcp ({DEFAULT_PROFILE} profile)")
    logger.info(f"Full tool set: http://{host}:{port}/mcp/full")
    logger.info(f"SSE endpoint (legacy): http://{host}:{port}/sse")
    logger.info(f"Health check: http://{host}:{port}/health")
    uvicorn.run(app, host=host, port=port)


def create_http_app():
    """Build and return the combined Starlette ASGI app (no server started).

    Split out from ``main_http`` so it can be exercised by a Starlette
    ``TestClient`` without binding a socket. Serves ``/mcp`` (Streamable HTTP,
    default profile), ``/mcp/full`` (every tool), legacy ``/sse`` +
    ``/messages/``, plus ``/`` and ``/health``.
    """
    import contextlib

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
            await served_mcp._mcp_server.run(
                streams[0], streams[1], served_mcp._mcp_server.create_initialization_options()
            )
        return Response()

    class StreamableHTTPCompat:
        """ASGI shim: serve a request as if the client had hit ``/mcp``.

        Streamable-HTTP clients (claude.ai custom connectors) POST their
        `initialize` to the exact URL they're given. Anyone configured with
        the legacy ``/sse`` URL used to get a bare 405 and a "Couldn't
        connect" in the client. Rewriting the path to ``/mcp`` and delegating
        to the Streamable HTTP app makes ``POST /sse`` just work, while
        ``GET /sse`` still serves the legacy HTTP+SSE handshake above.
        """

        def __init__(self, app, path: str = "/mcp"):
            self.app = app
            self.path = path

        async def __call__(self, scope, receive, send):
            scope = dict(scope)
            scope["path"] = self.path
            scope["raw_path"] = self.path.encode()
            await self.app(scope, receive, send)

    def tool_counts() -> dict:
        # "tools" is what /mcp lists; "tools_total" is what /mcp/full lists.
        return {
            "profile": DEFAULT_PROFILE,
            "tools": len(served_mcp._tool_manager._tools),
            "tools_total": len(mcp._tool_manager._tools),
        }

    async def health_check(request):
        """Health check endpoint for monitoring."""
        return JSONResponse({
            "status": "healthy",
            "service": "vgc-mcp",
            "revision": os.environ.get("RENDER_GIT_COMMIT"),
            "branch": os.environ.get("RENDER_GIT_BRANCH"),
            "tool_modules": REGISTERED_TOOL_MODULE_COUNT,
            **tool_counts(),
            "active_sessions": session_registry.session_count(),
        })

    async def root(request):
        """Root endpoint with server info."""
        import importlib.metadata

        try:
            version = importlib.metadata.version("vgc-mcp")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        return JSONResponse({
            "name": "vgc-mcp",
            "version": version,
            "revision": os.environ.get("RENDER_GIT_COMMIT"),
            "branch": os.environ.get("RENDER_GIT_BRANCH"),
            "description": "Pokemon VGC MCP Server - damage calcs, spreads, team building",
            "tool_modules": REGISTERED_TOOL_MODULE_COUNT,
            **tool_counts(),
            "endpoints": {
                "mcp": "/mcp",
                "mcp_full": "/mcp/full",
                "sse": "/sse",
                "health": "/health",
                "messages": "/messages/"
            },
            "connect": "Use /mcp (Streamable HTTP) in MCP clients, or /mcp/full "
                       "for every tool; /sse is the legacy HTTP+SSE transport "
                       "(POST /sse is forwarded to /mcp)."
        })

    # This is a deliberately public endpoint. FastMCP's default transport
    # security only allows localhost Host/Origin headers (DNS-rebinding
    # protection for locally-run servers), which 421-rejects every request
    # that reaches a hosted deployment (Host: vgc-mcp.onrender.com,
    # Origin: https://claude.ai, ...). Rebinding attacks target private
    # services behind the client's network position; they don't apply to a
    # public TLS host, so disable the check here. The stdio path (main) is
    # unaffected.
    from mcp.server.transport_security import TransportSecuritySettings
    for server in (mcp, mcp_core):
        server.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )

    # Streamable HTTP (modern MCP transport). streamable_http_app() lazily
    # creates the session manager and returns a Starlette app whose only
    # route is /mcp — we reuse that route in our combined app and run the
    # session manager via the outer app's lifespan (mounted sub-app
    # lifespans do NOT propagate in Starlette, so this must be explicit).
    # The full server always lives at /mcp/full. /mcp serves the default
    # profile: the core server, or the full one again when
    # VGC_MCP_PROFILE=full (through a path rewrite, because one session
    # manager owns one route).
    mcp.settings.streamable_http_path = "/mcp/full"
    full_app = mcp.streamable_http_app()
    if served_mcp is mcp_core:
        streamable_app = mcp_core.streamable_http_app()
        mcp_routes = [*streamable_app.routes, *full_app.routes]
    else:
        streamable_app = StreamableHTTPCompat(full_app, "/mcp/full")
        mcp_routes = [
            Route("/mcp", endpoint=streamable_app, methods=["GET", "POST", "DELETE"]),
            *full_app.routes,
        ]

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())
            if served_mcp is mcp_core:
                await stack.enter_async_context(mcp_core.session_manager.run())
            yield

    app = Starlette(
        routes=[
            Route("/", endpoint=root, methods=["GET"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
            # GET /sse = legacy HTTP+SSE handshake. POST /sse = a
            # streamable-HTTP client pointed at the legacy URL — forward it
            # to the /mcp handler instead of 405ing (see StreamableHTTPCompat).
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Route(
                "/sse",
                endpoint=StreamableHTTPCompat(streamable_app),
                methods=["POST", "DELETE"],
            ),
            Mount("/messages/", app=sse.handle_post_message),
            *mcp_routes,  # /mcp and /mcp/full
        ],
        middleware=_build_middleware(CORSMiddleware, Middleware),
        lifespan=lifespan,
    )

    return app


if __name__ == "__main__":
    main()
