"""Tests for VGC format legality checking."""

import pytest
from vgc_mcp.rules.regulation_loader import get_regulation_config, reset_regulation_config
from vgc_mcp.rules.vgc_rules import (
    get_regulation,
    list_regulations,
    VGCRegulation,
)
from vgc_mcp.rules.restricted import (
    is_restricted,
    is_banned,
    get_restricted_status,
    count_restricted,
    find_banned,
    find_restricted,
)
from vgc_mcp.rules.item_clause import (
    check_item_clause,
    get_duplicate_items,
    suggest_alternative_items,
    normalize_item_name,
)


@pytest.fixture(autouse=True)
def reset_config():
    """Reset regulation config before each test."""
    reset_regulation_config()
    yield
    reset_regulation_config()


class TestVGCRegulations:
    """Test VGC regulation definitions."""

    def test_reg_f_exists(self):
        """Regulation F should be defined."""
        reg = get_regulation("reg_f")
        assert reg is not None
        assert reg.name == "Regulation F"
        assert reg.restricted_limit == 2

    def test_reg_g_exists(self):
        """Regulation G should be defined."""
        reg = get_regulation("reg_g")
        assert reg is not None
        assert reg.restricted_limit == 1

    def test_reg_h_exists(self):
        """Regulation H should be defined."""
        reg = get_regulation("reg_h")
        assert reg is not None
        assert reg.restricted_limit == 0

    def test_all_regulations_have_required_fields(self):
        """All regulations should have required fields."""
        config = get_regulation_config()
        for code in config.list_regulation_codes():
            reg = get_regulation(code)
            assert isinstance(reg, VGCRegulation)
            assert reg.item_clause is True
            assert reg.species_clause is True
            assert reg.level == 50
            assert reg.pokemon_limit == 6
            assert reg.bring_limit == 4

    def test_get_regulation_flexible_input(self):
        """get_regulation should handle various input formats."""
        # Various ways to specify Regulation F
        assert get_regulation("reg_f") is not None
        assert get_regulation("f") is not None
        assert get_regulation("REG_F") is not None
        assert get_regulation("reg-f") is not None

    def test_get_regulation_invalid(self):
        """Invalid regulation should return None."""
        assert get_regulation("reg_z") is None
        assert get_regulation("invalid") is None

    def test_list_regulations(self):
        """Should list all available regulations."""
        regulations = list_regulations()
        assert len(regulations) >= 3  # At least F, G, H
        codes = [r["code"] for r in regulations]
        assert "reg_f" in codes
        assert "reg_g" in codes
        assert "reg_h" in codes


class TestRestrictedPokemon:
    """Test restricted Pokemon checking."""

    def test_koraidon_is_restricted(self):
        """Koraidon should be restricted."""
        assert is_restricted("koraidon")
        status = get_restricted_status("koraidon")
        assert status == "restricted"

    def test_miraidon_is_restricted(self):
        """Miraidon should be restricted."""
        assert is_restricted("miraidon")

    def test_kyogre_is_restricted(self):
        """Kyogre should be restricted."""
        assert is_restricted("kyogre")

    def test_calyrex_shadow_is_restricted(self):
        """Calyrex-Shadow should be restricted."""
        assert is_restricted("calyrex-shadow-rider")

    def test_pikachu_is_not_restricted(self):
        """Pikachu should not be restricted."""
        assert not is_restricted("pikachu")
        status = get_restricted_status("pikachu")
        assert status == "allowed"

    def test_count_restricted(self):
        """Should count restricted Pokemon correctly."""
        pokemon = ["koraidon", "miraidon", "incineroar"]
        result = count_restricted(pokemon)
        assert result == 2

    def test_count_restricted_none(self):
        """Should return 0 for no restricted."""
        pokemon = ["incineroar", "flutter-mane", "rillaboom"]
        result = count_restricted(pokemon)
        assert result == 0

    def test_find_restricted(self):
        """Should find restricted Pokemon in a list."""
        pokemon = ["koraidon", "incineroar", "miraidon"]
        restricted = find_restricted(pokemon)
        assert "koraidon" in restricted
        assert "miraidon" in restricted
        assert "incineroar" not in restricted


class TestBannedPokemon:
    """Test banned Pokemon checking."""

    def test_mew_is_banned(self):
        """Mew should be banned."""
        assert is_banned("mew")
        status = get_restricted_status("mew")
        assert status == "banned"

    def test_arceus_is_banned(self):
        """Arceus should be banned."""
        assert is_banned("arceus")

    def test_pecharunt_is_banned(self):
        """Pecharunt should be banned."""
        assert is_banned("pecharunt")

    def test_koraidon_is_not_banned(self):
        """Koraidon is restricted, not banned."""
        assert not is_banned("koraidon")

    def test_find_banned(self):
        """Should find banned Pokemon in list."""
        pokemon = ["mew", "incineroar", "arceus"]
        banned = find_banned(pokemon)
        assert "mew" in banned
        assert "arceus" in banned
        assert "incineroar" not in banned

    def test_find_banned_none(self):
        """Should return empty list if no banned."""
        pokemon = ["incineroar", "flutter-mane"]
        assert find_banned(pokemon) == []


class TestItemClause:
    """Test item clause validation."""

    def test_no_duplicates_valid(self):
        """Team with unique items should be valid."""
        items = ["choice-scarf", "life-orb", "focus-sash"]
        result = check_item_clause(items)
        assert result["valid"] is True
        assert len(result["duplicates"]) == 0

    def test_duplicates_invalid(self):
        """Team with duplicate items should be invalid."""
        items = ["choice-scarf", "choice-scarf", "life-orb"]
        result = check_item_clause(items)
        assert result["valid"] is False
        assert "choice-scarf" in result["duplicates"]

    def test_none_items_ignored(self):
        """None items should be ignored."""
        items = [None, "life-orb", None, "focus-sash"]
        result = check_item_clause(items)
        assert result["valid"] is True

    def test_normalize_item_name(self):
        """Item names should be normalized."""
        assert normalize_item_name("Choice Scarf") == "choice-scarf"
        assert normalize_item_name("life orb") == "life-orb"
        assert normalize_item_name("FOCUS SASH") == "focus-sash"

    def test_get_duplicate_items(self):
        """Should return list of duplicate items."""
        items = ["life-orb", "life-orb", "focus-sash", "focus-sash"]
        duplicates = get_duplicate_items(items)
        assert "life-orb" in duplicates
        assert "focus-sash" in duplicates

    def test_suggest_alternatives(self):
        """Should suggest alternative items."""
        alternatives = suggest_alternative_items("choice-scarf")
        assert len(alternatives) > 0
        assert "choice-scarf" not in alternatives

    def test_suggest_alternatives_by_role(self):
        """Should prioritize by role."""
        offensive = suggest_alternative_items("life-orb", "attacker")
        defensive = suggest_alternative_items("life-orb", "support")
        # Offensive suggestions should differ from defensive
        assert offensive != defensive


class TestRestrictedPokemonList:
    """Test that restricted Pokemon list is comprehensive."""

    def test_has_box_legends(self):
        """Should include all box legends."""
        config = get_regulation_config()
        restricted = config.get_restricted_pokemon("reg_f")
        box_legends = ["koraidon", "miraidon", "kyogre", "groudon", "rayquaza"]
        for legend in box_legends:
            assert legend in restricted, f"{legend} missing from restricted"

    def test_has_calyrex_forms(self):
        """Should include Calyrex forms."""
        config = get_regulation_config()
        restricted = config.get_restricted_pokemon("reg_f")
        assert "calyrex" in restricted or "calyrex-shadow-rider" in restricted
        assert "calyrex-ice-rider" in restricted or "calyrex" in restricted


class TestBannedPokemonList:
    """Test that banned Pokemon list is comprehensive."""

    def test_has_mythicals(self):
        """Should include mythical Pokemon."""
        config = get_regulation_config()
        banned = config.get_banned_pokemon("reg_f")
        mythicals = ["mew", "celebi", "jirachi", "deoxys", "darkrai"]
        for mythical in mythicals:
            assert mythical in banned, f"{mythical} missing from banned"


class TestRegulationConfig:
    """Test the regulation configuration system."""

    def test_current_regulation(self):
        """Should return the current regulation."""
        config = get_regulation_config()
        current = config.current_regulation
        assert current is not None
        assert current.startswith("reg_")

    def test_session_override(self):
        """Should allow session override of regulation."""
        config = get_regulation_config()
        original = config.current_regulation

        # Set to a different regulation
        if original == "reg_f":
            config.set_session_regulation("reg_g")
            assert config.current_regulation == "reg_g"
        else:
            config.set_session_regulation("reg_f")
            assert config.current_regulation == "reg_f"

        # Clear override
        config.clear_session_override()
        assert config.current_regulation == original

    def test_get_smogon_formats(self):
        """Should return Smogon format strings."""
        config = get_regulation_config()
        formats = config.get_smogon_formats("reg_f")
        assert len(formats) > 0
        assert any("vgc" in f.lower() for f in formats)

    def test_get_all_smogon_formats(self):
        """Should return all Smogon formats from all regulations."""
        config = get_regulation_config()
        all_formats = config.get_all_smogon_formats()
        assert len(all_formats) >= 2  # Should have multiple formats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
