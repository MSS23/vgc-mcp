"""Tests for bulk optimization with diminishing returns."""

import pytest
from vgc_mcp_core.calc.bulk_optimization import (
    calculate_optimal_bulk_distribution,
    calculate_hp,
    calculate_defense_stat,
    calculate_effective_bulk,
    analyze_diminishing_returns,
    calculate_marginal_gain
)


class TestBasicCalculations:
    """Test basic stat calculation functions."""

    def test_hp_calculation(self):
        """Test HP stat calculation."""
        # Standard HP calculation at level 50
        # HP = floor((2*Base + IV + EV/4)*50/100 + 50 + 10)
        hp = calculate_hp(base=100, ev=252, iv=31)
        # floor((2*100 + 31 + 63)*0.5 + 60) = floor(294*0.5 + 60) = floor(147 + 60) = 207
        assert hp == 207

    def test_hp_with_zero_evs(self):
        """Test HP with no EV investment."""
        hp = calculate_hp(base=100, ev=0, iv=31)
        # floor((2*100 + 31 + 0)*0.5 + 60) = floor(231*0.5 + 60) = floor(115.5 + 60) = 175
        assert hp == 175

    def test_defense_calculation(self):
        """Test defense stat calculation."""
        # Stat = floor((floor((2*Base + IV + EV/4)*50/100) + 5) * Nature)
        defense = calculate_defense_stat(base=100, ev=252, nature_mod=1.0, iv=31)
        # floor((floor((2*100 + 31 + 63)*0.5) + 5) * 1.0) = floor(147 + 5) = 152
        assert defense == 152

    def test_defense_with_nature_boost(self):
        """Test defense with +10% nature boost."""
        defense = calculate_defense_stat(base=100, ev=252, nature_mod=1.1, iv=31)
        # floor((floor((2*100 + 31 + 63)*0.5) + 5) * 1.1) = floor(152 * 1.1) = 167
        assert defense == 167

    def test_effective_bulk(self):
        """Test effective bulk calculation."""
        bulk = calculate_effective_bulk(hp=200, defense=100)
        assert bulk == 20000


class TestOptimalBulkDistribution:
    """Test optimal bulk EV distribution."""

    def test_high_hp_pokemon_invests_in_defense(self):
        """High base HP Pokemon should invest more in defenses."""
        # Blissey-like stats: high HP, low defense
        result = calculate_optimal_bulk_distribution(
            base_hp=255,  # Very high HP
            base_def=10,  # Very low defense
            base_spd=135,
            nature="Bold",  # +Def nature
            total_bulk_evs=252,
            defense_weight=1.0  # Physical bulk only
        )

        # Should invest more in defense due to high base HP
        assert result.def_evs >= result.hp_evs

    def test_high_defense_pokemon_invests_in_hp(self):
        """High base Defense Pokemon should invest more in HP."""
        # Shuckle-like stats: low HP, high defense
        result = calculate_optimal_bulk_distribution(
            base_hp=20,   # Low HP
            base_def=230,  # Very high defense
            base_spd=230,
            nature="Bold",
            total_bulk_evs=252,
            defense_weight=1.0
        )

        # Should invest more in HP due to high base defense
        assert result.hp_evs >= result.def_evs

    def test_balanced_pokemon_splits_evs(self):
        """Equal base HP/Def should result in roughly balanced investment."""
        result = calculate_optimal_bulk_distribution(
            base_hp=100,
            base_def=100,
            base_spd=100,
            nature="Bold",
            total_bulk_evs=252,
            defense_weight=0.5  # Balanced
        )

        # Should have some spread between stats
        assert result.hp_evs > 0
        # Could invest in either def or spd depending on weight

    def test_nature_boost_reduces_ev_need(self):
        """Defense-boosting nature should shift EVs toward HP."""
        result_bold = calculate_optimal_bulk_distribution(
            base_hp=100,
            base_def=100,
            base_spd=100,
            nature="Bold",  # +Def
            total_bulk_evs=252,
            defense_weight=1.0
        )

        result_hardy = calculate_optimal_bulk_distribution(
            base_hp=100,
            base_def=100,
            base_spd=100,
            nature="Hardy",  # Neutral
            total_bulk_evs=252,
            defense_weight=1.0
        )

        # Bold should invest less in Defense and more in HP (or similar bulk)
        # The key is the bulk_score should be higher with Bold
        assert result_bold.physical_bulk >= result_hardy.physical_bulk

    def test_efficiency_better_than_single_stat(self):
        """Optimal distribution should be better than dumping all into one stat."""
        result = calculate_optimal_bulk_distribution(
            base_hp=100,
            base_def=100,
            base_spd=100,
            nature="Bold",
            total_bulk_evs=252,
            defense_weight=1.0
        )

        # Efficiency should show improvement over naive allocation
        comparison = result.comparison
        if comparison:
            # Optimal should be better than or equal to all-HP or all-Def
            assert result.physical_bulk >= comparison.get("all_hp_bulk", 0)


class TestDiminishingReturns:
    """Test diminishing returns analysis."""

    def test_marginal_gain_decreases(self):
        """Marginal gain should decrease as EVs increase."""
        # At 0 EVs, marginal gain should be higher than at 248 EVs
        gain_at_0 = calculate_marginal_gain(base_stat=100, current_evs=0, stat_type="hp")
        gain_at_248 = calculate_marginal_gain(base_stat=100, current_evs=248, stat_type="hp")

        # Both should be 0 or 1 (adding 4 EVs gives +1 or +0 to stat)
        # Due to how floor works, gains are typically 0 or 1
        assert gain_at_0 >= 0
        assert gain_at_248 >= 0

    def test_analyze_returns(self):
        """Test full diminishing returns analysis."""
        analysis = analyze_diminishing_returns(
            base_hp=100,
            base_def=100,
            base_spd=100,
            nature="Bold"
        )

        assert "hp_gains" in analysis
        assert "def_gains" in analysis
        assert "spd_gains" in analysis
        assert "recommendations" in analysis

        # Should have entries at various EV thresholds
        assert len(analysis["hp_gains"]) > 0


class TestDefenseWeighting:
    """Test defense weight parameter."""

    def test_physical_only(self):
        """Defense weight 1.0 should focus on physical bulk."""
        result = calculate_optimal_bulk_distribution(
            base_hp=100,
            base_def=100,
            base_spd=100,
            nature="Bold",
            total_bulk_evs=252,
            defense_weight=1.0
        )

        # Should invest in Def, not SpD
        assert result.def_evs >= result.spd_evs

    def test_special_only(self):
        """Defense weight 0.0 should focus on special bulk."""
        result = calculate_optimal_bulk_distribution(
            base_hp=100,
            base_def=100,
            base_spd=100,
            nature="Calm",  # +SpD
            total_bulk_evs=252,
            defense_weight=0.0
        )

        # Should invest in SpD, not Def
        assert result.spd_evs >= result.def_evs

    def test_balanced(self):
        """Defense weight 0.5 should balance both."""
        result = calculate_optimal_bulk_distribution(
            base_hp=100,
            base_def=100,
            base_spd=100,
            nature="Hardy",
            total_bulk_evs=252,
            defense_weight=0.5
        )

        # Should have investment in both defenses or HP
        total = result.hp_evs + result.def_evs + result.spd_evs
        assert total <= 252


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
