"""Champions (Reg MA) regression for compare_speed (speed_analysis_tools).

compare_speed must dispatch on format_system: in a Champions session the
``*_speed_evs`` arguments are Stat Points (0-32, 66 budget) and Speed uses the
SP formula (Flutter Mane Timid 32 SP -> 205, Dragapult Jolly 32 SP -> 213),
with the per-mon investment field labelled ``sps``. The mainline EV path must
stay byte-for-byte unchanged (32 EV -> 174 / 182, field labelled ``evs``).

These call the tool through the REAL MCP dispatch path (server.mcp.call_tool),
the same path Claude uses. PokeAPI is live.
"""

import json

import pytest

from vgc_mcp import server
from vgc_mcp_core.rules.regulation_loader import get_regulation_config


def _text(res):
    block = res[0] if isinstance(res, (list, tuple)) else res
    return getattr(block, "text", str(block))


async def _call(tool, args, reg):
    get_regulation_config().set_session_regulation(reg, by_user=True)
    return json.loads(_text(await server.mcp.call_tool(tool, args)))


_ARGS = {
    "pokemon1_name": "flutter-mane",
    "pokemon2_name": "dragapult",
    "pokemon1_nature": "timid",
    "pokemon1_speed_evs": 32,
    "pokemon2_nature": "jolly",
    "pokemon2_speed_evs": 32,
}


@pytest.mark.asyncio
async def test_compare_speed_champions_uses_sp_path():
    r = await _call("compare_speed", dict(_ARGS), "reg_ma_champs")

    # 32 SP saturates to the 252-EV stat under the SP formula.
    assert r["pokemon1"]["final_speed"] == 205
    assert r["pokemon2"]["final_speed"] == 213

    # Dragapult (213) outspeeds Flutter Mane (205).
    assert r["winner"] == "dragapult"
    assert r["difference"] == 8

    # Investment field is labelled 'sps', not 'evs', and tagged champions.
    assert r["pokemon1"]["sps"] == 32
    assert r["pokemon2"]["sps"] == 32
    assert "evs" not in r["pokemon1"]
    assert "evs" not in r["pokemon2"]
    assert r["format_system"] == "champions"
    assert "SP" in r["stat_units"]


@pytest.mark.asyncio
async def test_compare_speed_mainline_unchanged():
    r = await _call("compare_speed", dict(_ARGS), "reg_f")

    # 32 EV is a tiny investment under the EV formula.
    assert r["pokemon1"]["final_speed"] == 174
    assert r["pokemon2"]["final_speed"] == 182

    # Investment field stays 'evs'; no champions tagging on the mainline path.
    assert r["pokemon1"]["evs"] == 32
    assert r["pokemon2"]["evs"] == 32
    assert "sps" not in r["pokemon1"]
    assert "sps" not in r["pokemon2"]
    assert "format_system" not in r
