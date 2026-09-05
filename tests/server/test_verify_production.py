"""Tests for the post-deployment production verifier."""

import json
from email.message import Message

import pytest

from scripts import verify_production


@pytest.mark.parametrize("bad", ["chaos", "damage", "mass", "error", None])
def test_functional_checks_catch_real_failures(monkeypatch, bad):
    sets = {"top_spreads": [{"nature": "Adamant"}], "_meta": {
        "source_url": "https://www.smogon.com/stats/2026-08/chaos/example-1630.json",
        "month": "2026-08", "format": "example", "rating": 1630}}
    damage = {"ohko_percent": 0, "details": {"outcome_distribution": [
        {"damage": 16, "probability": .5}, {"damage": 19, "probability": .5}]}}
    if bad == "chaos":
        sets["top_spreads"] = []
    elif bad == "damage":
        damage["ohko_percent"] = 100
    elif bad == "mass":
        damage["details"]["outcome_distribution"][0]["probability"] = .2
    elif bad == "error":
        damage = {"success": False, "error": "api_error"}
    calls = []
    def post(url, request, session_id=None):
        calls.append(request["params"]["name"])
        payload = sets if len(calls) == 1 else damage
        return {"result": {"content": [{"type": "text", "text": json.dumps(payload)}]}}, Message()
    monkeypatch.setattr(verify_production, "_post_mcp", post)
    if bad:
        with pytest.raises(RuntimeError):
            verify_production.verify_functional_tools("https://example.invalid/mcp", "session")
    else:
        verify_production.verify_functional_tools("https://example.invalid/mcp", "session")
        assert calls == ["get_common_sets", "calculate_move_outcomes"]


def test_sse_json_extracts_json_rpc_envelope():
    body = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n'

    assert verify_production._sse_json(body)["id"] == 1


def test_sse_json_rejects_response_without_data_event():
    with pytest.raises(ValueError, match="SSE data event"):
        verify_production._sse_json("event: ping\n\n")


def test_wait_for_revision_requires_exact_deployed_sha(monkeypatch):
    responses = iter(
        [
            (200, Message(), '{"status":"healthy","revision":"old"}'),
            (200, Message(), '{"status":"healthy","revision":"expected"}'),
        ]
    )
    monotonic_values = iter([0, 1, 2])

    monkeypatch.setattr(verify_production, "_request", lambda _url: next(responses))
    monkeypatch.setattr(verify_production.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(verify_production.time, "sleep", lambda _seconds: None)

    health = verify_production.wait_for_revision(
        "https://example.invalid", "expected", timeout=10
    )

    assert health["revision"] == "expected"
