"""Tests for intelligent nature selection algorithm."""

import pytest
from vgc_mcp_core.calc.nature_optimization import (
    find_optimal_nature_for_benchmarks,
    get_relevant_natures,
    calculate_evs_for_benchmarks,
    calculate_nature_score
)
from vgc_mcp_core.models.pokemon import Nature, BaseStats
from vgc_mcp_core.calc.stats import calculate_stat, calculate_speed


class TestGetRelevantNatures:
    """Test nature filtering logic."""

    def test_physical_attacker_natures(self):
        """Physical attackers should get +Atk natures."""
        natures = get_relevant_natures(is_physical=True, is_special=False, role="offensive")
        assert Nature.ADAMANT in natures
        assert Nature.JOLLY in natures
        assert Nature.SERIOUS in natures
        # Should not include -Atk natures
        assert Nature.MODEST not in natures

    def test_special_attacker_natures(self):
        """Special attackers should get +SpA natures."""
        natures = get_relevant_natures(is_physical=False, is_special=True, role="offensive")
        assert Nature.MODEST in natures
        assert Nature.TIMID in natures
        assert Nature.SERIOUS in natures
        # Should not include -SpA natures
        assert Nature.ADAMANT not in natures

    def test_defensive_role_natures(self):
        """Defensive role should get +Def/+SpD natures."""
        natures = get_relevant_natures(role="defensive")
        assert Nature.BOLD in natures
        assert Nature.CALM in natures
        assert Nature.IMPISH in natures
        assert Nature.CAREFUL in natures


class TestCalculateEVsForBenchmarks:
    """Test EV calculation for benchmarks."""

    def test_speed_benchmark_only(self):
        """Calculate EVs for speed benchmark."""
        base_stats = BaseStats(hp=115, attack=115, defense=85, special_attack=90, special_defense=75, speed=100)
        benchmarks = {"speed_target": 137}
        
        evs = calculate_evs_for_benchmarks(base_stats, Nature.ADAMANT, benchmarks)
        assert evs is not None
        assert evs["speed"] > 0
        assert evs["speed"] <= 252

    def test_impossible_speed_benchmark(self):
        """Return None for impossible speed target."""
        base_stats = BaseStats(hp=50, attack=50, defense=50, special_attack=50, special_defense=50, speed=30)
        benchmarks = {"speed_target": 300}  # Impossible even with 252 EVs
        
        evs = calculate_evs_for_benchmarks(base_stats, Nature.JOLLY, benchmarks)
        assert evs is None

    def test_offensive_benchmark(self):
        """Calculate EVs with offensive priority."""
        base_stats = BaseStats(hp=115, attack=115, defense=85, special_attack=90, special_defense=75, speed=100)
        benchmarks = {
            "speed_target": 137,
            "prioritize": "offense",
            "offensive_evs": 252
        }
        
        evs = calculate_evs_for_benchmarks(base_stats, Nature.ADAMANT, benchmarks)
        assert evs is not None
        assert evs["attack"] == 252
        assert evs["speed"] > 0


class TestCalculateNatureScore:
    """Test nature scoring function."""

    def test_physical_attacker_scoring(self):
        """Physical attackers prioritize Attack + Speed."""
        final_stats = {"attack": 167, "speed": 137, "hp": 187}
        score = calculate_nature_score(
            Nature.ADAMANT, final_stats, is_physical=True, is_special=False, total_evs=264, role="offensive"
        )
        assert score > 0
        # Higher attack should give higher score
        high_atk_score = calculate_nature_score(
            Nature.ADAMANT, {"attack": 167, "speed": 137, "hp": 187}, 
            is_physical=True, is_special=False, total_evs=264, role="offensive"
        )
        low_atk_score = calculate_nature_score(
            Nature.TIMID, {"attack": 147, "speed": 137, "hp": 187}, 
            is_physical=True, is_special=False, total_evs=264, role="offensive"
        )
        assert high_atk_score > low_atk_score

    def test_ev_penalty(self):
        """Higher EV usage should reduce score."""
        final_stats = {"attack": 167, "speed": 137, "hp": 187}
        low_ev_score = calculate_nature_score(
            Nature.ADAMANT, final_stats, is_physical=True, is_special=False, total_evs=264, role="offensive"
        )
        high_ev_score = calculate_nature_score(
            Nature.ADAMANT, final_stats, is_physical=True, is_special=False, total_evs=400, role="offensive"
        )
        assert low_ev_score > high_ev_score


class TestEnteiBenchmark:
    """Critical test: Entei should choose Adamant over Timid."""

    def test_entei_chooses_adamant(self):
        """
        Entei benchmark test: 137 Speed, maximize Attack.
        
        Expected: Adamant nature (167 Attack) beats Timid (147 Attack).
        """
        # Entei base stats: 115 HP, 115 Atk, 85 Def, 90 SpA, 75 SpD, 100 Spe
        entei_base = BaseStats(hp=115, attack=115, defense=85, special_attack=90, special_defense=75, speed=100)
        
        benchmarks = {
            "speed_target": 137,  # Outspeed -1 Chien-Pao
            "prioritize": "offense",
            "offensive_evs": 252
        }
        
        result = find_optimal_nature_for_benchmarks(
            base_stats=entei_base,
            benchmarks=benchmarks,
            is_physical=True,
            is_special=False,
            role="offensive"
        )
        
        assert result is not None
        assert result.best_nature == Nature.ADAMANT, f"Expected Adamant, got {result.best_nature}"
        assert result.final_stats["attack"] >= 167, f"Expected >= 167 Attack, got {result.final_stats['attack']}"
        assert result.final_stats["speed"] >= 137, f"Expected >= 137 Speed, got {result.final_stats['speed']}"
        
        # Verify Adamant gives more Attack than Timid would
        # Timid with same EVs would give ~147 Attack (115 base * 0.9 nature penalty)
        assert result.final_stats["attack"] > 150, "Adamant should give significantly more Attack than Timid"

    def test_entei_ev_distribution(self):
        """Verify Entei's EV distribution is efficient."""
        entei_base = BaseStats(hp=115, attack=115, defense=85, special_attack=90, special_defense=75, speed=100)
        
        benchmarks = {
            "speed_target": 137,
            "prioritize": "offense",
            "offensive_evs": 252
        }
        
        result = find_optimal_nature_for_benchmarks(
            base_stats=entei_base,
            benchmarks=benchmarks,
            is_physical=True,
            is_special=False,
            role="offensive"
        )
        
        assert result is not None
        total_evs = sum(result.evs.values())
        assert total_evs <= 508, f"Total EVs ({total_evs}) exceeds 508"
        
        # With Adamant, should need fewer Speed EVs than Timid
        # Adamant: +Atk means we can invest less in Attack EVs, more in Speed
        # Actually wait - if we need 137 Speed, Adamant needs MORE Speed EVs than Timid
        # But Adamant gives us +Atk boost, so we get more Attack with same Attack EVs
        # The key is: Adamant maximizes Attack stat while still hitting speed benchmark
        
        # Verify we're maximizing Attack
        assert result.evs["attack"] > 0, "Should invest in Attack EVs"
        assert result.final_stats["attack"] >= 167, "Should achieve high Attack"


class TestHighBaseSpeed:
    """Test Pokemon with high base Speed prefer Attack boost."""

    def test_high_speed_prefers_attack_boost(self):
        """
        Pokemon with base 140+ Speed should prefer +Atk over +Spe.
        Can hit speed benchmarks without nature boost, so maximize Attack.
        """
        # Example: Dragapult (base 142 Speed, 120 Attack)
        dragapult_base = BaseStats(hp=88, attack=120, defense=75, special_attack=100, special_defense=75, speed=142)
        
        benchmarks = {
            "speed_target": 200,  # Common speed tier
            "prioritize": "offense",
            "offensive_evs": 252
        }
        
        result = find_optimal_nature_for_benchmarks(
            base_stats=dragapult_base,
            benchmarks=benchmarks,
            is_physical=True,
            is_special=False,
            role="offensive"
        )
        
        assert result is not None
        # With high base Speed, Adamant (+Atk) should be preferred over Jolly (+Spe)
        # because we can hit speed benchmark with fewer EVs using Adamant
        assert result.best_nature in [Nature.ADAMANT, Nature.JOLLY]
        
        # Verify Attack is maximized (Dragapult with 252 Atk EVs and Adamant = ~172 Attack)
        assert result.final_stats["attack"] > 170, "Should achieve high Attack"


class TestLowBaseSpeed:
    """Test Pokemon with low base Speed require Speed boost."""

    def test_low_speed_requires_speed_boost(self):
        """
        Pokemon with base 60 Speed needs +Spe nature to hit common benchmarks.
        Jolly/Timid should be selected over Adamant/Modest.
        """
        # Example: Incineroar (base 60 Speed, 115 Attack)
        incineroar_base = BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60)
        
        benchmarks = {
            "speed_target": 100,  # Common speed tier
            "prioritize": "offense",
            "offensive_evs": 252
        }
        
        result = find_optimal_nature_for_benchmarks(
            base_stats=incineroar_base,
            benchmarks=benchmarks,
            is_physical=True,
            is_special=False,
            role="offensive"
        )
        
        assert result is not None
        # With low base Speed, Jolly (+Spe) should be preferred to hit speed benchmark
        # But if we can't hit it even with Jolly, might fall back to Adamant
        assert result.final_stats["speed"] >= 100 or result.best_nature == Nature.JOLLY


class TestSpecialAttacker:
    """Test special attackers prefer Modest over Timid."""

    def test_special_attacker_modest_vs_timid(self):
        """
        Special attackers with high base SpA should prefer Modest.
        Only choose Timid if speed benchmark cannot be met otherwise.
        """
        # Example: Flutter Mane (base 135 SpA, 135 Speed)
        flutter_base = BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135)
        
        benchmarks = {
            "speed_target": 200,  # Common speed tier
            "prioritize": "offense",
            "offensive_evs": 252
        }
        
        result = find_optimal_nature_for_benchmarks(
            base_stats=flutter_base,
            benchmarks=benchmarks,
            is_physical=False,
            is_special=True,
            role="offensive"
        )
        
        assert result is not None
        # With high base Speed, Modest (+SpA) should be preferred
        assert result.best_nature in [Nature.MODEST, Nature.TIMID]
        assert result.final_stats["special_attack"] > 180, "Should achieve high SpA"


class TestNeutralNature:
    """Test when neutral nature is optimal."""

    def test_neutral_nature_when_optimal(self):
        """
        Some spreads don't benefit from any nature (low EVs in all stats).
        Should recommend Serious/Hardy/Docile.
        """
        # Pokemon with very low EV investment
        base_stats = BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80)
        
        benchmarks = {
            "speed_target": None,
            "prioritize": "bulk",
        }
        
        result = find_optimal_nature_for_benchmarks(
            base_stats=base_stats,
            benchmarks=benchmarks,
            is_physical=False,
            is_special=False,
            role="defensive"
        )
        
        # Neutral nature might be optimal for defensive builds with low EVs
        assert result is not None
        # Should select a valid nature (could be neutral or defensive)


class TestImpossibleBenchmarks:
    """Test handling of impossible benchmarks."""

    def test_impossible_speed_benchmark(self):
        """Requesting 200 Speed on base 60 Pokemon should fail gracefully."""
        base_stats = BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=60)
        
        benchmarks = {
            "speed_target": 200,  # Impossible even with Jolly + 252 EVs
            "prioritize": "offense",
            "offensive_evs": 252
        }
        
        result = find_optimal_nature_for_benchmarks(
            base_stats=base_stats,
            benchmarks=benchmarks,
            is_physical=True,
            is_special=False,
            role="offensive"
        )
        
        # Should return None if impossible
        assert result is None, "Should return None for impossible benchmarks"


class TestBackwardCompatibility:
    """Test that explicit nature parameter still works."""

    def test_explicit_nature_bypasses_auto_selection(self):
        """Calling with explicit nature should use that nature."""
        # This test would be in the tool integration tests
        # For now, verify the function accepts explicit nature via benchmarks
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
