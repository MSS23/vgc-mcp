"""Tests for move legality and learnset validation."""

import pytest
from vgc_mcp.validation.learnset import (
    normalize_move_name,
    categorize_learn_method,
    MoveValidationResult,
    MovesetValidationResult,
)


class TestMoveNormalization:
    """Test move name normalization."""

    def test_normalize_spaces(self):
        """Should convert spaces to hyphens."""
        assert normalize_move_name("Fake Out") == "fake-out"
        assert normalize_move_name("Close Combat") == "close-combat"

    def test_normalize_case(self):
        """Should convert to lowercase."""
        assert normalize_move_name("PROTECT") == "protect"
        assert normalize_move_name("Moonblast") == "moonblast"

    def test_normalize_apostrophe(self):
        """Should remove apostrophes."""
        assert normalize_move_name("King's Shield") == "kings-shield"

    def test_normalize_multi_word(self):
        """Should handle multi-word moves correctly."""
        # Test the normal use case of multi-word moves
        assert normalize_move_name("Close Combat") == "close-combat"
        assert normalize_move_name("fake out") == "fake-out"


class TestLearnMethodCategories:
    """Test learn method categorization."""

    def test_level_up(self):
        """Level-up should be categorized correctly."""
        assert categorize_learn_method("level-up") == "Level Up"

    def test_machine(self):
        """Machine should be categorized as TM/TR."""
        assert categorize_learn_method("machine") == "TM/TR"

    def test_egg(self):
        """Egg moves should note breeding."""
        result = categorize_learn_method("egg")
        assert "Egg" in result
        assert "breeding" in result.lower()

    def test_tutor(self):
        """Tutor should be categorized correctly."""
        assert categorize_learn_method("tutor") == "Move Tutor"

    def test_unknown_method(self):
        """Unknown methods should be title-cased."""
        assert categorize_learn_method("some-method") == "Some Method"


class TestMoveValidationResult:
    """Test MoveValidationResult dataclass."""

    def test_create_legal_move(self):
        """Should create legal move result."""
        result = MoveValidationResult(
            move="Protect",
            legal=True,
            methods=["machine", "level-up"],
            reason="Learnable via: machine, level-up"
        )
        assert result.legal is True
        assert len(result.methods) == 2

    def test_create_illegal_move(self):
        """Should create illegal move result."""
        result = MoveValidationResult(
            move="V-create",
            legal=False,
            methods=[],
            reason="Not learnable by this Pokemon"
        )
        assert result.legal is False
        assert len(result.methods) == 0


class TestMovesetValidationResult:
    """Test MovesetValidationResult dataclass."""

    def test_all_legal_moveset(self):
        """Should handle all legal moveset."""
        moves = [
            MoveValidationResult("Protect", True, ["machine"], "Learnable"),
            MoveValidationResult("Flamethrower", True, ["machine"], "Learnable"),
        ]
        result = MovesetValidationResult(
            pokemon="Charizard",
            all_legal=True,
            moves=moves,
            illegal_moves=[]
        )
        assert result.all_legal is True
        assert len(result.illegal_moves) == 0

    def test_has_illegal_moves(self):
        """Should track illegal moves."""
        moves = [
            MoveValidationResult("Protect", True, ["machine"], "Learnable"),
            MoveValidationResult("V-create", False, [], "Not learnable"),
        ]
        result = MovesetValidationResult(
            pokemon="Charizard",
            all_legal=False,
            moves=moves,
            illegal_moves=["V-create"]
        )
        assert result.all_legal is False
        assert "V-create" in result.illegal_moves


# Note: Async tests for API functions would require mocking the PokeAPI client
# These are integration tests that would be tested separately

class TestLearnsetIntegration:
    """Placeholder for integration tests with mocked API."""

    @pytest.mark.skip(reason="Requires mocked PokeAPI client")
    async def test_get_learnable_moves(self):
        """Test getting learnable moves from API."""
        pass

    @pytest.mark.skip(reason="Requires mocked PokeAPI client")
    async def test_validate_moveset(self):
        """Test validating a moveset."""
        pass

    @pytest.mark.skip(reason="Requires mocked PokeAPI client")
    async def test_validate_team_movesets(self):
        """Test validating team movesets."""
        pass

    @pytest.mark.skip(reason="Requires mocked PokeAPI client")
    async def test_suggest_legal_moves(self):
        """Test suggesting legal moves."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
