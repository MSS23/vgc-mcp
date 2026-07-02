"""Regression tests for the import/export MCP tools in a Champions session.

These call the ACTUAL registered MCP tools (via FastMCP.call_tool) rather than
the pure showdown helpers, to lock in that a Champions SPs paste imports as a
``format_system='champions'`` build and exports an ``SPs:`` line — not a 0-EV
mainline build (which produced Flutter Mane SpA 155 / Spe 170 instead of
187/205 before the fix).
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.import_export_tools import register_import_export_tools
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.team.manager import TeamManager

CHAMPIONS_PASTE = """Manectric-Mega @ Life Orb
Ability: Intimidate
Tera Type: Electric
SPs: 2 HP / 32 SpA / 32 Spe
Timid Nature
- Thunderbolt
- Volt Switch
- Overheat
- Protect"""

FLUTTER_CHAMP_PASTE = """Flutter Mane @ Booster Energy
Ability: Protosynthesis
Tera Type: Fairy
SPs: 32 SpA / 32 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Icy Wind
- Protect"""

MAINLINE_PASTE = """Dragapult @ Choice Specs
Ability: Infiltrator
Tera Type: Ghost
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Shadow Ball
- Draco Meteor
- Flamethrower
- U-turn"""


def _make_server():
    mcp = FastMCP("test")
    api = PokeAPIClient()
    tm = TeamManager()
    register_import_export_tools(mcp, api, tm)
    return mcp, tm


def _result(call_output):
    """Unwrap FastMCP.call_tool's content list into the tool's dict result."""
    return json.loads(call_output[0].text)


class TestImportChampions:
    @pytest.mark.asyncio
    async def test_import_sps_builds_champions(self):
        mcp, tm = _make_server()
        res = _result(
            await mcp.call_tool(
                "import_showdown_pokemon",
                {"paste": CHAMPIONS_PASTE, "add_to_team": True},
            )
        )
        assert res["success"] is True
        pk = tm.get_pokemon(0)
        assert pk.format_system == "champions"
        assert pk.sps is not None
        assert pk.sps.special_attack == 32
        assert pk.sps.speed == 32
        # Mainline EV path must NOT be populated.
        assert pk.evs.special_attack == 0

    @pytest.mark.asyncio
    async def test_import_sps_produces_correct_stats(self):
        mcp, tm = _make_server()
        _result(
            await mcp.call_tool(
                "import_showdown_pokemon",
                {"paste": FLUTTER_CHAMP_PASTE, "add_to_team": True},
            )
        )
        pk = tm.get_pokemon(0)
        stats = calculate_all_stats(pk)
        # 32 SP saturates to the 252-EV stat: Timid Flutter Mane = 187 SpA / 205 Spe.
        assert stats["special_attack"] == 187
        assert stats["speed"] == 205

    @pytest.mark.asyncio
    async def test_import_surfaces_regulation_auto_detected(self):
        mcp, tm = _make_server()
        res = _result(
            await mcp.call_tool(
                "import_showdown_pokemon",
                {"paste": CHAMPIONS_PASTE, "add_to_team": True},
            )
        )
        assert "regulation_auto_detected" in res
        # Mega form -> Champions (current default reg, MB).
        assert res["regulation_auto_detected"].get("regulation") == "reg_mb_champs"

    @pytest.mark.asyncio
    async def test_import_response_includes_parsed_sps(self):
        mcp, tm = _make_server()
        res = _result(
            await mcp.call_tool(
                "import_showdown_pokemon",
                {"paste": CHAMPIONS_PASTE, "add_to_team": False},
            )
        )
        assert res["parsed"]["sps"] == {
            "hp": 2, "atk": 0, "def": 0, "spa": 32, "spd": 0, "spe": 32,
        }


class TestImportTeamChampions:
    @pytest.mark.asyncio
    async def test_import_team_builds_champions(self):
        mcp, tm = _make_server()
        res = _result(
            await mcp.call_tool(
                "import_showdown_team",
                {"paste": CHAMPIONS_PASTE, "clear_existing": True},
            )
        )
        assert res["imported_count"] == 1
        assert "regulation_auto_detected" in res
        pk = tm.get_pokemon(0)
        assert pk.format_system == "champions"
        assert pk.sps.special_attack == 32


class TestExportChampions:
    @pytest.mark.asyncio
    async def test_export_pokemon_emits_sps_line(self):
        mcp, tm = _make_server()
        _result(
            await mcp.call_tool(
                "import_showdown_pokemon",
                {"paste": CHAMPIONS_PASTE, "add_to_team": True},
            )
        )
        out = _result(await mcp.call_tool("export_pokemon_to_paste", {"slot": 1}))
        paste = out["paste"]
        assert "SPs: 2 HP / 32 SpA / 32 Spe" in paste
        assert "EVs:" not in paste
        assert paste.splitlines()[0].startswith("Manectric-Mega")

    @pytest.mark.asyncio
    async def test_export_team_emits_sps_line(self):
        mcp, tm = _make_server()
        _result(
            await mcp.call_tool(
                "import_showdown_pokemon",
                {"paste": CHAMPIONS_PASTE, "add_to_team": True},
            )
        )
        out = _result(await mcp.call_tool("export_team_to_paste", {}))
        paste = out["paste"]
        assert "SPs: 2 HP / 32 SpA / 32 Spe" in paste
        assert "EVs:" not in paste
        assert "Manectric-Mega" in paste.splitlines()[0]

    @pytest.mark.asyncio
    async def test_champions_round_trips_through_tools(self):
        mcp, tm = _make_server()
        _result(
            await mcp.call_tool(
                "import_showdown_pokemon",
                {"paste": CHAMPIONS_PASTE, "add_to_team": True},
            )
        )
        exported = _result(
            await mcp.call_tool("export_pokemon_to_paste", {"slot": 1})
        )["paste"]

        # Re-import the exported paste into a fresh server.
        mcp2, tm2 = _make_server()
        _result(
            await mcp2.call_tool(
                "import_showdown_pokemon",
                {"paste": exported, "add_to_team": True},
            )
        )
        pk2 = tm2.get_pokemon(0)
        assert pk2.format_system == "champions"
        assert pk2.sps.special_attack == 32
        assert pk2.sps.speed == 32
        assert pk2.sps.hp == 2


class TestMainlineUnchanged:
    @pytest.mark.asyncio
    async def test_mainline_import_export_unchanged(self):
        mcp, tm = _make_server()
        _result(
            await mcp.call_tool(
                "import_showdown_pokemon",
                {"paste": MAINLINE_PASTE, "add_to_team": True},
            )
        )
        pk = tm.get_pokemon(0)
        assert pk.format_system == "mainline"
        assert pk.sps is None
        assert pk.evs.special_attack == 252
        assert pk.evs.speed == 252

        out = _result(await mcp.call_tool("export_pokemon_to_paste", {"slot": 1}))
        paste = out["paste"]
        assert "EVs: 4 HP / 252 SpA / 252 Spe" in paste
        assert "SPs:" not in paste
