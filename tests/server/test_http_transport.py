"""Tests for the HTTP transport layer, auth, and rate limiting.

The MCP `[remote]` extra (starlette/uvicorn) is optional; skip cleanly if it
isn't installed so the default `[dev]` test job doesn't fail.
"""

import importlib.util
import json

import pytest

from vgc_mcp.profiles import CORE_TOOLS, FULL_TOOL_COUNT

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


def test_rate_limit_prunes_expired_buckets():
    from vgc_mcp.http_middleware import RateLimitMiddleware

    rl = RateLimitMiddleware(app=None, limit=5, window=60.0)
    for i in range(10_001):
        rl._allowed(f"10.0.{i // 256}.{i % 256}", now=0.0)
    assert rl._allowed("1.2.3.4", now=120.0)  # every old bucket has expired
    assert len(rl._buckets) == 1


def test_rate_limit_ignores_spoofed_leftmost_forwarded_for():
    """Rotating the client-controlled leftmost XFF entry must not reset the limit."""
    from starlette.middleware import Middleware

    from vgc_mcp.http_middleware import RateLimitMiddleware

    client = _dummy_app_client(
        Middleware(RateLimitMiddleware, limit=2, window=60.0)
    )
    codes = [
        client.get(
            "/mcp", headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}
        ).status_code
        for i in range(4)
    ]
    assert codes[:2] == [200, 200]
    assert codes[2:] == [429, 429]


def test_client_ip_uses_trusted_hop():
    from vgc_mcp.http_middleware import RateLimitMiddleware

    def scope(xff: str | None) -> dict:
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return {"type": "http", "headers": headers, "client": ("127.0.0.9", 1)}

    one = RateLimitMiddleware(app=None, limit=1)  # type: ignore[arg-type]
    two = RateLimitMiddleware(app=None, limit=1, trusted_proxy_hops=2)  # type: ignore[arg-type]
    none = RateLimitMiddleware(app=None, limit=1, trusted_proxy_hops=0)  # type: ignore[arg-type]
    assert one._client_ip(scope("spoof, 198.51.100.4")) == "198.51.100.4"
    assert two._client_ip(scope("spoof, 198.51.100.4, 10.1.1.1")) == "198.51.100.4"
    assert two._client_ip(scope("198.51.100.4")) == "198.51.100.4"
    assert none._client_ip(scope("spoof, 198.51.100.4")) == "127.0.0.9"
    assert one._client_ip(scope(None)) == "127.0.0.9"


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


def test_health_endpoint(http_client, monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    resp = http_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["tool_modules"] == 52
    assert body["profile"] == "core"
    assert body["tools"] == len(CORE_TOOLS)
    assert body["tools_total"] == FULL_TOOL_COUNT
    assert "active_sessions" in body
    assert body["revision"] == "abc123"
    assert body["branch"] == "main"


def test_root_endpoint(http_client):
    resp = http_client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["endpoints"]["mcp"] == "/mcp"
    assert body["endpoints"]["mcp_full"] == "/mcp/full"
    assert body["tool_modules"] == 52
    assert body["tools"] == len(CORE_TOOLS)
    assert body["tools_total"] == FULL_TOOL_COUNT


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


def _start_mcp_session(http_client, request_id, path="/mcp"):
    init_body = {
        **_INITIALIZE_BODY,
        "id": request_id,
        "params": {
            **_INITIALIZE_BODY["params"],
            "clientInfo": {"name": f"probe-{request_id}", "version": "1.0"},
        },
    }
    response = http_client.post(path, json=init_body, headers=_MCP_HEADERS)
    assert response.status_code == 200
    session_id = response.headers["Mcp-Session-Id"]
    ready_headers = {**_MCP_HEADERS, "Mcp-Session-Id": session_id}
    ready = http_client.post(
        path,
        json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        headers=ready_headers,
    )
    assert ready.status_code == 202
    return session_id


def _mcp_request(http_client, session_id, body, path="/mcp"):
    response = http_client.post(
        path, json=body, headers={**_MCP_HEADERS, "Mcp-Session-Id": session_id}
    )
    assert response.status_code == 200
    data_line = next(line for line in response.text.splitlines() if line.startswith("data:"))
    return json.loads(data_line.removeprefix("data:").strip())


def _call_mcp_tool(http_client, session_id, request_id, name, arguments, path="/mcp"):
    response = http_client.post(
        path,
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers={**_MCP_HEADERS, "Mcp-Session-Id": session_id},
    )
    assert response.status_code == 200
    data_line = next(line for line in response.text.splitlines() if line.startswith("data:"))
    envelope = json.loads(data_line.removeprefix("data:").strip())
    assert not envelope["result"].get("isError", False)
    return json.loads(envelope["result"]["content"][0]["text"])


def test_streamable_http_sessions_isolate_regulation_choice(http_client):
    full = "/mcp/full"
    session_a = _start_mcp_session(http_client, 101, full)
    session_b = _start_mcp_session(http_client, 102, full)

    _call_mcp_tool(
        http_client, session_a, 103, "set_session_regulation", {"regulation": "Reg F"}, full
    )
    _call_mcp_tool(
        http_client, session_b, 104, "set_session_regulation", {"regulation": "Reg H"}, full
    )

    current_a = _call_mcp_tool(
        http_client, session_a, 105, "get_current_regulation_info", {}, full
    )
    current_b = _call_mcp_tool(
        http_client, session_b, 106, "get_current_regulation_info", {}, full
    )
    assert current_a["current_regulation"] == "reg_f"
    assert current_b["current_regulation"] == "reg_h"


def _listed_tool_names(http_client, path, request_id):
    session = _start_mcp_session(http_client, request_id, path)
    envelope = _mcp_request(
        http_client,
        session,
        {"jsonrpc": "2.0", "id": request_id + 1, "method": "tools/list", "params": {}},
        path,
    )
    return {tool["name"] for tool in envelope["result"]["tools"]}


def test_mcp_lists_exactly_the_core_profile(http_client):
    assert _listed_tool_names(http_client, "/mcp", 201) == set(CORE_TOOLS)


def test_mcp_full_lists_every_registered_tool(http_client):
    names = _listed_tool_names(http_client, "/mcp/full", 211)
    assert len(names) == FULL_TOOL_COUNT
    assert set(CORE_TOOLS) <= names


def test_core_endpoint_rejects_non_core_tools(http_client):
    session = _start_mcp_session(http_client, 221)
    envelope = _mcp_request(
        http_client,
        session,
        {
            "jsonrpc": "2.0",
            "id": 222,
            "method": "tools/call",
            "params": {"name": "get_current_regulation_info", "arguments": {}},
        },
    )
    assert envelope["result"]["isError"] is True


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
