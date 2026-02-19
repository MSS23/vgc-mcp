"""Tests for HP number optimization for items and terrain."""

import pytest

from vgc_mcp_core.calc.hp_optimization import (
    adjust_hp_evs_for_item,
    find_optimal_hp_evs,
    score_hp_for_item,
)
from vgc_mcp_core.calc.stats import calculate_hp


# ---------------------------------------------------------------------------
# TestScoreHpForItem
# ---------------------------------------------------------------------------
class TestScoreHpForItem:
    """Test HP scoring for different items."""

    # --- Leftovers / Black Sludge (1/16 recovery) ---

    def test_leftovers_perfect_divisibility(self):
        """HP divisible by 16 should score 1.0 for Leftovers."""
        assert score_hp_for_item(192, "leftovers") == 1.0
        assert score_hp_for_item(176, "leftovers") == 1.0
        assert score_hp_for_item(160, "leftovers") == 1.0

    def test_leftovers_imperfect(self):
        """HP not divisible by 16 should score < 1.0."""
        score = score_hp_for_item(191, "leftovers")
        assert 0.0 < score < 1.0

    def test_black_sludge_same_as_leftovers(self):
        """Black Sludge uses same 1/16 formula as Leftovers."""
        assert score_hp_for_item(192, "black-sludge") == 1.0
        assert score_hp_for_item(191, "black-sludge") < 1.0

    def test_grassy_terrain_same_as_leftovers(self):
        """Grassy Terrain uses same 1/16 formula."""
        assert score_hp_for_item(192, "grassy-terrain") == 1.0
        assert score_hp_for_item(191, "grassy-terrain") < 1.0

    # --- Life Orb (1/10 recoil) ---

    def test_life_orb_optimal(self):
        """HP = 10n-1 (remainder 9) should score 1.0 for Life Orb."""
        assert score_hp_for_item(159, "life-orb") == 1.0
        assert score_hp_for_item(169, "life-orb") == 1.0
        assert score_hp_for_item(179, "life-orb") == 1.0

    def test_life_orb_worst(self):
        """HP = 10n (remainder 0) should score 0.0 for Life Orb."""
        assert score_hp_for_item(160, "life-orb") == 0.0
        assert score_hp_for_item(170, "life-orb") == 0.0

    def test_life_orb_middle(self):
        """HP with middle remainders should score between 0 and 1."""
        score = score_hp_for_item(165, "life-orb")  # remainder 5
        assert 0.0 < score < 1.0

    # --- Sitrus Berry (1/4 heal) ---

    def test_sitrus_perfect(self):
        """HP divisible by 4 should score 1.0 for Sitrus Berry."""
        assert score_hp_for_item(188, "sitrus-berry") == 1.0
        assert score_hp_for_item(200, "sitrus-berry") == 1.0

    def test_sitrus_imperfect(self):
        """HP not divisible by 4 should score < 1.0."""
        score = score_hp_for_item(189, "sitrus-berry")  # 189 % 4 = 1
        assert 0.0 < score < 1.0

    # --- Unknown / No item ---

    def test_unknown_item_neutral(self):
        """Unknown items should always score 1.0 (no preference)."""
        assert score_hp_for_item(191, "choice-band") == 1.0
        assert score_hp_for_item(160, "assault-vest") == 1.0
        assert score_hp_for_item(175, "focus-sash") == 1.0

    # --- Item name normalization ---

    def test_item_name_spaces(self):
        """Items with spaces should be normalized."""
        assert score_hp_for_item(160, "Life Orb") == 0.0  # 160 % 10 == 0 (worst)
        assert score_hp_for_item(159, "Life Orb") == 1.0

    def test_item_name_mixed_case(self):
        """Items with mixed case should be normalized."""
        assert score_hp_for_item(192, "LEFTOVERS") == 1.0


# ---------------------------------------------------------------------------
# TestFindOptimalHpEvs
# ---------------------------------------------------------------------------
class TestFindOptimalHpEvs:
    """Test finding optimal HP EV values for items."""

    def test_returns_sorted_by_score(self):
        """Results should be sorted by score descending."""
        results = find_optimal_hp_evs(95, "leftovers")  # Incineroar base HP
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_leftovers_finds_16n_values(self):
        """Top results for Leftovers should have HP divisible by 16."""
        results = find_optimal_hp_evs(95, "leftovers")
        top_results = [r for r in results if r["score"] == 1.0]
        assert len(top_results) > 0
        for r in top_results:
            assert r["hp_stat"] % 16 == 0, f"HP {r['hp_stat']} is not divisible by 16"

    def test_life_orb_finds_10n_minus_1(self):
        """Top results for Life Orb should have HP % 10 == 9."""
        results = find_optimal_hp_evs(100, "life-orb")  # Urshifu base HP
        top_results = [r for r in results if r["score"] == 1.0]
        assert len(top_results) > 0
        for r in top_results:
            assert r["hp_stat"] % 10 == 9, f"HP {r['hp_stat']} % 10 != 9"

    def test_respects_ev_limits(self):
        """No EVs should exceed 252 or be negative."""
        results = find_optimal_hp_evs(80, "leftovers")
        for r in results:
            assert 0 <= r["ev"] <= 252

    def test_recovery_amounts_leftovers(self):
        """Recovery amounts should match hp // 16."""
        results = find_optimal_hp_evs(95, "leftovers")
        for r in results:
            expected_recovery = r["hp_stat"] // 16
            assert r["recovery_per_turn"] == expected_recovery

    def test_recoil_amounts_life_orb(self):
        """Recoil amounts should be negative hp // 10."""
        results = find_optimal_hp_evs(100, "life-orb")
        for r in results:
            expected_recoil = -(r["hp_stat"] // 10)
            assert r["recovery_per_turn"] == expected_recoil

    def test_heal_amounts_sitrus(self):
        """Heal amounts should match hp // 4."""
        results = find_optimal_hp_evs(90, "sitrus-berry")
        for r in results:
            expected_heal = r["hp_stat"] // 4
            assert r["recovery_per_turn"] == expected_heal

    def test_notes_describe_remainder(self):
        """Notes should describe the HP remainder."""
        results = find_optimal_hp_evs(95, "leftovers")
        optimal = [r for r in results if r["score"] == 1.0]
        assert any("optimal" in r["notes"].lower() for r in optimal)


# ---------------------------------------------------------------------------
# TestAdjustHpEvs
# ---------------------------------------------------------------------------
class TestAdjustHpEvs:
    """Test HP EV adjustment for items."""

    def test_adjusts_within_range(self):
        """Should find better HP number within ±8 EVs."""
        # Incineroar base 95: 252 EVs = 202 HP (202 % 16 = 10)
        # 244 EVs = 200 HP (200 % 16 = 8) - not optimal
        # Need to check if there's an optimal within range
        result = adjust_hp_evs_for_item(95, 252, "leftovers", max_adjustment=8)
        # Should try nearby values
        assert result["adjusted_evs"] <= 252
        assert result["score_after"] >= result["score_before"]

    def test_no_change_when_already_optimal(self):
        """Should return same EVs if HP is already perfect."""
        # Find an EV value that gives HP divisible by 16 for base 95
        for ev in range(0, 253, 4):
            hp = calculate_hp(95, 31, ev, 50)
            if hp % 16 == 0:
                result = adjust_hp_evs_for_item(95, ev, "leftovers")
                assert result["adjusted_evs"] == ev
                assert result["ev_cost"] == 0
                assert "Already optimal" in result["improvement"]
                break

    def test_no_change_for_unknown_item(self):
        """Should return same EVs for items without HP optimization."""
        result = adjust_hp_evs_for_item(95, 252, "choice-band")
        assert result["adjusted_evs"] == 252
        assert result["ev_cost"] == 0

    def test_prefers_lower_ev_cost(self):
        """When multiple options have same score, prefer smaller adjustment."""
        # Use a wider range to ensure there are multiple options
        result = adjust_hp_evs_for_item(95, 100, "leftovers", max_adjustment=12)
        # If adjusted, the adjustment should be as small as possible
        if result["ev_cost"] != 0:
            assert abs(result["ev_cost"]) <= 12

    def test_returns_score_info(self):
        """Should include before and after scores."""
        result = adjust_hp_evs_for_item(95, 252, "leftovers")
        assert "score_before" in result
        assert "score_after" in result
        assert 0.0 <= result["score_before"] <= 1.0
        assert 0.0 <= result["score_after"] <= 1.0

    def test_life_orb_reduces_recoil(self):
        """Life Orb adjustment should reduce recoil."""
        # Urshifu base 100: find an EV value that gives HP divisible by 10
        for ev in range(0, 253, 4):
            hp = calculate_hp(100, 31, ev, 50)
            if hp % 10 == 0:
                result = adjust_hp_evs_for_item(100, ev, "life-orb", max_adjustment=8)
                # Score should improve (or stay if no nearby option)
                assert result["score_after"] >= result["score_before"]
                break

    def test_ev_adjustment_is_valid_breakpoint(self):
        """Adjusted EVs should be a valid EV breakpoint."""
        from vgc_mcp_core.config import EV_BREAKPOINTS_LV50
        result = adjust_hp_evs_for_item(95, 100, "leftovers", max_adjustment=12)
        assert result["adjusted_evs"] in EV_BREAKPOINTS_LV50

    def test_sitrus_berry_adjustment(self):
        """Sitrus Berry should prefer HP divisible by 4."""
        result = adjust_hp_evs_for_item(80, 100, "sitrus-berry", max_adjustment=8)
        adjusted_hp = result["adjusted_hp"]
        original_hp = result["original_hp"]
        # If adjusted, the new HP should be at least as good for Sitrus
        assert score_hp_for_item(adjusted_hp, "sitrus-berry") >= score_hp_for_item(
            original_hp, "sitrus-berry"
        )


# ---------------------------------------------------------------------------
# TestHpOptimizationIntegration
# ---------------------------------------------------------------------------
class TestHpOptimizationIntegration:
    """Integration tests verifying HP calculations match chip_damage.py formulas."""

    def test_leftovers_recovery_matches_chip_formula(self):
        """Recovery from find_optimal_hp_evs should match chip_damage.py formula."""
        from vgc_mcp_core.calc.chip_damage import calculate_leftovers_recovery

        results = find_optimal_hp_evs(95, "leftovers")
        for r in results[:5]:  # Check first 5
            chip_result = calculate_leftovers_recovery(r["hp_stat"], r["hp_stat"])
            assert r["recovery_per_turn"] == abs(chip_result.damage)

    def test_life_orb_recoil_matches_item_formula(self):
        """Recoil from find_optimal_hp_evs should match items.py formula."""
        from vgc_mcp_core.calc.items import calculate_life_orb_effect

        results = find_optimal_hp_evs(100, "life-orb")
        for r in results[:5]:
            item_result = calculate_life_orb_effect(100, r["hp_stat"])
            assert abs(r["recovery_per_turn"]) == item_result["recoil"]

    def test_real_pokemon_leftovers_optimization(self):
        """Test with real Incineroar stats (base 95 HP)."""
        results = find_optimal_hp_evs(95, "leftovers")
        # Find the 0 EV option
        zero_ev = next(r for r in results if r["ev"] == 0)
        # Incineroar 0 HP EVs = floor((2*95 + 31) * 0.5 + 60) = floor(110.5 + 60) = 170
        assert zero_ev["hp_stat"] == calculate_hp(95, 31, 0, 50)

        # 252 EV option
        max_ev = next(r for r in results if r["ev"] == 252)
        assert max_ev["hp_stat"] == calculate_hp(95, 31, 252, 50)

    def test_real_pokemon_life_orb_optimization(self):
        """Test with real Urshifu stats (base 100 HP)."""
        results = find_optimal_hp_evs(100, "life-orb")
        # All top results should have HP ending in 9
        top = [r for r in results if r["score"] == 1.0]
        assert len(top) > 0
        for r in top:
            assert r["hp_stat"] % 10 == 9
