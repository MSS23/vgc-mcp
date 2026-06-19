"""Champions (Reg MA) regression test for workflow tool `suggest_ev_spread`.

Bug: in a Champions session the SP-scale answer (primary showdown_paste,
summary, and the `champions` block) was correct, but the TOP-LEVEL `spread`
dict still carried EV-scale numbers (spa:252, total:252) and a
`mainline_showdown_paste` with an 'EVs: 252 SpA' line was also present. An LLM
reading the raw response could surface those EV numbers as the answer.

These tests go through the REAL MCP dispatch path (`server.mcp.call_tool`) — the
same path Claude uses — and assert no per-stat>32 / total>66 / 'EVs:' appears as
a primary field in a Champions response. The mainline path is guarded unchanged.

PokeAPI is live (per the task contract).
"""

import json

import pytest

from vgc_mcp import server
from vgc_mcp_core.rules.regulation_loader import get_regulation_config


def _text(res):
    block = res[0] if isinstance(res, (list, tuple)) else res
    return getattr(block, "text", str(block))


async def _call(tool, args, reg):
    cfg = get_regulation_config()
    cfg.set_session_regulation(reg, by_user=True)
    try:
        return json.loads(_text(await server.mcp.call_tool(tool, args)))
    finally:
        cfg.clear_session_override()


_SP_STATS = ("hp", "atk", "def", "spa", "spd", "spe")


@pytest.mark.asyncio
async def test_champions_top_level_spread_is_sp_scale():
    r = await _call(
        "suggest_ev_spread",
        {
            "pokemon_name": "flutter-mane",
            "outspeed_targets": ["iron-bundle"],
            "prioritize": "offense",
        },
        "reg_ma_champs",
    )

    assert r["format_system"] == "champions"

    # Top-level spread must read in SP units, not EV units.
    spread = r["spread"]
    assert spread.get("stat_units") == "Stat Points (SPs)"
    for stat in _SP_STATS:
        assert 0 <= spread[stat] <= 32, f"{stat}={spread[stat]} exceeds SP cap 32"
    assert spread["total"] <= 66, f"SP total {spread['total']} exceeds 66"

    # Primary paste must be the SP paste.
    assert "SPs:" in r["showdown_paste"]
    assert "EVs:" not in r["showdown_paste"]

    # The EV-scale paste must NOT masquerade as the primary answer.
    assert "mainline_showdown_paste" not in r
    # It may still be present, but only under a clearly-secondary key.
    if "ev_equivalent_showdown_paste" in r:
        assert "EVs:" in r["ev_equivalent_showdown_paste"]

    # No 'EVs:' / per-stat>32 / total>66 anywhere in the primary surface
    # (everything except the explicitly-secondary EV reference + champions block).
    primary = {
        k: v
        for k, v in r.items()
        if k not in ("ev_equivalent_showdown_paste", "champions")
    }
    blob = json.dumps(primary)
    assert "EVs:" not in blob


@pytest.mark.asyncio
async def test_champions_block_still_correct():
    r = await _call(
        "suggest_ev_spread",
        {"pokemon_name": "flutter-mane", "prioritize": "offense"},
        "reg_ma_champs",
    )
    champ = r["champions"]
    assert champ["format_system"] == "champions"
    assert "SPs:" in champ["showdown_paste"]
    assert champ["spread_sps"]["total"] <= 66
    # Top-level spread mirrors the champions SP allocation.
    for stat in _SP_STATS:
        assert r["spread"][stat] == champ["spread_sps"][stat]


@pytest.mark.asyncio
async def test_mainline_unchanged():
    r = await _call(
        "suggest_ev_spread",
        {
            "pokemon_name": "flutter-mane",
            "outspeed_targets": ["iron-bundle"],
            "prioritize": "offense",
        },
        "reg_f",
    )

    assert r["format_system"] == "mainline"
    assert "champions" not in r

    # Mainline keeps EV-scale spread + the mainline EV paste, unchanged.
    spread = r["spread"]
    assert "stat_units" not in spread
    # EV-scale numbers are present (the offensive flutter-mane spread maxes a stat).
    assert max(spread["spa"], spread["spe"]) > 32
    assert "EVs:" in r["showdown_paste"]
    assert "SPs:" not in r["showdown_paste"]
    assert "EVs:" in r["mainline_showdown_paste"]
    assert "ev_equivalent_showdown_paste" not in r
