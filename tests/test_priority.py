"""Tests for priority move and turn order analysis."""

import pytest
from vgc_mcp.calc.priority import (
    get_move_priority,
    determine_turn_order,
    get_priority_moves_by_bracket,
    categorize_priority_move,
    find_team_priority_moves,
    analyze_fake_out_matchup,
    get_priority_bracket_summary,
    check_prankster_immunity,
    normalize_move_name,
    PRIORITY_MOVES,
    FAKE_OUT_POKEMON,
    PRANKSTER_POKEMON,
)


class TestMovePriority:
    """Test move priority lookup."""

    def test_protect_priority(self):
        """Protect should have +4 priority."""
        assert get_move_priority("protect") == 4

    def test_fake_out_priority(self):
        """Fake Out should have +3 priority."""
        assert get_move_priority("fake-out") == 3
        assert get_move_priority("Fake Out") == 3

    def test_extreme_speed_priority(self):
        """Extreme Speed should have +2 priority."""
        assert get_move_priority("extreme-speed") == 2

    def test_aqua_jet_priority(self):
        """Aqua Jet should have +1 priority."""
        assert get_move_priority("aqua-jet") == 1

    def test_normal_move_priority(self):
        """Normal moves should have 0 priority."""
        assert get_move_priority("flamethrower") == 0
        assert get_move_priority("earthquake") == 0

    def test_trick_room_priority(self):
        """Trick Room should have -7 priority."""
        assert get_move_priority("trick-room") == -7

    def test_counter_priority(self):
        """Counter should have -6 priority."""
        assert get_move_priority("counter") == -6


class TestGrassyGlide:
    """Test Grassy Glide priority mechanics."""

    def test_grassy_glide_in_terrain(self):
        """Grassy Glide should have +1 in Grassy Terrain."""
        assert get_move_priority("grassy-glide", terrain="grassy") == 1

    def test_grassy_glide_no_terrain(self):
        """Grassy Glide should have 0 outside terrain."""
        assert get_move_priority("grassy-glide") == 0
        assert get_move_priority("grassy-glide", terrain="electric") == 0


class TestPrankster:
    """Test Prankster ability interactions."""

    def test_prankster_boosts_status(self):
        """Prankster should boost status move priority."""
        # Normal Thunder Wave is 0 priority
        base = get_move_priority("thunder-wave")
        boosted = get_move_priority("thunder-wave", ability="prankster", is_status=True)
        assert boosted == base + 1

    def test_prankster_immunity(self):
        """Dark types should be immune to Prankster moves."""
        assert check_prankster_immunity(["Dark"], True) is True
        assert check_prankster_immunity(["Dark", "Fire"], True) is True
        assert check_prankster_immunity(["Fire"], True) is False
        assert check_prankster_immunity(["Dark"], False) is False


class TestTurnOrder:
    """Test turn order determination."""

    def test_higher_priority_first(self):
        """Higher priority move should go first."""
        result = determine_turn_order(
            pokemon1_name="Incineroar",
            pokemon1_move="Fake Out",
            pokemon1_speed=80,
            pokemon2_name="Flutter Mane",
            pokemon2_move="Moonblast",
            pokemon2_speed=200
        )
        assert result.first_mover == "Incineroar"
        assert "priority" in result.reason.lower()

    def test_same_priority_faster_first(self):
        """Same priority, faster Pokemon goes first."""
        result = determine_turn_order(
            pokemon1_name="Fast",
            pokemon1_move="Tackle",
            pokemon1_speed=150,
            pokemon2_name="Slow",
            pokemon2_move="Tackle",
            pokemon2_speed=100
        )
        assert result.first_mover == "Fast"
        assert "faster" in result.reason.lower()

    def test_speed_tie(self):
        """Same speed should be 50/50."""
        result = determine_turn_order(
            pokemon1_name="Pokemon1",
            pokemon1_move="Tackle",
            pokemon1_speed=100,
            pokemon2_name="Pokemon2",
            pokemon2_move="Tackle",
            pokemon2_speed=100
        )
        assert result.speed_tie is True
        assert result.first_mover == "50/50"

    def test_trick_room_slower_first(self):
        """In Trick Room, slower Pokemon goes first."""
        result = determine_turn_order(
            pokemon1_name="Fast",
            pokemon1_move="Tackle",
            pokemon1_speed=150,
            pokemon2_name="Slow",
            pokemon2_move="Tackle",
            pokemon2_speed=50,
            trick_room=True
        )
        assert result.first_mover == "Slow"
        assert result.trick_room_active is True

    def test_trick_room_priority_still_first(self):
        """Priority moves still go first in Trick Room."""
        result = determine_turn_order(
            pokemon1_name="Fast",
            pokemon1_move="Protect",
            pokemon1_speed=150,
            pokemon2_name="Slow",
            pokemon2_move="Tackle",
            pokemon2_speed=50,
            trick_room=True
        )
        # Protect (+4) beats Tackle (0) regardless of Trick Room
        assert result.first_mover == "Fast"


class TestPriorityBrackets:
    """Test priority bracket utilities."""

    def test_get_protection_moves(self):
        """Should get all +4 priority moves."""
        moves = get_priority_moves_by_bracket(4)
        assert "protect" in moves
        assert "detect" in moves

    def test_get_fake_out_bracket(self):
        """Should get Fake Out and related moves."""
        moves = get_priority_moves_by_bracket(3)
        assert "fake-out" in moves
        assert "quick-guard" in moves

    def test_bracket_summary(self):
        """Should get all brackets."""
        summary = get_priority_bracket_summary()
        assert 4 in summary  # Protect
        assert 0 not in summary  # Normal moves not listed
        assert -7 in summary  # Trick Room


class TestCategorizePriority:
    """Test move categorization."""

    def test_protect_is_defensive(self):
        """Protect should be defensive."""
        info = categorize_priority_move("protect")
        assert info.category == "defensive"

    def test_helping_hand_is_support(self):
        """Helping Hand should be support."""
        info = categorize_priority_move("helping-hand")
        assert info.category == "support"

    def test_aqua_jet_is_offensive(self):
        """Aqua Jet should be offensive."""
        info = categorize_priority_move("aqua-jet")
        assert info.category == "offensive"


class TestTeamPriorityMoves:
    """Test finding priority moves on a team."""

    def test_find_priority_moves(self):
        """Should find priority moves in team."""
        team_moves = {
            "Incineroar": ["Fake Out", "Flare Blitz", "Knock Off", "Parting Shot"],
            "Rillaboom": ["Grassy Glide", "Wood Hammer", "U-turn", "Fake Out"]
        }
        result = find_team_priority_moves(team_moves)

        assert "Incineroar" in result
        assert "Rillaboom" in result
        assert any(m.move.lower().replace(" ", "-") == "fake-out"
                   for m in result["Incineroar"])

    def test_no_priority_moves(self):
        """Should return empty for team without priority."""
        team_moves = {
            "Pokemon": ["Tackle", "Ember", "Water Gun", "Thunderbolt"]
        }
        result = find_team_priority_moves(team_moves)
        assert len(result) == 0


class TestFakeOutMatchup:
    """Test Fake Out speed interaction."""

    def test_opponent_no_fake_out(self):
        """Should handle opponent without Fake Out."""
        result = analyze_fake_out_matchup(100, "flutter-mane", 200)
        assert result["opponent_has_fake_out"] is False

    def test_faster_wins_fake_out(self):
        """Faster Fake Out user should win."""
        result = analyze_fake_out_matchup(100, "incineroar", 80)
        assert "faster" in result["result"].lower()

    def test_slower_wins_in_trick_room(self):
        """Slower wins in Trick Room."""
        result = analyze_fake_out_matchup(100, "incineroar", 80, trick_room=True)
        assert "slower" in result["result"].lower() or "TR" in result["result"]


class TestNormalization:
    """Test move name normalization."""

    def test_normalize_spaces(self):
        """Should handle spaces."""
        assert normalize_move_name("Fake Out") == "fake-out"

    def test_normalize_case(self):
        """Should handle case."""
        assert normalize_move_name("PROTECT") == "protect"

    def test_normalize_apostrophe(self):
        """Should handle apostrophes."""
        assert normalize_move_name("King's Shield") == "kings-shield"


class TestPokemonLists:
    """Test common Pokemon lists."""

    def test_fake_out_pokemon(self):
        """Fake Out Pokemon list should include common users."""
        assert "incineroar" in FAKE_OUT_POKEMON
        assert "rillaboom" in FAKE_OUT_POKEMON

    def test_prankster_pokemon(self):
        """Prankster Pokemon list should include common users."""
        assert "whimsicott" in PRANKSTER_POKEMON
        assert "grimmsnarl" in PRANKSTER_POKEMON


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
