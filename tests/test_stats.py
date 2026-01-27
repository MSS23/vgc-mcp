"""Tests for stat calculations.

CRITICAL BENCHMARKS - These MUST pass:
| Pokemon      | Nature | Speed EVs | Expected Speed |
|--------------|--------|-----------|----------------|
| Flutter Mane | Timid  | 252       | 205            |
| Dragapult    | Jolly  | 252       | 213            |
| Urshifu      | Jolly  | 252       | 163            |
"""

import pytest
from vgc_mcp_core.calc.stats import (
    calculate_hp,
    calculate_stat,
    calculate_speed,
    calculate_all_stats,
    find_speed_evs,
)
from vgc_mcp_core.models.pokemon import (
    Nature,
    PokemonBuild,
    BaseStats,
    EVSpread,
    IVSpread,
)


class TestSpeedBenchmarks:
    """Critical speed benchmarks that MUST pass."""

    def test_flutter_mane_max_speed(self):
        """Flutter Mane: Timid, 252 EVs = 205 Speed"""
        # Base Speed: 135
        speed = calculate_speed(
            base_speed=135,
            iv=31,
            ev=252,
            level=50,
            nature=Nature.TIMID
        )
        assert speed == 205, f"Flutter Mane speed should be 205, got {speed}"

    def test_dragapult_max_speed(self):
        """Dragapult: Jolly, 252 EVs = 213 Speed"""
        # Base Speed: 142
        speed = calculate_speed(
            base_speed=142,
            iv=31,
            ev=252,
            level=50,
            nature=Nature.JOLLY
        )
        assert speed == 213, f"Dragapult speed should be 213, got {speed}"

    def test_urshifu_max_speed(self):
        """Urshifu: Jolly, 252 EVs = 163 Speed"""
        # Base Speed: 97
        speed = calculate_speed(
            base_speed=97,
            iv=31,
            ev=252,
            level=50,
            nature=Nature.JOLLY
        )
        assert speed == 163, f"Urshifu speed should be 163, got {speed}"

    def test_miraidon_max_speed(self):
        """Miraidon: Timid, 252 EVs = 205 Speed"""
        # Base Speed: 135 (same as Flutter Mane)
        speed = calculate_speed(
            base_speed=135,
            iv=31,
            ev=252,
            level=50,
            nature=Nature.TIMID
        )
        assert speed == 205

    def test_incineroar_neutral_speed(self):
        """Incineroar: Adamant (neutral speed), 0 EVs = 80 Speed"""
        # Base Speed: 60
        speed = calculate_speed(
            base_speed=60,
            iv=31,
            ev=0,
            level=50,
            nature=Nature.ADAMANT  # Neutral for speed
        )
        assert speed == 80, f"Incineroar speed should be 80, got {speed}"


class TestSpeedCalculationFormula:
    """Test the speed calculation formula in detail."""

    def test_neutral_nature_no_investment(self):
        """Base 100 speed, neutral nature, no EVs = 120"""
        # floor((2*100 + 31 + 0) * 0.5 + 5) * 1.0 = floor(115.5 + 5) = 120
        speed = calculate_speed(100, 31, 0, 50, Nature.SERIOUS)
        assert speed == 120

    def test_positive_nature_max_investment(self):
        """Base 100 speed, +speed nature, 252 EVs"""
        # floor((2*100 + 31 + 63) * 0.5 + 5) * 1.1
        # = floor((294) * 0.5 + 5) * 1.1
        # = floor(147 + 5) * 1.1
        # = 152 * 1.1 = 167.2 -> 167
        speed = calculate_speed(100, 31, 252, 50, Nature.JOLLY)
        assert speed == 167

    def test_negative_nature_no_investment(self):
        """Base 100 speed, -speed nature, 0 EVs"""
        # floor((2*100 + 31 + 0) * 0.5 + 5) * 0.9
        # = floor(115.5 + 5) * 0.9
        # = 120 * 0.9 = 108
        speed = calculate_speed(100, 31, 0, 50, Nature.BRAVE)
        assert speed == 108

    def test_zero_iv_zero_ev(self):
        """Base 100 speed, 0 IV, 0 EV, -speed nature (minimum)"""
        # floor((2*100 + 0 + 0) * 0.5 + 5) * 0.9
        # = floor(100 + 5) * 0.9
        # = 105 * 0.9 = 94.5 -> 94
        speed = calculate_speed(100, 0, 0, 50, Nature.BRAVE)
        assert speed == 94


class TestHPCalculation:
    """Test HP calculation formula."""

    def test_hp_formula_basic(self):
        """Base 100 HP, 31 IV, 0 EV, level 50"""
        # floor((2*100 + 31 + 0) * 0.5 + 50 + 10) = floor(115.5 + 60) = 175
        hp = calculate_hp(100, 31, 0, 50)
        assert hp == 175

    def test_hp_formula_max_investment(self):
        """Base 100 HP, 31 IV, 252 EV, level 50"""
        # floor((2*100 + 31 + 63) * 0.5 + 50 + 10)
        # = floor(294 * 0.5 + 60)
        # = floor(147 + 60) = 207
        hp = calculate_hp(100, 31, 252, 50)
        assert hp == 207

    def test_shedinja_always_1hp(self):
        """Shedinja (base HP = 1) always has 1 HP."""
        hp = calculate_hp(1, 31, 252, 50)
        assert hp == 1

    def test_entei_hp_ev_efficiency(self):
        """Verify HP EV recommendations are efficient (no wasteful breakpoints)."""
        from vgc_mcp_core.config import normalize_evs

        base_hp = 115  # Entei

        # Test that 112 EVs is wasteful
        hp_108 = calculate_hp(base_hp, iv=31, ev=108)
        hp_112 = calculate_hp(base_hp, iv=31, ev=112)
        hp_116 = calculate_hp(base_hp, iv=31, ev=116)

        assert hp_108 == 204, "108 EVs should give 204 HP"
        assert hp_112 == 204, "112 EVs gives same 204 HP (wasteful!)"
        assert hp_116 == 205, "116 EVs should give 205 HP"

        # Verify normalize_evs catches this:
        assert normalize_evs(112) == 108, "112 should normalize to 108"

        # Valid breakpoints around 112:
        assert normalize_evs(108) == 108
        assert normalize_evs(116) == 116


class TestFullStatCalculation:
    """Test full Pokemon stat calculations."""

    def test_flutter_mane_offensive_spread(self):
        """Flutter Mane: Timid 252 SpA / 4 SpD / 252 Spe"""
        pokemon = PokemonBuild(
            name="flutter-mane",
            base_stats=BaseStats(
                hp=55, attack=55, defense=55,
                special_attack=135, special_defense=135, speed=135
            ),
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, special_defense=4, speed=252),
            types=["Ghost", "Fairy"]
        )

        stats = calculate_all_stats(pokemon)

        assert stats["hp"] == 130  # 55 base, no investment
        assert stats["speed"] == 205  # Benchmark
        assert stats["special_attack"] == 187  # Max SpA with neutral from nature


class TestFindSpeedEVs:
    """Test finding required Speed EVs."""

    def test_find_evs_to_outspeed(self):
        """Find EVs to hit a specific speed target."""
        # Flutter Mane base 135, want to hit 205 with Timid
        evs = find_speed_evs(135, 205, Nature.TIMID)
        assert evs == 252

    def test_find_evs_lower_target(self):
        """Find EVs for lower speed target."""
        # Base 100, want 150 with Jolly
        evs = find_speed_evs(100, 150, Nature.JOLLY)
        assert evs is not None
        # Verify the result
        actual = calculate_speed(100, 31, evs, 50, Nature.JOLLY)
        assert actual >= 150

    def test_unreachable_target(self):
        """Return None if target is unreachable."""
        # Base 50 can't hit 200 even with max investment
        evs = find_speed_evs(50, 200, Nature.JOLLY)
        assert evs is None


class TestNatureModifiers:
    """Test nature modifiers are applied correctly."""

    def test_adamant_boosts_attack(self):
        """Adamant (+Atk, -SpA) should boost Attack."""
        base = 100
        atk_neutral = calculate_stat(base, 31, 252, 50, 1.0)
        atk_adamant = calculate_stat(base, 31, 252, 50, 1.1)
        assert atk_adamant > atk_neutral

    def test_modest_boosts_special_attack(self):
        """Modest (+SpA, -Atk) should boost Special Attack."""
        base = 100
        spa_neutral = calculate_stat(base, 31, 252, 50, 1.0)
        spa_modest = calculate_stat(base, 31, 252, 50, 1.1)
        assert spa_modest > spa_neutral

    def test_brave_reduces_speed(self):
        """Brave (+Atk, -Spe) should reduce Speed."""
        base = 100
        spe_neutral = calculate_stat(base, 31, 0, 50, 1.0)
        spe_brave = calculate_stat(base, 31, 0, 50, 0.9)
        assert spe_brave < spe_neutral


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
