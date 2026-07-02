"""Champions Reg MA legality enforcement (Agent T1).

Covers:
- check_pokemon_legality tool: off-allowlist mons report legal=False under an
  allowlist regulation; on-allowlist mons (incl. Megas) report legal=True.
- validate_team_rules / validate_team_legality: an all-off-allowlist Champions
  team is flagged invalid; an allowlisted team passes.

These call the ACTUAL @mcp.tool handlers (and the underlying rule function),
not just the pure helpers, asserting allowlist behavior end-to-end.
"""

from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.legality_tools import register_legality_tools
from vgc_mcp_core.models.pokemon import BaseStats, Nature, PokemonBuild
from vgc_mcp_core.models.team import Team, TeamSlot
from vgc_mcp_core.rules.vgc_rules import validate_team_rules

REG_MA = "reg_ma_champs"


def _make_slot(name, item=None):
    pokemon = MagicMock()
    pokemon.name = name
    pokemon.item = item
    slot = MagicMock()
    slot.pokemon = pokemon
    return slot


def _mk_build(name):
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(
            hp=80, attack=80, defense=80,
            special_attack=80, special_defense=80, speed=80,
        ),
        nature=Nature.SERIOUS,
        types=["normal"],
    )


@pytest.fixture
def mock_team_manager():
    manager = MagicMock()
    team = MagicMock()
    team.slots = []
    manager.get_current_team.return_value = team
    return manager


@pytest.fixture
def tools(mock_team_manager):
    mcp = FastMCP("test")
    register_legality_tools(mcp, mock_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


# ---------------------------------------------------------------------------
# T1-a: check_pokemon_legality
# ---------------------------------------------------------------------------

class TestCheckPokemonLegalityAllowlist:
    @pytest.mark.parametrize("name", ["flutter-mane", "chien-pao", "koraidon"])
    async def test_off_allowlist_is_illegal(self, tools, name):
        fn = tools["check_pokemon_legality"].fn
        result = await fn(pokemon_name=name, regulation=REG_MA)
        assert result["legal"] is False, result
        assert result["status"] == "illegal"
        assert "not on the reg ma allowlist" in result["message"].lower()

    @pytest.mark.parametrize("name", ["incineroar", "manectric", "manectric-mega"])
    async def test_on_allowlist_is_legal(self, tools, name):
        fn = tools["check_pokemon_legality"].fn
        result = await fn(pokemon_name=name, regulation=REG_MA)
        assert result["legal"] is True, result
        assert result["status"] == "allowed"

    async def test_mainline_path_unchanged(self, tools):
        # Banlist regulation: restricted mon still reported legal with the
        # restricted flag set (byte-for-byte unchanged behavior).
        fn = tools["check_pokemon_legality"].fn
        result = await fn(pokemon_name="koraidon", regulation="reg_g")
        assert result["legal"] is True
        assert result["restricted"] is True
        assert result["status"] == "restricted"


# ---------------------------------------------------------------------------
# T1-b: validate_team_rules / validate_team_legality
# ---------------------------------------------------------------------------

class TestValidateTeamAllowlist:
    def test_off_allowlist_team_is_invalid(self):
        team = Team(
            name="bad",
            slots=[
                TeamSlot(pokemon=_mk_build("flutter-mane"), slot_index=0),
                TeamSlot(pokemon=_mk_build("chien-pao"), slot_index=1),
            ],
        )
        result = validate_team_rules(team, REG_MA)
        assert result["valid"] is False, result
        joined = " ".join(result["violations"]).lower()
        assert "flutter-mane" in joined
        assert "chien-pao" in joined
        assert "not legal" in joined

    def test_allowlisted_team_passes(self):
        team = Team(
            name="good",
            slots=[
                TeamSlot(pokemon=_mk_build("incineroar"), slot_index=0),
                TeamSlot(pokemon=_mk_build("manectric-mega"), slot_index=1),
            ],
        )
        result = validate_team_rules(team, REG_MA)
        assert result["valid"] is True, result
        assert result["violations"] == []

    def test_allowlist_skips_restricted_logic(self):
        # Even with a mainline-restricted mon (koraidon) on the team, the
        # allowlist path reports it via the allowlist violation, NOT the
        # "too many restricted" message.
        team = Team(
            name="x",
            slots=[TeamSlot(pokemon=_mk_build("koraidon"), slot_index=0)],
        )
        result = validate_team_rules(team, REG_MA)
        assert result["restricted_count"] == 0
        joined = " ".join(result["violations"]).lower()
        assert "restricted" not in joined
        assert "koraidon" in joined

    def test_mainline_validation_unchanged(self):
        team = Team(
            name="m",
            slots=[
                TeamSlot(pokemon=_mk_build("incineroar"), slot_index=0),
                TeamSlot(pokemon=_mk_build("flutter-mane"), slot_index=1),
            ],
        )
        result = validate_team_rules(team, "reg_f")
        assert result["valid"] is True
        assert "restricted_count" in result


class TestValidateTeamLegalityTool:
    async def test_tool_flags_off_allowlist_team(self, mock_team_manager):
        team = MagicMock()
        team.slots = [
            _make_slot("flutter-mane"),
            _make_slot("chien-pao"),
        ]
        mock_team_manager.get_current_team.return_value = team
        mcp = FastMCP("test")
        register_legality_tools(mcp, mock_team_manager)
        tool_map = {t.name: t for t in mcp._tool_manager._tools.values()}
        fn = tool_map["validate_team_legality"].fn
        result = await fn(regulation=REG_MA)
        assert result["valid"] is False, result
        joined = " ".join(result["violations"]).lower()
        assert "flutter-mane" in joined and "chien-pao" in joined
