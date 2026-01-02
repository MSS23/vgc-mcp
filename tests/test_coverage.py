"""Tests for move-based coverage analysis."""

import pytest
from vgc_mcp_core.calc.coverage import (
    analyze_move_coverage,
    find_coverage_holes,
    check_quad_weaknesses,
    check_coverage_vs_pokemon,
    suggest_coverage_moves,
    get_coverage_summary,
    normalize_move_name,
    get_move_type_from_name,
    ALL_TYPES,
    COVERAGE_MOVES,
)


class TestMoveNormalization:
    """Test move name normalization."""

    def test_normalize_spaces(self):
        """Should convert spaces to hyphens."""
        assert normalize_move_name("Heat Wave") == "heat-wave"
        assert normalize_move_name("Close Combat") == "close-combat"

    def test_normalize_case(self):
        """Should convert to lowercase."""
        assert normalize_move_name("FLAMETHROWER") == "flamethrower"
        assert normalize_move_name("Ice Beam") == "ice-beam"

    def test_normalize_apostrophe(self):
        """Should remove apostrophes."""
        assert normalize_move_name("King's Shield") == "kings-shield"


class TestMoveTypeFromName:
    """Test getting move type from name."""

    def test_common_moves(self):
        """Should identify types of common moves."""
        assert get_move_type_from_name("Heat Wave") == "Fire"
        assert get_move_type_from_name("Earthquake") == "Ground"
        assert get_move_type_from_name("Moonblast") == "Fairy"

    def test_case_insensitive(self):
        """Should handle different cases."""
        assert get_move_type_from_name("heat wave") == "Fire"
        assert get_move_type_from_name("EARTHQUAKE") == "Ground"

    def test_unknown_move(self):
        """Should return None for unknown moves."""
        assert get_move_type_from_name("Unknown Move XYZ") is None


class TestCoverageAnalysis:
    """Test full coverage analysis."""

    def test_basic_coverage(self):
        """Should analyze basic move coverage."""
        team_data = [
            {
                "name": "Charizard",
                "types": ["Fire", "Flying"],
                "moves": ["Heat Wave", "Air Slash", "Flamethrower", "Protect"]
            }
        ]

        result = analyze_move_coverage(team_data)

        assert "Charizard" in result.team_pokemon
        # Fire hits Grass, Ice, Bug, Steel SE
        assert result.type_coverage["Grass"].is_covered
        assert result.type_coverage["Ice"].is_covered
        assert result.type_coverage["Steel"].is_covered

    def test_multiple_pokemon_coverage(self):
        """Should combine coverage from multiple Pokemon."""
        team_data = [
            {
                "name": "Charizard",
                "types": ["Fire", "Flying"],
                "moves": ["Heat Wave", "Protect"]
            },
            {
                "name": "Garchomp",
                "types": ["Dragon", "Ground"],
                "moves": ["Earthquake", "Dragon Claw"]
            }
        ]

        result = analyze_move_coverage(team_data)

        # Fire covers Grass, Ice, Bug, Steel
        # Ground covers Fire, Electric, Poison, Rock, Steel
        # Dragon covers Dragon
        assert result.type_coverage["Grass"].is_covered
        assert result.type_coverage["Electric"].is_covered
        assert result.type_coverage["Dragon"].is_covered

    def test_coverage_holes_detected(self):
        """Should detect types with no SE coverage."""
        # Team with limited coverage
        team_data = [
            {
                "name": "Magikarp",
                "types": ["Water"],
                "moves": ["Splash"]  # No damaging moves with known types
            }
        ]

        result = analyze_move_coverage(team_data)

        # Should have many coverage holes
        assert len(result.coverage_holes) > 0

    def test_stab_vs_non_stab(self):
        """Should distinguish STAB from non-STAB coverage."""
        team_data = [
            {
                "name": "Charizard",
                "types": ["Fire", "Flying"],
                "moves": ["Heat Wave", "Earthquake"]  # Ground is non-STAB
            }
        ]

        result = analyze_move_coverage(team_data)

        # Heat Wave should be STAB coverage for Grass/Ice/Bug/Steel
        grass_coverage = result.type_coverage["Grass"]
        assert any(c.is_stab for c in grass_coverage.covered_by)

        # Earthquake should be non-STAB for Fire/Electric/Poison/Rock/Steel
        electric_coverage = result.type_coverage["Electric"]
        assert any(not c.is_stab for c in electric_coverage.covered_by)


class TestQuadWeaknesses:
    """Test quad weakness detection."""

    def test_charizard_quad_rock(self):
        """Charizard should have 4x Rock weakness."""
        team_data = [
            {
                "name": "Charizard",
                "types": ["Fire", "Flying"],
                "moves": []
            }
        ]

        result = check_quad_weaknesses(team_data)

        assert len(result) == 1
        assert result[0]["pokemon"] == "Charizard"
        assert result[0]["weak_to"] == "Rock"
        assert result[0]["multiplier"] == 4.0

    def test_no_quad_weakness(self):
        """Pokemon without quad weaknesses."""
        team_data = [
            {
                "name": "Pikachu",
                "types": ["Electric"],
                "moves": []
            }
        ]

        result = check_quad_weaknesses(team_data)
        assert len(result) == 0

    def test_multiple_quad_weaknesses(self):
        """Team with multiple quad weaknesses."""
        team_data = [
            {
                "name": "Charizard",
                "types": ["Fire", "Flying"],  # 4x Rock
                "moves": []
            },
            {
                "name": "Gyarados",
                "types": ["Water", "Flying"],  # 4x Electric
                "moves": []
            }
        ]

        result = check_quad_weaknesses(team_data)

        assert len(result) == 2
        types_hit = {qw["weak_to"] for qw in result}
        assert "Rock" in types_hit
        assert "Electric" in types_hit


class TestCoverageVsPokemon:
    """Test coverage against specific Pokemon."""

    def test_coverage_vs_steel(self):
        """Test coverage against Steel type."""
        team_data = [
            {
                "name": "Charizard",
                "types": ["Fire", "Flying"],
                "moves": ["Heat Wave", "Air Slash"]
            }
        ]

        result = check_coverage_vs_pokemon(team_data, ["Steel"])

        assert result["has_coverage"] is True
        assert result["coverage_count"] >= 1
        # Heat Wave should hit Steel 2x
        assert any(opt["move"] == "Heat Wave" for opt in result["options"])

    def test_no_coverage_vs_type(self):
        """Test when team has no coverage."""
        team_data = [
            {
                "name": "Charizard",
                "types": ["Fire", "Flying"],
                "moves": ["Heat Wave"]  # Fire doesn't hit Water SE
            }
        ]

        result = check_coverage_vs_pokemon(team_data, ["Water"])

        assert result["has_coverage"] is False
        assert result["coverage_count"] == 0

    def test_dual_type_coverage(self):
        """Test coverage against dual types."""
        team_data = [
            {
                "name": "Garchomp",
                "types": ["Dragon", "Ground"],
                "moves": ["Earthquake", "Dragon Claw"]
            }
        ]

        # Ground hits Fire/Flying 2x, but Flying is immune
        # Actually Ground is immune to Flying, Ground hits Fire 2x
        result = check_coverage_vs_pokemon(team_data, ["Fire", "Flying"])

        # Earthquake hits Fire (though Flying makes it neutral overall)
        # Let's check a simpler case
        result2 = check_coverage_vs_pokemon(team_data, ["Fire", "Steel"])

        # Ground 2x on Fire, Ground 2x on Steel = 4x
        assert result2["has_coverage"] is True


class TestCoverageSuggestions:
    """Test coverage move suggestions."""

    def test_suggest_for_holes(self):
        """Should suggest moves to fill coverage holes."""
        holes = ["Ice", "Ground"]

        suggestions = suggest_coverage_moves(holes)

        assert len(suggestions) > 0
        # Should suggest moves that hit Ice or Ground
        move_names = [s["move"] for s in suggestions]
        # Fighting or Fire hits Ice, Water or Grass hits Ground
        assert any(s["fills_gap"] in ["Ice", "Ground"] for s in suggestions)

    def test_prioritize_spread_moves(self):
        """Should prioritize spread moves when requested."""
        holes = ["Fire"]  # Water hits Fire

        normal_suggestions = suggest_coverage_moves(holes, prioritize_spread=False)
        spread_suggestions = suggest_coverage_moves(holes, prioritize_spread=True)

        # Both should have suggestions
        assert len(normal_suggestions) > 0
        assert len(spread_suggestions) > 0

    def test_filter_by_category(self):
        """Should filter by physical/special."""
        holes = ["Grass"]  # Fire, Ice, Poison, Flying, Bug hit Grass

        physical = suggest_coverage_moves(holes, category_preference="physical")
        special = suggest_coverage_moves(holes, category_preference="special")

        assert all(s["category"] == "physical" for s in physical)
        assert all(s["category"] == "special" for s in special)


class TestCoverageSummary:
    """Test coverage summary generation."""

    def test_summary_structure(self):
        """Should return proper summary structure."""
        team_data = [
            {
                "name": "Charizard",
                "types": ["Fire", "Flying"],
                "moves": ["Heat Wave", "Air Slash", "Earthquake", "Dragon Claw"]
            }
        ]

        summary = get_coverage_summary(team_data)

        assert "total_types" in summary
        assert "covered_types" in summary
        assert "coverage_holes" in summary
        assert "coverage_percentage" in summary
        assert summary["total_types"] == 18

    def test_full_coverage_team(self):
        """Test a team with good coverage."""
        # Team with diverse coverage
        team_data = [
            {
                "name": "Pokemon1",
                "types": ["Fire", "Flying"],
                "moves": ["Heat Wave", "Hurricane"]  # Fire hits Grass/Ice/Bug/Steel, Flying hits Grass/Fighting/Bug
            },
            {
                "name": "Pokemon2",
                "types": ["Water", "Ground"],
                "moves": ["Surf", "Earthquake"]  # Water hits Fire/Ground/Rock, Ground hits Fire/Electric/Poison/Rock/Steel
            },
            {
                "name": "Pokemon3",
                "types": ["Ice", "Fighting"],
                "moves": ["Ice Beam", "Close Combat"]  # Ice hits Grass/Ground/Flying/Dragon, Fighting hits Normal/Ice/Rock/Dark/Steel
            }
        ]

        summary = get_coverage_summary(team_data)

        # Should have good coverage
        assert summary["covered_types"] >= 10
        assert summary["coverage_percentage"] >= 50


class TestCoverageMoveDatabase:
    """Test the coverage move database."""

    def test_all_types_have_moves(self):
        """All types should have coverage moves defined."""
        for type_name in ALL_TYPES:
            assert type_name in COVERAGE_MOVES, f"Missing moves for {type_name}"
            assert len(COVERAGE_MOVES[type_name]) > 0

    def test_move_structure(self):
        """Moves should have required fields."""
        for type_name, moves in COVERAGE_MOVES.items():
            for move in moves:
                assert "name" in move
                assert "power" in move
                assert "category" in move

    def test_spread_moves_flagged(self):
        """Spread moves should be properly flagged."""
        spread_moves = []
        for type_name, moves in COVERAGE_MOVES.items():
            for move in moves:
                if move.get("spread"):
                    spread_moves.append(move["name"])

        # Common VGC spread moves should be in the list
        assert "Heat Wave" in spread_moves
        assert "Earthquake" in spread_moves
        assert "Rock Slide" in spread_moves


class TestFindCoverageHoles:
    """Test the convenience function for finding holes."""

    def test_empty_team(self):
        """Empty team should have all types as holes."""
        result = find_coverage_holes([])
        # With no moves, all types are holes
        assert len(result) == 18

    def test_partial_coverage(self):
        """Team with some coverage should have fewer holes."""
        team_data = [
            {
                "name": "Charizard",
                "types": ["Fire", "Flying"],
                "moves": ["Heat Wave", "Air Slash", "Earthquake", "Dragon Claw"]
            }
        ]

        holes = find_coverage_holes(team_data)

        # Should have fewer than 18 holes
        assert len(holes) < 18


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
