"""Tests for Pokemon-accurate rounding."""

import pytest
from vgc_mcp_core.calc.damage import poke_round, apply_mod, STAT_STAGE_MODS, MOD_CHOICE_BOOST, MOD_RUIN


class TestPokeRound:
    """Test poke_round function."""
    
    def test_half_rounds_down(self):
        """0.5 should round DOWN in Pokemon."""
        assert poke_round(10.5) == 10
        assert poke_round(100.5) == 100
        assert poke_round(199.5) == 199
    
    def test_above_half_rounds_up(self):
        """Values > 0.5 should round UP."""
        assert poke_round(10.6) == 11
        assert poke_round(10.51) == 11
        assert poke_round(100.7) == 101
    
    def test_below_half_rounds_down(self):
        """Values < 0.5 should round DOWN."""
        assert poke_round(10.4) == 10
        assert poke_round(10.49) == 10
        assert poke_round(100.3) == 100
    
    def test_integers_unchanged(self):
        """Integer values should remain unchanged."""
        assert poke_round(10) == 10
        assert poke_round(100) == 100


class TestStatModifiers:
    """Test stat modifier application with proper rounding."""
    
    def test_choice_band_rounding(self):
        """133 * 1.5 = 199.5 should round to 199."""
        result = apply_mod(133, MOD_CHOICE_BOOST)
        assert result == 199
    
    def test_ruin_ability_rounding(self):
        """134 * 0.75 = 100.5 should round to 100."""
        result = apply_mod(134, MOD_RUIN)
        assert result == 100
    
    def test_stat_stage_modifiers(self):
        """Test stat stage modifiers use proper rounding."""
        # +1 stage = 1.5x
        result = apply_mod(100, STAT_STAGE_MODS[1])
        assert result == 150
        
        # -1 stage = 0.667x
        result = apply_mod(150, STAT_STAGE_MODS[-1])
        assert result == 100  # 150 * 0.667 = 100.05, rounds to 100
    
    def test_neutral_modifier(self):
        """4096 (1.0x) should not change value."""
        result = apply_mod(100, 4096)
        assert result == 100


class TestRoundingConsistency:
    """Test that rounding is consistent across different stat values."""
    
    def test_choice_band_consistency(self):
        """Choice Band should consistently round 1.5x multipliers."""
        test_cases = [
            (100, 150),
            (133, 199),  # 199.5 rounds down
            (134, 201),  # 201.0 rounds normally
            (200, 300),
        ]
        
        for input_val, expected in test_cases:
            result = apply_mod(input_val, MOD_CHOICE_BOOST)
            assert result == expected, f"Failed for {input_val}: got {result}, expected {expected}"
    
    def test_ruin_consistency(self):
        """Ruin abilities should consistently round 0.75x multipliers."""
        test_cases = [
            (100, 75),
            (134, 100),  # 100.5 rounds down
            (135, 101),  # 101.25 rounds down
            (200, 150),
        ]
        
        for input_val, expected in test_cases:
            result = apply_mod(input_val, MOD_RUIN)
            assert result == expected, f"Failed for {input_val}: got {result}, expected {expected}"
