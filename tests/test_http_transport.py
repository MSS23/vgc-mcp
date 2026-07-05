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
