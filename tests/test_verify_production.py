"""Tests for the post-deployment production verifier."""

from email.message import Message

import pytest

from scripts import verify_production


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
