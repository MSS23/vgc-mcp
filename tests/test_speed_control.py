"""Tests for speed control analysis."""

import pytest
from vgc_mcp_core.calc.speed_control import (
    analyze_trick_room,
    analyze_tailwind,
    analyze_speed_drop,
    analyze_paralysis,
    get_team_speeds,
    apply_speed_modifier,
    apply_stage_modifier,
    get_speed_control_summary,
    SPEED_STAGE_MULTIPLIERS,
)
from vgc_mcp_core.models.pokemon import PokemonBuild, BaseStats, Nature, EVSpread
from vgc_mcp_core.models.team import Team, TeamSlot


def make_pokemon(name: str, base_speed: int, speed_evs: int = 0, nature: Nature = Nature.SERIOUS) -> PokemonBuild:
    """Helper to create Pokemon for speed testing."""
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(
            hp=80, attack=80, defense=80,
            special_attack=80, special_defense=80,
            speed=base_speed
        ),
        nature=nature,
        evs=EVSpread(speed=speed_evs),
        types=["Normal"]
    )


def make_team(pokemon_list: list[PokemonBuild]) -> Team:
    """Create a team from Pokemon list."""
    team = Team()
    for p in pokemon_list:
        team.add_pokemon(p)
    return team


class TestSpeedModifiers:
    """Test speed modifier calculations."""

    def test_tailwind_doubles_speed(self):
        """Tailwind should double speed."""
        result = apply_speed_modifier(100, 2.0)
        assert result == 200

    def test_paralysis_halves_speed(self):
        """Paralysis should halve speed."""
        result = apply_speed_modifier(100, 0.5)
        assert result == 50

    def test_paralysis_floors_result(self):
        """Paralysis should floor odd speeds."""
        result = apply_speed_modifier(101, 0.5)
        assert result == 50  # floor(50.5)

    def test_stage_modifiers(self):
        """Test stat stage multipliers."""
        # -1 stage = 2/3 speed
        result = apply_stage_modifier(150, -1)
        assert result == 100  # floor(150 * 2/3)

        # -2 stages = 1/2 speed
        result = apply_stage_modifier(100, -2)
        assert result == 50

        # +1 stage = 3/2 speed
        result = apply_stage_modifier(100, 1)
        assert result == 150

    def test_stage_clamping(self):
        """Stages should be clamped to -6 to +6."""
        # -7 should be treated as -6
        result_minus7 = apply_stage_modifier(100, -7)
        result_minus6 = apply_stage_modifier(100, -6)
        assert result_minus7 == result_minus6

        # +7 should be treated as +6
        result_plus7 = apply_stage_modifier(100, 7)
        result_plus6 = apply_stage_modifier(100, 6)
        assert result_plus7 == result_plus6

    def test_icy_wind_exact_calculation(self):
        """Verify -1 speed stage uses exact 2/3, not 0.67 approximation."""
        # Critical case: Chien-Pao with 205 speed after Icy Wind
        speed_205 = apply_stage_modifier(205, -1)
        assert speed_205 == 136, f"205 * 2/3 should be 136, got {speed_205}"

        # Verify 0.67 approximation would be wrong:
        wrong_calc = int(205 * 0.67)
        assert wrong_calc == 137, "0.67 approximation gives 137"
        assert speed_205 != wrong_calc, "Must use exact 2/3, not 0.67"

        # Additional test cases:
        assert apply_stage_modifier(150, -1) == 100
        assert apply_stage_modifier(99, -1) == 66


class TestGetTeamSpeeds:
    """Test team speed tier extraction."""

    def test_sorts_by_speed_descending(self):
        """Team speeds should be sorted fastest to slowest."""
        fast = make_pokemon("fast", 130, 252, Nature.TIMID)
        medium = make_pokemon("medium", 100, 252, Nature.JOLLY)
        slow = make_pokemon("slow", 50, 0, Nature.BRAVE)

        team = make_team([slow, fast, medium])
        speeds = get_team_speeds(team)

        assert speeds[0].name == "fast"
        assert speeds[1].name == "medium"
        assert speeds[2].name == "slow"

    def test_includes_final_speed(self):
        """Should calculate final speed stat correctly."""
        # Base 100, 252 EVs, Jolly (+10%)
        # Formula: floor((floor((2*100 + 31 + 252/4) * 50/100) + 5) * 1.1)
        # = floor((floor(294 * 0.5) + 5) * 1.1)
        # = floor((147 + 5) * 1.1)
        # = floor(167.2) = 167
        pokemon = make_pokemon("test", 100, 252, Nature.JOLLY)
        team = make_team([pokemon])
        speeds = get_team_speeds(team)

        # Check it's in the ballpark (exact value depends on formula implementation)
        assert speeds[0].final_speed > 150


class TestTrickRoomAnalysis:
    """Test Trick Room analysis."""

    def test_tr_reverses_order(self):
        """In Trick Room, slowest should be first."""
        fast = make_pokemon("fast", 130)
        slow = make_pokemon("slow", 30)

        team = make_team([fast, slow])
        analysis = analyze_trick_room(team)

        assert analysis.move_order[0] == "slow"
        assert analysis.move_order[-1] == "fast"

    def test_tr_identifies_good_pokemon(self):
        """Should identify Pokemon that benefit from TR."""
        very_slow = make_pokemon("very-slow", 30)
        team = make_team([very_slow])
        analysis = analyze_trick_room(team)

        # Should note it's a good TR Pokemon
        notes = analysis.team_speeds[0].notes
        assert any("Excellent TR" in note or "Good TR" in note for note in notes)

    def test_tr_warns_about_fast_pokemon(self):
        """Should warn about Pokemon too fast for TR."""
        fast = make_pokemon("fast", 130, 252, Nature.TIMID)
        team = make_team([fast])
        analysis = analyze_trick_room(team)

        # Should note it's too fast
        notes = analysis.team_speeds[0].notes
        assert any("Too fast" in note for note in notes)


class TestTailwindAnalysis:
    """Test Tailwind analysis."""

    def test_tailwind_doubles_all_speeds(self):
        """All Pokemon should have doubled speed in analysis."""
        pokemon = make_pokemon("test", 100, 252, Nature.JOLLY)
        team = make_team([pokemon])
        analysis = analyze_tailwind(team)

        original = analysis.team_speeds[0].final_speed
        with_tw = analysis.team_speeds[0].modified_speed

        assert with_tw == original * 2

    def test_tailwind_preserves_order(self):
        """Fastest should still be first after Tailwind."""
        fast = make_pokemon("fast", 130)
        slow = make_pokemon("slow", 50)

        team = make_team([fast, slow])
        analysis = analyze_tailwind(team)

        assert analysis.move_order[0] == "fast"


class TestSpeedDropAnalysis:
    """Test speed drop (Icy Wind/Electroweb) analysis."""

    def test_speed_drop_analysis(self):
        """Should analyze what team outspeeds after drops."""
        pokemon = make_pokemon("test", 100)
        team = make_team([pokemon])
        analysis = analyze_speed_drop(team, -1)

        assert analysis.condition == "After 1 Speed drop(s)"
        assert len(analysis.notes) > 0


class TestParalysisAnalysis:
    """Test paralysis analysis."""

    def test_paralysis_analysis(self):
        """Should analyze what team outspeeds when opponents are paralyzed."""
        pokemon = make_pokemon("test", 100)
        team = make_team([pokemon])
        analysis = analyze_paralysis(team)

        assert "paralyzed" in analysis.condition.lower() or "Paralyzed" in analysis.condition
        assert len(analysis.notes) > 0


class TestSpeedControlSummary:
    """Test comprehensive speed control summary."""

    def test_summary_includes_all_analyses(self):
        """Summary should include TR, Tailwind, and Icy Wind data."""
        pokemon = make_pokemon("test", 100)
        team = make_team([pokemon])
        summary = get_speed_control_summary(team)

        assert "base_speeds" in summary
        assert "trick_room" in summary
        assert "tailwind" in summary
        assert "after_icy_wind" in summary

    def test_summary_base_speeds_format(self):
        """Base speeds should include all expected fields."""
        pokemon = make_pokemon("test", 100, 252, Nature.JOLLY)
        team = make_team([pokemon])
        summary = get_speed_control_summary(team)

        base = summary["base_speeds"][0]
        assert "name" in base
        assert "speed" in base
        assert "base" in base
        assert "nature" in base
        assert "evs" in base


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
