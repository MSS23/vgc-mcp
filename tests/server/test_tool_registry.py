"""Fail-fast guarantees for automatic MCP tool discovery."""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools import _resolve_kwargs, register_all


def test_missing_required_registration_dependency_is_fatal():
    def register_example(mcp, unavailable_client):
        raise AssertionError("registration should not be reached")

    with pytest.raises(RuntimeError, match="unavailable_client"):
        _resolve_kwargs(register_example, {"mcp": object()})


def test_duplicate_tool_name_is_fatal(monkeypatch):
    def register_first(mcp):
        @mcp.tool()
        def duplicate_name() -> str:
            return "first"

    def register_second(mcp):
        @mcp.tool()
        def duplicate_name() -> str:
            return "second"

    monkeypatch.setattr(
        "vgc_mcp.tools.discover_register_functions",
        lambda: [("first_tools", register_first), ("second_tools", register_second)],
    )

    with pytest.raises(RuntimeError, match="duplicate tool name: duplicate_name"):
        register_all(FastMCP("registry-test"))


def test_empty_tool_module_is_fatal(monkeypatch):
    def register_empty(mcp):
        return None

    monkeypatch.setattr(
        "vgc_mcp.tools.discover_register_functions",
        lambda: [("empty_tools", register_empty)],
    )

    with pytest.raises(RuntimeError, match="registered no tools"):
        register_all(FastMCP("registry-test"))
