"""Core tool descriptions stay short: every word is paid for on each request."""

import asyncio

MAX_CORE_DESCRIPTION = 700


def test_core_tool_descriptions_are_short():
    from vgc_mcp.server import mcp_core

    long = {
        t.name: len(t.description or "")
        for t in asyncio.run(mcp_core.list_tools())
        if len(t.description or "") > MAX_CORE_DESCRIPTION
    }
    assert not long, f"core descriptions over {MAX_CORE_DESCRIPTION} chars: {long}"
