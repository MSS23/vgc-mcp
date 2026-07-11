"""Tests for the HTTP transport layer, auth, and rate limiting.

The MCP `[remote]` extra (starlette/uvicorn) is optional; skip cleanly if it
isn't installed so the default `[dev]` test job doesn't fail.
"""

import importlib.util

import pytest

REMOTE_AVAILABLE = importlib.util.find_spec("starlette") is not None

pytestmark = pytest.mark.skipif(
    not REMOTE_AVAILABLE, reason="requires the [remote] extra (starlette)"
)


# ---------------------------------------------------------------------------
# Middleware unit tests (dummy ASGI app — no MCP session manager needed)
# ---------------------------------------------------------------------------

def _dummy_app_client(*middlewares):
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    async def ok(request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[
            Route("/", ok),
            Route("/health", ok),
            Route("/mcp", ok, methods=["GET", "POST"]),
        ],
        middleware=list(middlewares),
    )
    return TestClient(app)


def test_bearer_auth_blocks_without_token():
    from starlette.middleware import Middleware

    from vgc_mcp.http_middleware import BearerAuthMiddleware

    client = _dummy_app_client(
        Middleware(BearerAuthMiddleware, api_key="secret123")
    )
    # Protected endpoint rejected without token.
    assert client.get("/mcp").status_code == 401
    # Exempt endpoints always pass.
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_bearer_auth_allows_with_token():
    from starlette.middleware import Middleware

    from vgc_mcp.http_middleware import BearerAuthMiddleware

    client = _dummy_app_client(
        Middleware(BearerAuthMiddleware, api_key="secret123")
    )
    resp = client.get("/mcp", headers={"Authorization": "Bearer secret123"})
    assert resp.status_code == 200
    assert client.get("/mcp", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_bearer_auth_disabled_when_no_key():
    from starlette.middleware import Middleware

    from vgc_mcp.http_middleware import BearerAuthMiddleware

    client = _dummy_app_client(Middleware(BearerAuthMiddleware, api_key=None))
    assert client.get("/mcp").status_code == 200


def test_rate_limit_returns_429_over_limit():
    from starlette.middleware import Middleware

    from vgc_mcp.http_middleware import RateLimitMiddleware

    client = _dummy_app_client(
        Middleware(RateLimitMiddleware, limit=3, window=60.0)
    )
    codes = [client.get("/mcp").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]
    # Health is exempt from limiting.
    assert client.get("/health").status_code == 200


def test_rate_limit_disabled_when_zero():
    from starlette.middleware import Middleware

    from vgc_mcp.http_middleware import RateLimitMiddleware

    client = _dummy_app_client(Middleware(RateLimitMiddleware, limit=0))
    assert all(client.get("/mcp").status_code == 200 for _ in range(10))


# ---------------------------------------------------------------------------
# Real app smoke tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def http_client():
    from starlette.testclient import TestClient

    from vgc_mcp.server import create_http_app

    app = create_http_app()
    with TestClient(app) as client:
        yield client


def test_health_endpoint(http_client):
    resp = http_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["tools"] > 150
    assert "active_sessions" in body


def test_root_endpoint(http_client):
    resp = http_client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["endpoints"]["mcp"] == "/mcp"
    assert body["tools"] > 150


def test_mcp_endpoint_exists(http_client):
    # A bare GET without the MCP handshake headers should not 404 (route is
    # wired) and should not 500 (transport handles it gracefully).
    resp = http_client.get("/mcp")
    assert resp.status_code != 404
    assert resp.status_code < 500


_INITIALIZE_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "probe", "version": "1.0"},
    },
}

_MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def test_streamable_http_initialize_on_mcp(http_client):
    resp = http_client.post("/mcp", json=_INITIALIZE_BODY, headers=_MCP_HEADERS)
    assert resp.status_code == 200
    assert "VGC Team Builder" in resp.text


def test_post_sse_forwards_to_streamable_http(http_client):
    """A streamable-HTTP client pointed at the legacy /sse URL must not 405.

    Regression for the claude.ai "Couldn't connect" failure: connectors POST
    initialize to the exact URL they're given. POST /sse now behaves exactly
    like POST /mcp (see StreamableHTTPCompat in server.py).
    """
    resp = http_client.post("/sse", json=_INITIALIZE_BODY, headers=_MCP_HEADERS)
    assert resp.status_code == 200
    assert "VGC Team Builder" in resp.text


def test_get_sse_still_serves_legacy_transport():
    # The legacy GET handshake must survive the POST compat route. Opening a
    # real SSE stream would block the TestClient on an endless response, so
    # assert the routing table instead: GET /sse and POST /sse are separate
    # routes, with GET mapping to the legacy handler and POST to the
    # streamable-HTTP compat shim.
    from vgc_mcp.server import create_http_app

    app = create_http_app()
    sse_routes = {
        tuple(sorted(r.methods - {"HEAD"})): r
        for r in app.routes
        if getattr(r, "path", None) == "/sse" and getattr(r, "methods", None)
    }
    assert ("GET",) in sse_routes, "GET /sse (legacy SSE handshake) route missing"
    post_route = sse_routes.get(("DELETE", "POST"))
    assert post_route is not None, "POST/DELETE /sse compat route missing"
    assert type(post_route.endpoint).__name__ == "StreamableHTTPCompat"
