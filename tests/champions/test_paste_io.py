"""Tests for Showdown paste import/export with the Champions SPs line."""

from vgc_mcp_core.formats.showdown import (
    parse_showdown_pokemon,
    export_pokemon_to_showdown,
    parsed_to_sp_spread,
)


CHAMPIONS_PASTE = """Garchomp @ Choice Band
Ability: Rough Skin
Tera Type: Ground
SPs: 4 HP / 32 Atk / 30 Spe
Adamant Nature
- Earthquake
- Dragon Claw
- Stone Edge
- U-turn"""

MAINLINE_PASTE = """Dragapult @ Choice Specs
Ability: Infiltrator
Tera Type: Ghost
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Shadow Ball
- Draco Meteor
- Flamethrower
- U-turn"""


class TestImportSPs:
    def test_parses_sps_line(self):
        parsed = parse_showdown_pokemon(CHAMPIONS_PASTE)
        assert parsed.sps is not None
        assert parsed.sps["hp"] == 4
        assert parsed.sps["atk"] == 32
        assert parsed.sps["spe"] == 30
        # EVs untouched (default zero)
        assert parsed.evs["hp"] == 0

    def test_mainline_paste_has_no_sps(self):
        parsed = parse_showdown_pokemon(MAINLINE_PASTE)
        assert parsed.sps is None
        assert parsed.evs["spe"] == 252

    def test_parsed_to_sp_spread_round_trip(self):
        parsed = parse_showdown_pokemon(CHAMPIONS_PASTE)
        sps = parsed_to_sp_spread(parsed)
        assert sps is not None
        assert sps.hp == 4
        assert sps.attack == 32
        assert sps.speed == 30
        assert sps.total == 66

    def test_parsed_mainline_returns_none_sps(self):
        parsed = parse_showdown_pokemon(MAINLINE_PASTE)
        assert parsed_to_sp_spread(parsed) is None

    def test_stat_points_synonym(self):
        paste = CHAMPIONS_PASTE.replace("SPs:", "Stat Points:")
        parsed = parse_showdown_pokemon(paste)
        assert parsed.sps is not None
        assert parsed.sps["atk"] == 32


class TestExportSPs:
    def test_emits_sps_line(self):
        out = export_pokemon_to_showdown(
            species="Garchomp",
            item="Choice Band",
            ability="Rough Skin",
            tera_type="Ground",
            sps={"hp": 4, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 30},
            nature="Adamant",
            moves=["Earthquake", "Dragon Claw", "Stone Edge", "U-turn"],
        )
        assert "SPs: 4 HP / 32 Atk / 30 Spe" in out
        assert "EVs:" not in out  # SPs replaces EVs

    def test_mainline_export_unchanged(self):
        out = export_pokemon_to_showdown(
            species="Dragapult",
            item="Choice Specs",
            ability="Infiltrator",
            tera_type="Ghost",
            evs={"hp": 4, "atk": 0, "def": 0, "spa": 252, "spd": 0, "spe": 252},
            nature="Timid",
            moves=["Shadow Ball"],
        )
        assert "EVs: 4 HP / 252 SpA / 252 Spe" in out
        assert "SPs:" not in out

    def test_sps_takes_precedence_when_both_provided(self):
        # Defensive: if a caller passes both, the SPs line wins.
        out = export_pokemon_to_showdown(
            species="Garchomp",
            evs={"hp": 252, "atk": 252},
            sps={"hp": 4, "atk": 32, "spe": 30},
            nature="Adamant",
        )
        assert "SPs:" in out
        assert "EVs:" not in out
