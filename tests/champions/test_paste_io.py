"""Tests for Showdown paste import/export with the Champions SPs line."""

import pytest

from vgc_mcp_core.models.pokemon import (
    BaseStats,
    EVSpread,
    Nature,
    PokemonBuild,
    StatPointSpread,
)
from vgc_mcp_core.formats.showdown import (
    parse_showdown_pokemon,
    export_pokemon_to_showdown,
    format_showdown_species,
    parsed_to_pokemon_build,
    parsed_to_sp_spread,
    pokemon_build_to_showdown,
    ShowdownParseError,
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


def _make_build(name, **kwargs):
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(
            hp=80, attack=80, defense=80,
            special_attack=80, special_defense=80, speed=80,
        ),
        nature=kwargs.pop("nature", Nature.SERIOUS),
        types=kwargs.pop("types", ["normal"]),
        **kwargs,
    )


class TestSpeciesFormatting:
    """F2-a: hyphenated forms must keep hyphens; spaced base species use spaces."""

    @pytest.mark.parametrize(
        "internal,expected",
        [
            ("charizard-mega-y", "Charizard-Mega-Y"),
            ("manectric-mega", "Manectric-Mega"),
            ("urshifu-rapid-strike", "Urshifu-Rapid-Strike"),
            ("calyrex-shadow", "Calyrex-Shadow"),
            ("tauros-paldea-aqua", "Tauros-Paldea-Aqua"),
            ("indeedee-f", "Indeedee-F"),
        ],
    )
    def test_hyphenated_forms_keep_hyphens(self, internal, expected):
        assert format_showdown_species(internal) == expected

    @pytest.mark.parametrize(
        "internal,expected",
        [
            ("flutter-mane", "Flutter Mane"),
            ("iron-hands", "Iron Hands"),
            ("tapu-koko", "Tapu Koko"),
            ("great-tusk", "Great Tusk"),
        ],
    )
    def test_spaced_base_species_use_spaces(self, internal, expected):
        assert format_showdown_species(internal) == expected

    def test_pokemon_build_to_showdown_preserves_form_hyphens(self):
        build = _make_build("urshifu-rapid-strike")
        first_line = pokemon_build_to_showdown(build).splitlines()[0]
        assert first_line == "Urshifu-Rapid-Strike"

    def test_pokemon_build_to_showdown_spaced_species(self):
        build = _make_build("flutter-mane")
        first_line = pokemon_build_to_showdown(build).splitlines()[0]
        assert first_line == "Flutter Mane"


class TestSpValidation:
    """F2-b: out-of-range / over-budget SPs raise ShowdownParseError, not ValidationError."""

    def test_per_stat_cap_raises_parse_error(self):
        paste = (
            "Garchomp @ Choice Band\n"
            "SPs: 4 HP / 40 SpA / 30 Spe\n"
            "Adamant Nature"
        )
        parsed = parse_showdown_pokemon(paste)
        with pytest.raises(ShowdownParseError, match="SpA 40 exceeds"):
            parsed_to_sp_spread(parsed)

    def test_total_budget_raises_parse_error(self):
        paste = (
            "Garchomp\n"
            "SPs: 32 HP / 32 Atk / 32 Spe\n"
            "Adamant Nature"
        )
        parsed = parse_showdown_pokemon(paste)
        with pytest.raises(ShowdownParseError, match="exceeds Champions budget of 66"):
            parsed_to_sp_spread(parsed)

    def test_valid_sps_still_parse(self):
        paste = (
            "Garchomp\n"
            "SPs: 4 HP / 32 Atk / 30 Spe\n"
            "Adamant Nature"
        )
        sps = parsed_to_sp_spread(parse_showdown_pokemon(paste))
        assert sps.total == 66


class TestParsedToPokemonBuild:
    """F2-c: shared helper builds correct-format PokemonBuild and round-trips."""

    def test_champions_paste_round_trip(self):
        paste = (
            "Charizard-Mega-Y @ Charizardite Y\n"
            "Ability: Drought\n"
            "Tera Type: Fire\n"
            "SPs: 4 HP / 32 SpA / 30 Spe\n"
            "Timid Nature\n"
            "- Heat Wave\n"
            "- Solar Beam"
        )
        parsed = parse_showdown_pokemon(paste)
        bs = BaseStats(
            hp=78, attack=104, defense=78,
            special_attack=159, special_defense=115, speed=100,
        )
        build = parsed_to_pokemon_build(parsed, bs, ["fire", "flying"])

        assert build.format_system == "champions"
        assert build.sps is not None
        assert build.sps.total == 66
        assert build.evs == EVSpread()

        out = pokemon_build_to_showdown(build)
        assert out.splitlines()[0].startswith("Charizard-Mega-Y")
        assert "SPs: 4 HP / 32 SpA / 30 Spe" in out
        assert "EVs:" not in out

        reparsed = parse_showdown_pokemon(out)
        assert reparsed.sps == {
            "hp": 4, "atk": 0, "def": 0, "spa": 32, "spd": 0, "spe": 30,
        }

    def test_mainline_paste_builds_mainline(self):
        parsed = parse_showdown_pokemon(MAINLINE_PASTE)
        bs = BaseStats(
            hp=88, attack=120, defense=75,
            special_attack=100, special_defense=75, speed=142,
        )
        build = parsed_to_pokemon_build(parsed, bs, ["dragon", "ghost"])
        assert build.format_system == "mainline"
        assert build.sps is None
        assert build.evs.speed == 252
        assert build.evs.special_attack == 252

    def test_extra_kwargs_override(self):
        parsed = parse_showdown_pokemon(CHAMPIONS_PASTE)
        bs = BaseStats(
            hp=108, attack=130, defense=95,
            special_attack=80, special_defense=85, speed=102,
        )
        build = parsed_to_pokemon_build(
            parsed, bs, ["dragon", "ground"],
            extra_kwargs={"name": "garchomp"},
        )
        assert build.name == "garchomp"
        assert build.format_system == "champions"
