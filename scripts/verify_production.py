"""Wait for and smoke-test the exact VGC MCP revision deployed on Render."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_URL = "https://vgc-mcp.onrender.com"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 90,
) -> tuple[int, Any, str]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers or {},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.headers, response.read().decode("utf-8")


def _sse_json(body: str) -> dict[str, Any]:
    for line in body.splitlines():
        if line.startswith("data:"):
            return json.loads(line.removeprefix("data:").strip())
    raise ValueError("MCP response did not contain an SSE data event")


def _post_mcp(
    mcp_url: str,
    payload: dict[str, Any],
    *,
    session_id: str | None = None,
) -> tuple[dict[str, Any] | None, Any]:
    headers = dict(MCP_HEADERS)
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    status, response_headers, body = _request(
        mcp_url,
        method="POST",
        payload=payload,
        headers=headers,
    )
    if status == 202 and not body:
        return None, response_headers
    if status != 200:
        raise RuntimeError(f"MCP request returned HTTP {status}: {body[:500]}")
    return _sse_json(body), response_headers


def wait_for_revision(base_url: str, expected_sha: str | None, timeout: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error = "no response"
    while time.monotonic() < deadline:
        try:
            status, _, body = _request(f"{base_url}/health")
            health = json.loads(body)
            revision = health.get("revision")
            if status == 200 and health.get("status") == "healthy":
                if not expected_sha or revision == expected_sha:
                    return health
                last_error = f"healthy but running {revision!r}, expected {expected_sha!r}"
            else:
                last_error = f"HTTP {status}: {body[:300]}"
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = str(exc)
        print(f"Waiting for Render deployment: {last_error}", flush=True)
        time.sleep(15)
    raise TimeoutError(f"Production did not reach the expected revision: {last_error}")


def verify_mcp(base_url: str, health: dict[str, Any]) -> None:
    mcp_url = f"{base_url}/mcp"
    initialize, response_headers = _post_mcp(
        mcp_url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "production-smoke", "version": "1.0"},
            },
        },
    )
    if not initialize or initialize.get("result", {}).get("serverInfo", {}).get("name") != "VGC Team Builder":
        raise RuntimeError(f"Unexpected initialize response: {initialize}")

    session_id = response_headers.get("Mcp-Session-Id")
    if not session_id:
        raise RuntimeError("Initialize response omitted Mcp-Session-Id")

    _post_mcp(
        mcp_url,
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        session_id=session_id,
    )
    tools_envelope, _ = _post_mcp(
        mcp_url,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        session_id=session_id,
    )
    tools = tools_envelope.get("result", {}).get("tools", []) if tools_envelope else []
    if len(tools) != health.get("tools") or len(tools) < 200:
        raise RuntimeError(
            f"Tool surface mismatch: MCP listed {len(tools)}, health reported {health.get('tools')}"
        )

    damage_tool = next((tool for tool in tools if tool.get("name") == "calculate_damage_output"), None)
    properties = (damage_tool or {}).get("inputSchema", {}).get("properties", {})
    if "attacker_spe_evs" not in properties:
        raise RuntimeError("Production damage schema is missing attacker_spe_evs")
    booster = properties.get("attacker_booster_energy", {})
    booster_types = {branch.get("type") for branch in booster.get("anyOf", [])}
    if booster.get("default", object()) is not None or booster_types != {"boolean", "null"}:
        raise RuntimeError(f"Unexpected Booster Energy schema: {booster}")

    welcome, _ = _post_mcp(
        mcp_url,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "welcome_new_user", "arguments": {}},
        },
        session_id=session_id,
    )
    if not welcome or welcome.get("result", {}).get("isError"):
        raise RuntimeError(f"Live tool call failed: {welcome}")

    try:
        _request(
            mcp_url,
            method="DELETE",
            headers={"Accept": "application/json, text/event-stream", "Mcp-Session-Id": session_id},
        )
    except urllib.error.HTTPError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_URL)
    parser.add_argument("--expected-sha")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    try:
        health = wait_for_revision(base_url, args.expected_sha, args.timeout)
        verify_mcp(base_url, health)
    except Exception as exc:
        print(f"Production verification failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Production verified: revision={health.get('revision')} "
        f"tools={health.get('tools')} url={base_url}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
