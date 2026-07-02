"""Tests for the Champions stat calculator (calc/stats_champions.py)."""

import pytest

from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.calc.stats_champions import (
    calculate_all_stats_champions,
    calculate_hp_sp,
    calculate_speed_sp,
    calculate_stat_sp,
    find_speed_sps,
)
from vgc_mcp_core.models.pokemon import (
    BaseStats,
    Nature,
    PokemonBuild,
    StatPointSpread,
)


class TestSpeedBenchmarks:
    """At 32 SP a stat lands at the same value as at 252 EV in mainline.

    These benchmarks come from the mainline test suite — the SP system maps
    1 SP -> 8 EV-equivalent, so 32 SP saturates the floor-truncated stat
    formula identically to the 252 EV cap.
    """

    def test_dragapult_jolly_max_speed(self):
        # Mainline benchmark: Dragapult Jolly 252 Spe = 213
        assert calculate_speed_sp(142, 31, 32, 50, Nature.JOLLY) == 213

    def test_flutter_mane_timid_max_speed(self):
        # Mainline benchmark: Flutter Mane Timid 252 Spe = 205
        assert calculate_speed_sp(135, 31, 32, 50, Nature.TIMID) == 205

    def test_urshifu_jolly_max_speed(self):
        # Mainline benchmark: Urshifu Jolly 252 Spe = 163
        assert calculate_speed_sp(97, 31, 32, 50, Nature.JOLLY) == 163

    def test_zero_sp_neutral_speed(self):
        # Incineroar base 60, 0 SP, neutral nature -> 80 (matches mainline 0 EV)
        assert calculate_speed_sp(60, 31, 0, 50, Nature.SERIOUS) == 80


class TestHPCalc:
    def test_max_hp_invest(self):
        # Snorlax base 160 HP at 32 SP -> matches 252 EV mainline (244)
        from vgc_mcp_core.calc.stats import calculate_hp
        assert calculate_hp_sp(160, 31, 32, 50) == calculate_hp(160, 31, 252, 50)

    def test_shedinja_always_one(self):
        assert calculate_hp_sp(1, 31, 32, 50) == 1


class TestNatureDispatch:
    def test_adamant_attack_boost(self):
        # base 130 Atk, 32 SP, Adamant — should equal mainline 252 EV value
        from vgc_mcp_core.calc.stats import calculate_stat
        from vgc_mcp_core.models.pokemon import get_nature_modifier
        mod = get_nature_modifier(Nature.ADAMANT, "attack")
        assert calculate_stat_sp(130, 31, 32, 50, mod) == calculate_stat(130, 31, 252, 50, mod)


class TestAllStatsDispatcher:
    """`calculate_all_stats` must dispatch to the SP path for champions builds."""

    @pytest.fixture
    def base_stats(self):
        return BaseStats(hp=88, attack=120, defense=75, special_attack=100, special_defense=75, speed=142)

    def test_mainline_path_unchanged(self, base_stats):
        pb = PokemonBuild(
            name="dragapult",
            base_stats=base_stats,
            evs=__import__("vgc_mcp_core.models.pokemon", fromlist=["EVSpread"]).EVSpread(
                speed=252, attack=252, hp=4
            ),
            nature=Nature.JOLLY,
        )
        stats = calculate_all_stats(pb)
        assert stats["speed"] == 213
        assert stats["attack"] == 172

    def test_champions_path_routes_correctly(self, base_stats):
        pb = PokemonBuild(
            name="dragapult",
            base_stats=base_stats,
            format_system="champions",
            sps=StatPointSpread(speed=32, attack=32, hp=2),
            nature=Nature.JOLLY,
        )
        stats = calculate_all_stats(pb)
        assert stats["speed"] == 213
        assert stats["attack"] == 172

    def test_champions_no_sps_uses_zero(self, base_stats):
        pb = PokemonBuild(
            name="dragapult",
            base_stats=base_stats,
            format_system="champions",
            nature=Nature.SERIOUS,
        )
        stats = calculate_all_stats_champions(pb)
        # Speed at 0 SP, neutral nature
        assert stats["speed"] == calculate_speed_sp(142, 31, 0, 50, Nature.SERIOUS)


class TestFindSpeedSps:
    def test_finds_minimum_sp(self):
        # Need 213 Speed with Dragapult base 142 Jolly — should find 32 SP
        assert find_speed_sps(142, 213, Nature.JOLLY) == 32

    def test_returns_none_if_unreachable(self):
        # No SP value gets a 60 base, neutral nature, to 200 Speed
        assert find_speed_sps(60, 200, Nature.SERIOUS) is None

    def test_zero_sp_when_base_already_meets_target(self):
        # Dragapult base 142 Jolly already exceeds 100 Speed at 0 SP
        assert find_speed_sps(142, 100, Nature.JOLLY) == 0
