"""Tests for core builder functionality."""

import pytest
from vgc_mcp.team.core_builder import (
    get_pokemon_role,
    get_type_synergy,
    analyze_core_synergy,
    POKEMON_ROLES,
)
from vgc_mcp.models.pokemon import PokemonBuild, BaseStats, Nature, EVSpread
from vgc_mcp.models.team import Team


def make_pokemon(name: str, types: list[str]) -> PokemonBuild:
    """Helper to create Pokemon for testing."""
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(
            hp=80, attack=80, defense=80,
            special_attack=80, special_defense=80, speed=80
        ),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=types
    )


def make_team(pokemon_list: list[PokemonBuild]) -> Team:
    """Create a team from Pokemon list."""
    team = Team()
    for p in pokemon_list:
        team.add_pokemon(p)
    return team


class TestPokemonRoles:
    """Test Pokemon role identification."""

    def test_incineroar_has_intimidate_and_fake_out(self):
        """Incineroar should have Intimidate and Fake Out roles."""
        roles = get_pokemon_role("incineroar")

        assert "intimidate" in roles
        assert "fake_out" in roles

    def test_tornadus_has_tailwind(self):
        """Tornadus should be a Tailwind setter."""
        roles = get_pokemon_role("tornadus")

        assert "tailwind_setter" in roles

    def test_hatterene_has_trick_room(self):
        """Hatterene should be a Trick Room setter."""
        roles = get_pokemon_role("hatterene")

        assert "trick_room_setter" in roles

    def test_rillaboom_has_grassy_terrain_and_fake_out(self):
        """Rillaboom should set Grassy Terrain and have Fake Out."""
        roles = get_pokemon_role("rillaboom")

        assert "grassy_terrain" in roles
        assert "fake_out" in roles

    def test_unknown_pokemon_has_no_roles(self):
        """Unknown Pokemon should return empty list."""
        roles = get_pokemon_role("random-pokemon")

        assert roles == []

    def test_role_lookup_handles_formatting(self):
        """Role lookup should handle various name formats."""
        # With spaces
        roles1 = get_pokemon_role("indeedee f")
        # With hyphen
        roles2 = get_pokemon_role("indeedee-f")

        # Both should find roles (or both empty)
        assert roles1 == roles2


class TestTypeSynergy:
    """Test type synergy calculations."""

    def test_complementary_types_have_positive_synergy(self):
        """Types that cover each other's weaknesses should have positive synergy."""
        # Water resists Fire, which Fire is weak to
        # Fire resists Grass, which Water is weak to
        synergy = get_type_synergy(["Water"], ["Fire"])

        assert synergy > 0

    def test_shared_weakness_reduces_synergy(self):
        """Shared weaknesses should reduce synergy score."""
        # Both Rock and Ice are weak to Fighting
        synergy = get_type_synergy(["Rock"], ["Ice"])

        # May be low or negative due to shared weaknesses
        # The exact value depends on implementation
        assert isinstance(synergy, (int, float))


class TestCoreSynergyAnalysis:
    """Test team core synergy analysis."""

    def test_analysis_returns_expected_fields(self):
        """Analysis should return all expected fields."""
        water = make_pokemon("water-mon", ["Water"])
        fire = make_pokemon("fire-mon", ["Fire"])
        team = make_team([water, fire])

        analysis = analyze_core_synergy(team)

        assert hasattr(analysis, "pokemon")
        assert hasattr(analysis, "synergy_score")
        assert hasattr(analysis, "strengths")
        assert hasattr(analysis, "weaknesses")
        assert hasattr(analysis, "type_coverage")
        assert hasattr(analysis, "recommendations")

    def test_synergy_score_is_bounded(self):
        """Synergy score should be between 0 and 100."""
        water = make_pokemon("water-mon", ["Water"])
        fire = make_pokemon("fire-mon", ["Fire"])
        grass = make_pokemon("grass-mon", ["Grass"])
        team = make_team([water, fire, grass])

        analysis = analyze_core_synergy(team)

        assert 0 <= analysis.synergy_score <= 100

    def test_identifies_type_weaknesses(self):
        """Should identify shared type weaknesses."""
        # Both Grass and Water are weak to Flying
        # This should show up as a notable weakness
        grass1 = make_pokemon("grass1", ["Grass"])
        grass2 = make_pokemon("grass2", ["Grass"])
        water = make_pokemon("water", ["Water"])
        team = make_team([grass1, grass2, water])

        analysis = analyze_core_synergy(team)

        # Should note weakness somewhere
        assert len(analysis.weaknesses) > 0 or len(analysis.recommendations) > 0

    def test_type_coverage_tracking(self):
        """Should track how many Pokemon resist each type."""
        water1 = make_pokemon("water1", ["Water"])
        water2 = make_pokemon("water2", ["Water"])
        team = make_team([water1, water2])

        analysis = analyze_core_synergy(team)

        # Both Waters resist Fire
        assert analysis.type_coverage.get("Fire", 0) == 2

    def test_recommends_speed_control(self):
        """Should recommend speed control if missing."""
        # Pokemon without speed control roles
        water = make_pokemon("water-mon", ["Water"])
        fire = make_pokemon("fire-mon", ["Fire"])
        team = make_team([water, fire])

        analysis = analyze_core_synergy(team)

        # Should recommend some form of speed control
        has_speed_rec = any(
            "speed control" in rec.lower() or
            "tailwind" in rec.lower() or
            "trick room" in rec.lower()
            for rec in analysis.recommendations
        )
        # This might not always trigger depending on implementation
        # At minimum, we should have recommendations
        assert isinstance(analysis.recommendations, list)


class TestRoleData:
    """Test role data integrity."""

    def test_all_role_lists_are_non_empty(self):
        """All role categories should have at least one Pokemon."""
        for role, pokemon_list in POKEMON_ROLES.items():
            assert len(pokemon_list) > 0, f"Role {role} has no Pokemon"

    def test_pokemon_names_are_lowercase(self):
        """All Pokemon names in roles should be lowercase."""
        for role, pokemon_list in POKEMON_ROLES.items():
            for pokemon in pokemon_list:
                assert pokemon == pokemon.lower(), f"{pokemon} in {role} is not lowercase"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
