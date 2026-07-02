"""Tests for champions_optimization helpers."""

from vgc_mcp_core.calc.champions_optimization import (
    SP_PER_STAT_MAX,
    SP_TOTAL_MAX,
    find_bulk_sps_to_survive,
    find_optimal_hp_sps,
    find_speed_sps_to_outspeed,
    validate_sp_allocation,
)
from vgc_mcp_core.models.pokemon import Nature


def test_constants():
    assert SP_PER_STAT_MAX == 32
    assert SP_TOTAL_MAX == 66


class TestSpeedFinder:
    def test_outspeed_one_short_of_max(self):
        # Dragapult base 142 Jolly: 32 SP -> 213, so to outspeed 212 we need... 32 SP
        sps = find_speed_sps_to_outspeed(142, 212, Nature.JOLLY)
        assert sps == 32

    def test_unreachable_returns_none(self):
        # Cannot outspeed 213 with only 142 base Jolly (max is 213, need 214)
        assert find_speed_sps_to_outspeed(142, 213, Nature.JOLLY) is None

    def test_zero_sp_already_outspeeds(self):
        # Dragapult base 142 Jolly at 0 SP outspeeds 100
        assert find_speed_sps_to_outspeed(142, 100, Nature.JOLLY) == 0


class TestHPOptimization:
    def test_leftovers_finds_mod_16_perfect(self):
        opts = find_optimal_hp_sps(100, "leftovers")
        # Top result should be a perfect mod-16 HP number
        top = opts[0]
        assert top["score"] == 1.0
        assert top["hp_stat"] % 16 == 0

    def test_life_orb_finds_mod_10_minus_one(self):
        opts = find_optimal_hp_sps(100, "life-orb")
        top = opts[0]
        assert top["score"] == 1.0
        assert top["hp_stat"] % 10 == 9

    def test_unknown_item_returns_neutral_scores(self):
        opts = find_optimal_hp_sps(100, "leftover-pizza")
        # Neutral scoring — all scores 1.0, primary sort is by SP asc (lowest first)
        assert all(o["score"] == 1.0 for o in opts)


class TestBulkSolver:
    def test_finds_minimum_allocation(self):
        # 100/100 base, 200 dmg incoming: should find a small SP allocation
        result = find_bulk_sps_to_survive(100, 100, 200)
        assert result is not None
        assert result["total_sp"] <= SP_TOTAL_MAX
        assert result["hp_remaining"] > 0

    def test_unsurvivable_returns_none(self):
        # 1 HP shedinja-style + 50 base def, 9999 dmg — cannot survive
        result = find_bulk_sps_to_survive(1, 50, 9999)
        assert result is None


class TestValidator:
    def test_valid_max_budget(self):
        v = validate_sp_allocation({"hp": 32, "attack": 32, "speed": 2})
        assert v["is_valid"] is True
        assert v["total"] == 66
        assert v["remaining"] == 0
        assert v["over_budget"] == 0

    def test_per_stat_violation(self):
        v = validate_sp_allocation({"hp": 33})
        assert v["is_valid"] is False
        assert "hp: 33 SP exceeds per-stat max (32)" in v["per_stat_violations"]

    def test_total_over_budget(self):
        v = validate_sp_allocation({"hp": 32, "attack": 32, "speed": 32})
        assert v["is_valid"] is False
        assert v["over_budget"] == 30
        assert v["per_stat_violations"] == []

    def test_negative_sp(self):
        v = validate_sp_allocation({"hp": -5})
        assert v["is_valid"] is False
        assert any("negative" in s for s in v["per_stat_violations"])
