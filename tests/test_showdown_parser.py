"""Tests for Showdown paste parsing."""

import pytest
from vgc_mcp.formats.showdown import (
    parse_showdown_pokemon,
    parse_showdown_team,
    export_pokemon_to_showdown,
    export_team_to_showdown,
    parsed_to_ev_spread,
    parsed_to_iv_spread,
    parsed_to_nature,
    ShowdownParseError,
)
from vgc_mcp.models.pokemon import Nature


class TestShowdownParser:
    """Test Showdown paste parsing."""

    def test_parse_basic_pokemon(self):
        """Parse a basic Pokemon paste."""
        paste = """Pikachu @ Light Ball
Ability: Static
Level: 50
EVs: 252 SpA / 252 Spe / 4 HP
Timid Nature
- Thunderbolt
- Volt Tackle
- Fake Out
- Protect"""

        parsed = parse_showdown_pokemon(paste)

        assert parsed.species == "Pikachu"
        assert parsed.item == "Light Ball"
        assert parsed.ability == "Static"
        assert parsed.level == 50
        assert parsed.nature == "Timid"
        assert "Thunderbolt" in parsed.moves
        assert parsed.evs.get("spa") == 252
        assert parsed.evs.get("spe") == 252

    def test_parse_pokemon_with_nickname(self):
        """Parse a Pokemon with a nickname."""
        paste = """Sparky (Pikachu) @ Light Ball
Ability: Static
EVs: 252 SpA / 252 Spe
Timid Nature
- Thunderbolt"""

        parsed = parse_showdown_pokemon(paste)

        assert parsed.nickname == "Sparky"
        assert parsed.species == "Pikachu"

    def test_parse_form_pokemon(self):
        """Parse Pokemon with form names."""
        paste = """Urshifu-Rapid-Strike @ Choice Scarf
Ability: Unseen Fist
Level: 50
Tera Type: Water
EVs: 252 Atk / 252 Spe / 4 HP
Jolly Nature
- Surging Strikes
- Close Combat
- U-turn
- Aqua Jet"""

        parsed = parse_showdown_pokemon(paste)

        assert parsed.species == "Urshifu-Rapid-Strike"
        assert parsed.item == "Choice Scarf"
        assert parsed.tera_type == "Water"
        assert parsed.nature == "Jolly"
        assert "Surging Strikes" in parsed.moves

    def test_parse_pokemon_with_gender(self):
        """Parse a Pokemon with gender specified."""
        paste = """Indeedee (F) @ Psychic Seed
Ability: Psychic Surge
EVs: 252 HP / 252 Def / 4 SpD
Bold Nature
- Follow Me
- Psychic
- Helping Hand
- Protect"""

        parsed = parse_showdown_pokemon(paste)

        assert parsed.species == "Indeedee"
        assert parsed.gender == "F"

    def test_parse_pokemon_with_ivs(self):
        """Parse a Pokemon with custom IVs."""
        paste = """Torkoal @ Heat Rock
Ability: Drought
Level: 50
IVs: 0 Atk / 0 Spe
EVs: 252 HP / 252 SpA / 4 SpD
Quiet Nature
- Eruption
- Heat Wave
- Solar Beam
- Protect"""

        parsed = parse_showdown_pokemon(paste)

        assert parsed.ivs.get("atk") == 0
        assert parsed.ivs.get("spe") == 0
        assert parsed.ivs.get("hp") == 31  # Default

    def test_parse_shiny_pokemon(self):
        """Parse a shiny Pokemon."""
        paste = """Charizard @ Choice Specs
Ability: Solar Power
Shiny: Yes
EVs: 252 SpA / 252 Spe
Timid Nature
- Heat Wave"""

        parsed = parse_showdown_pokemon(paste)

        assert parsed.shiny == True
        assert parsed.species == "Charizard"

    def test_parse_team(self):
        """Parse a multi-Pokemon team paste."""
        paste = """Pikachu @ Light Ball
Ability: Static
EVs: 252 SpA / 252 Spe
Timid Nature
- Thunderbolt

Charizard @ Choice Specs
Ability: Solar Power
EVs: 252 SpA / 252 Spe
Timid Nature
- Heat Wave

Venusaur @ Life Orb
Ability: Chlorophyll
EVs: 252 SpA / 252 Spe
Modest Nature
- Giga Drain"""

        team = parse_showdown_team(paste)

        assert len(team) == 3
        assert team[0].species == "Pikachu"
        assert team[1].species == "Charizard"
        assert team[2].species == "Venusaur"

    def test_empty_paste_raises_error(self):
        """Empty paste should raise error."""
        with pytest.raises(ShowdownParseError):
            parse_showdown_pokemon("")

    def test_invalid_paste_parses_leniently(self):
        """Parser is lenient - treats any text as a species name."""
        # The parser is lenient by design, similar to Showdown
        # "This is not a valid paste" becomes species="This is not a valid paste"
        parsed = parse_showdown_pokemon("This is not a valid paste")
        assert parsed.species == "This is not a valid paste"  # Entire line treated as species


class TestShowdownExport:
    """Test Showdown paste export."""

    def test_export_basic_pokemon(self):
        """Export a basic Pokemon."""
        paste = export_pokemon_to_showdown(
            species="Pikachu",
            item="Light Ball",
            ability="Static",
            level=50,
            evs={"hp": 4, "spa": 252, "spe": 252},
            nature="Timid",
            moves=["Thunderbolt", "Volt Switch", "Fake Out", "Protect"]
        )

        assert "Pikachu @ Light Ball" in paste
        assert "Ability: Static" in paste
        assert "Timid Nature" in paste
        assert "- Thunderbolt" in paste

    def test_export_with_tera_type(self):
        """Export Pokemon with Tera type."""
        paste = export_pokemon_to_showdown(
            species="Urshifu-Rapid-Strike",
            ability="Unseen Fist",
            level=50,
            tera_type="Water",
            evs={"atk": 252, "spe": 252},
            nature="Jolly",
            moves=["Surging Strikes"]
        )

        assert "Tera Type: Water" in paste

    def test_export_with_custom_ivs(self):
        """Export Pokemon with custom IVs."""
        paste = export_pokemon_to_showdown(
            species="Torkoal",
            ability="Drought",
            level=50,
            evs={"hp": 252, "spa": 252},
            ivs={"atk": 0, "spe": 0},
            nature="Quiet",
            moves=["Eruption"]
        )

        assert "IVs: 0 Atk / 0 Spe" in paste

    def test_export_team(self):
        """Export multiple Pokemon."""
        team_data = [
            {
                "species": "Pikachu",
                "item": "Light Ball",
                "ability": "Static",
                "level": 50,
                "evs": {"spa": 252, "spe": 252},
                "nature": "Timid",
                "moves": ["Thunderbolt"]
            },
            {
                "species": "Charizard",
                "ability": "Solar Power",
                "level": 50,
                "evs": {"spa": 252, "spe": 252},
                "nature": "Timid",
                "moves": ["Heat Wave"]
            }
        ]

        paste = export_team_to_showdown(team_data)

        assert "Pikachu @ Light Ball" in paste
        assert "Charizard" in paste
        # Should be separated by blank lines
        assert "\n\n" in paste


class TestParsedConversion:
    """Test converting parsed data to model types."""

    def test_parsed_to_ev_spread(self):
        """Convert parsed EVs to EVSpread."""
        paste = """Pikachu @ Light Ball
Ability: Static
EVs: 252 SpA / 252 Spe / 4 HP
Timid Nature
- Thunderbolt"""

        parsed = parse_showdown_pokemon(paste)
        evs = parsed_to_ev_spread(parsed)

        assert evs.hp == 4
        assert evs.special_attack == 252
        assert evs.speed == 252
        assert evs.attack == 0

    def test_parsed_to_iv_spread(self):
        """Convert parsed IVs to IVSpread."""
        paste = """Torkoal @ Heat Rock
Ability: Drought
IVs: 0 Atk / 0 Spe
EVs: 252 HP
Quiet Nature
- Eruption"""

        parsed = parse_showdown_pokemon(paste)
        ivs = parsed_to_iv_spread(parsed)

        assert ivs.attack == 0
        assert ivs.speed == 0
        assert ivs.hp == 31  # Default

    def test_parsed_to_nature(self):
        """Convert parsed nature to Nature enum."""
        paste = """Pikachu @ Light Ball
Ability: Static
Timid Nature
- Thunderbolt"""

        parsed = parse_showdown_pokemon(paste)
        nature = parsed_to_nature(parsed)

        assert nature == Nature.TIMID


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
