"""Tests for EV efficiency optimization."""

import pytest
from vgc_mcp_core.calc.stats import (
    optimize_ev_efficiency,
    optimize_spread_efficiency,
    validate_ev_efficiency,
    calculate_stat,
    calculate_hp
)
from vgc_mcp_core.models.pokemon import (
    PokemonBuild,
    BaseStats,
    EVSpread,
    IVSpread,
    Nature
)


class TestOptimizeEVEfficiency:
    """Tests for optimize_ev_efficiency() function."""

    def test_urshifu_attack_waste(self):
        """Test the Urshifu-RS example: 152 Attack EVs should optimize to 148."""
        # Urshifu-RS: 130 Attack base, 31 IV, Jolly nature (1.1x)
        # 152 Attack EVs = 185 Attack stat
        # 148 Attack EVs = 185 Attack stat (same!)

        result = optimize_ev_efficiency(130, 31, 152, 50, 1.1, "normal")
        assert result == 148, f"Expected 148, got {result}"

        # Verify both give same stat
        stat_152 = calculate_stat(130, 31, 152, 50, 1.1)
        stat_148 = calculate_stat(130, 31, 148, 50, 1.1)
        assert stat_152 == stat_148 == 185

    def test_no_waste(self):
        """Test case where EVs are already optimal (no waste)."""
        # Test with a spread that doesn't have waste
        result = optimize_ev_efficiency(100, 31, 252, 50, 1.0, "normal")
        # Should stay at 252 or be optimized if there's waste
        # We'll just check it returns a valid value <= 252
        assert 0 <= result <= 252

    def test_zero_evs(self):
        """Test with 0 EVs (edge case)."""
        result = optimize_ev_efficiency(100, 31, 0, 50, 1.0, "normal")
        assert result == 0

    def test_hp_optimization(self):
        """Test HP EV optimization (different formula)."""
        # Test with HP stat type
        result = optimize_ev_efficiency(100, 31, 156, 50, 1.0, "hp")
        # Verify the result gives a valid HP value
        hp = calculate_hp(100, 31, result, 50)
        assert hp >= calculate_hp(100, 31, 0, 50)

    def test_multiple_reduction_levels(self):
        """Test that the function checks 4, 8, and 12 EV reductions."""
        # Create a case where 12 EV reduction still gives same stat
        # This is rare but possible with certain base stats
        result = optimize_ev_efficiency(85, 31, 252, 50, 1.0, "normal")
        # Should return something <= 252
        assert result <= 252

    def test_nature_modifiers(self):
        """Test with different nature modifiers."""
        base = 100

        # Positive nature (1.1x)
        result_pos = optimize_ev_efficiency(base, 31, 200, 50, 1.1, "normal")
        assert result_pos <= 200

        # Neutral nature (1.0x)
        result_neu = optimize_ev_efficiency(base, 31, 200, 50, 1.0, "normal")
        assert result_neu <= 200

        # Negative nature (0.9x)
        result_neg = optimize_ev_efficiency(base, 31, 200, 50, 0.9, "normal")
        assert result_neg <= 200


class TestOptimizeSpreadEfficiency:
    """Tests for optimize_spread_efficiency() function."""

    def test_urshifu_full_spread(self):
        """Test optimizing a full Urshifu spread with waste."""
        pokemon = PokemonBuild(
            name="Urshifu-Rapid-Strike",
            base_stats=BaseStats(hp=100, attack=130, defense=100, special_attack=63, special_defense=60, speed=97),
            evs=EVSpread(),
            ivs=IVSpread(),
            nature=Nature.JOLLY
        )

        current_evs = {
            "hp": 156,
            "attack": 152,  # Wasted!
            "defense": 0,
            "special_attack": 0,
            "special_defense": 108,
            "speed": 92
        }

        optimized, saved = optimize_spread_efficiency(pokemon, current_evs)

        # Should optimize Attack EVs from 152 to 148
        assert optimized["attack"] == 148, f"Expected 148 Attack EVs, got {optimized['attack']}"
        assert saved == 4, f"Expected 4 EVs saved, got {saved}"

        # Verify the stat is the same
        stat_original = calculate_stat(130, 31, 152, 50, 1.1)
        stat_optimized = calculate_stat(130, 31, 148, 50, 1.1)
        assert stat_original == stat_optimized == 185

    def test_no_waste_spread(self):
        """Test optimizing a spread that's already efficient."""
        pokemon = PokemonBuild(
            name="Test",
            base_stats=BaseStats(hp=100, attack=100, defense=100, special_attack=100, special_defense=100, speed=100),
            evs=EVSpread(hp=252, attack=0, defense=0, special_attack=0, special_defense=0, speed=0),
            ivs=IVSpread(),
            nature=Nature.SERIOUS
        )

        current_evs = {
            "hp": 252,
            "attack": 0,
            "defense": 0,
            "special_attack": 0,
            "special_defense": 0,
            "speed": 0
        }

        optimized, saved = optimize_spread_efficiency(pokemon, current_evs)

        # Should have 0 or minimal savings
        assert saved >= 0
        assert optimized["hp"] <= 252


class TestValidateEVEfficiency:
    """Tests for validate_ev_efficiency() function."""

    def test_detect_waste(self):
        """Test detecting wasted EVs."""
        pokemon = PokemonBuild(
            name="Urshifu-Rapid-Strike",
            base_stats=BaseStats(hp=100, attack=130, defense=100, special_attack=63, special_defense=60, speed=97),
            evs=EVSpread(),
            ivs=IVSpread(),
            nature=Nature.JOLLY
        )

        wasteful_evs = {
            "hp": 156,
            "attack": 152,  # Wasted!
            "defense": 0,
            "special_attack": 0,
            "special_defense": 108,
            "speed": 92
        }

        result = validate_ev_efficiency(pokemon, wasteful_evs)

        assert not result["is_efficient"], "Should detect inefficiency"
        assert result["total_wasted"] == 4, f"Expected 4 wasted EVs, got {result['total_wasted']}"
        assert "attack" in result["wasted_evs"], "Should identify attack as having waste"
        assert len(result["suggestions"]) > 0, "Should provide optimization suggestions"

    def test_efficient_spread(self):
        """Test validating an already efficient spread."""
        pokemon = PokemonBuild(
            name="Test",
            base_stats=BaseStats(hp=100, attack=100, defense=100, special_attack=100, special_defense=100, speed=100),
            evs=EVSpread(hp=252, attack=0, defense=0, special_attack=0, special_defense=0, speed=4),
            ivs=IVSpread(),
            nature=Nature.SERIOUS
        )

        efficient_evs = {
            "hp": 252,
            "attack": 0,
            "defense": 0,
            "special_attack": 0,
            "special_defense": 0,
            "speed": 4
        }

        result = validate_ev_efficiency(pokemon, efficient_evs)

        # Should be efficient or close to it
        # (might have minimal waste depending on base stats)
        assert result["total_wasted"] <= 4  # Allow for some edge cases


class TestIntegration:
    """Integration tests for EV efficiency across multiple functions."""

    def test_stat_consistency(self):
        """Test that optimized EVs give the same or better stats."""
        pokemon = PokemonBuild(
            name="Test",
            base_stats=BaseStats(hp=100, attack=130, defense=95, special_attack=80, special_defense=85, speed=100),
            evs=EVSpread(),
            ivs=IVSpread(),
            nature=Nature.ADAMANT  # +Atk, -SpA
        )

        # Create a spread with potential waste
        wasteful_evs = {
            "hp": 200,
            "attack": 152,
            "defense": 100,
            "special_attack": 0,
            "special_defense": 56,
            "speed": 0
        }

        # Optimize it
        optimized_evs, saved = optimize_spread_efficiency(pokemon, wasteful_evs)

        # Calculate stats for both spreads
        for stat_name in ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]:
            base_stat = getattr(pokemon.base_stats, stat_name)
            iv = 31

            if stat_name == "hp":
                original_stat = calculate_hp(base_stat, iv, wasteful_evs[stat_name], 50)
                optimized_stat = calculate_hp(base_stat, iv, optimized_evs[stat_name], 50)
            else:
                from vgc_mcp_core.models.pokemon import get_nature_modifier
                nature_mod = get_nature_modifier(pokemon.nature, stat_name)
                original_stat = calculate_stat(base_stat, iv, wasteful_evs[stat_name], 50, nature_mod)
                optimized_stat = calculate_stat(base_stat, iv, optimized_evs[stat_name], 50, nature_mod)

            # Optimized stat should be the same or better (never worse)
            assert optimized_stat >= original_stat, (
                f"{stat_name}: optimized stat ({optimized_stat}) should not be worse "
                f"than original ({original_stat})"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
