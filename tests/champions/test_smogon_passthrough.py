"""Regression tests for Champions Smogon spread passthrough (cluster F4).

[F4-a] smogon_helpers.get_common_spreads / get_common_spread must carry the
       Champions `sps` + `format_system` fields through, not silently emit
       evs={} (which degrades a Champions Pokemon to a 0-investment mainline
       build).
[F4-b] preset_tools.get_smogon_spreads must surface the Stat Point allocation
       for Champions spreads instead of an all-zeros EV table.
"""

import asyncio

import pytest

from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.tools.smogon_helpers import get_common_spread, get_common_spreads


def _champions_spread():
    """A real Champions spread as produced by SmogonStatsClient._parse_spread."""
    client = SmogonStatsClient.__new__(SmogonStatsClient)
    parsed = client._parse_spread("Timid:2/0/0/32/0/32", champions=True)
    parsed["usage"] = 50.0
    return parsed


class _FakeSmogonClient:
    """Minimal stand-in returning one Champions spread."""

    async def get_pokemon_usage(self, name, format_name=None, *args, **kwargs):
        return {
            "name": "Flutter Mane",
            "usage_percent": 50.0,
            "spreads": [_champions_spread()],
            "items": {"Choice Specs": 40.0},
            "abilities": {"Protosynthesis": 99.0},
            "tera_types": {},
            "_meta": {"format": "champions", "month": "2026-05", "rating": 1500},
        }


def test_parse_spread_champions_shape():
    """Sanity: source returns sps + format_system, NO evs key."""
    spread = _champions_spread()
    assert spread["format_system"] == "champions"
    assert "evs" not in spread
    assert spread["sps"]["special_attack"] == 32
    assert spread["sps"]["speed"] == 32


@pytest.mark.asyncio
async def test_get_common_spreads_preserves_champions_fields():
    """[F4-a] sps + format_system must survive the dict mapping."""
    spreads = await get_common_spreads(_FakeSmogonClient(), "flutter-mane")
    assert len(spreads) == 1
    row = spreads[0]
    assert row["format_system"] == "champions"
    assert row["sps"] is not None
    assert row["sps"]["special_attack"] == 32
    assert row["sps"]["speed"] == 32
    # evs stays empty (champions builds have no EVs) — but it must NOT be the
    # only stat source, which was the bug.
    assert row["evs"] == {}


@pytest.mark.asyncio
async def test_get_common_spread_singular_preserves_champions_fields():
    """[F4-a] singular helper delegates and must carry fields too."""
    row = await get_common_spread(_FakeSmogonClient(), "flutter-mane")
    assert row is not None
    assert row["format_system"] == "champions"
    assert row["sps"]["speed"] == 32


@pytest.mark.asyncio
async def test_get_common_spreads_mainline_unchanged():
    """Mainline spreads still expose evs and a None sps."""

    class _MainlineClient:
        async def get_pokemon_usage(self, name, *a, **k):
            client = SmogonStatsClient.__new__(SmogonStatsClient)
            parsed = client._parse_spread("Modest:252/0/4/252/0/0", champions=False)
            parsed["usage"] = 30.0
            return {
                "spreads": [parsed],
                "items": {"Choice Specs": 50.0},
                "abilities": {"Protosynthesis": 90.0},
            }

    spreads = await get_common_spreads(_MainlineClient(), "x")
    row = spreads[0]
    assert row["format_system"] == "mainline"
    assert row["sps"] is None
    assert row["evs"]["special_attack"] == 252


def _register_and_get_tool(smogon):
    """Register preset tools against a fake MCP and return get_smogon_spreads."""
    from mcp.server.fastmcp import FastMCP

    from vgc_mcp.tools.preset_tools import register_preset_tools

    mcp = FastMCP("test")
    captured = {}
    orig_tool = mcp.tool

    def patched_tool(*a, **k):
        decorator = orig_tool(*a, **k)

        def wrap(fn):
            captured[fn.__name__] = fn
            return decorator(fn)

        return wrap

    mcp.tool = patched_tool
    register_preset_tools(mcp, smogon=smogon)
    return captured["get_smogon_spreads"]


@pytest.mark.asyncio
async def test_get_smogon_spreads_surfaces_champions_stat_points():
    """[F4-b] Champions spreads surface SP allocation, not an all-zero EV table."""
    tool = _register_and_get_tool(_FakeSmogonClient())
    result = await tool("flutter-mane")
    rows = result["spreads"]
    assert len(rows) == 1
    row = rows[0]
    assert row["format_system"] == "champions"
    assert row["sps"]["special_attack"] == 32
    assert row["sps"]["speed"] == 32
    # The real allocation is exposed and labelled as Stat Points.
    assert row["allocation_label"] == "Stat Points"
    assert row["spread_string"] == "Timid:2/0/0/32/0/32"
    # Not silently all-zeros (the bug surfaced evs={} with no sps).
    assert any(v > 0 for v in row["sps"].values())
