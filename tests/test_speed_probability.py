"""Tests for speed probability calculations."""

import pytest
from vgc_mcp_core.calc.speed_probability import (
    calculate_speed_stat,
    parse_spread_to_speed,
    calculate_outspeed_probability,
    calculate_meta_outspeed_rate,
    calculate_speed_creep_evs,
    get_nature_speed_modifier
)


class TestSpeedStatCalculation:
    """Test speed stat calculation from spreads."""

    def test_timid_max_speed_flutter_mane(self):
        """Flutter Mane base 135, Timid 252 should be 205."""
        speed = calculate_speed_stat(135, "Timid", 252)
        assert speed == 205

    def test_jolly_max_speed_dragapult(self):
        """Dragapult base 142, Jolly 252 should be 213."""
        speed = calculate_speed_stat(142, "Jolly", 252)
        assert speed == 213

    def test_adamant_no_speed_incineroar(self):
        """Incineroar base 60, Adamant 0 speed EVs."""
        speed = calculate_speed_stat(60, "Adamant", 0)
        assert speed == 80

    def test_jolly_max_speed_urshifu(self):
        """Urshifu base 97, Jolly 252 should be 163."""
        speed = calculate_speed_stat(97, "Jolly", 252)
        assert speed == 163

    def test_neutral_nature(self):
        """Neutral nature should give 1.0 modifier."""
        mod = get_nature_speed_modifier("Serious")
        assert mod == 1.0

    def test_minus_speed_nature(self):
        """Brave should give 0.9 speed modifier."""
        mod = get_nature_speed_modifier("Brave")
        assert mod == 0.9


class TestParseSpreadToSpeed:
    """Test parsing Smogon spread format to speed stat."""

    def test_modest_spread(self):
        """Test parsing Modest spread with no speed investment."""
        spread = {
            "nature": "Modest",
            "evs": {"hp": 252, "attack": 0, "defense": 4, "special_attack": 252, "special_defense": 0, "speed": 0}
        }
        # Base 100 speed with no EVs, neutral speed nature
        speed = parse_spread_to_speed(100, spread)
        assert speed == 120  # floor((floor((2*100+31)*0.5)+5)*1.0) = 120

    def test_timid_max_speed_spread(self):
        """Test parsing Timid max speed spread."""
        spread = {
            "nature": "Timid",
            "evs": {"hp": 0, "attack": 0, "defense": 4, "special_attack": 252, "special_defense": 0, "speed": 252}
        }
        # Base 135 speed (Flutter Mane)
        speed = parse_spread_to_speed(135, spread)
        assert speed == 205


class TestOutspeedProbability:
    """Test outspeed probability calculations."""

    def test_faster_than_all_spreads(self):
        """Pokemon faster than all target spreads = 100% outspeed."""
        # Your speed is 200
        # Target's spreads all result in speeds <= 150
        target_spreads = [
            {"nature": "Modest", "evs": {"speed": 0}, "usage": 50.0},
            {"nature": "Modest", "evs": {"speed": 60}, "usage": 30.0},
            {"nature": "Modest", "evs": {"speed": 100}, "usage": 20.0},
        ]
        # Base 80, all these result in < 200
        result = calculate_outspeed_probability(200, 80, target_spreads, "Target")

        assert result.outspeed_probability == 100.0
        assert result.underspeed_probability == 0.0

    def test_slower_than_all_spreads(self):
        """Pokemon slower than all target spreads = 0% outspeed."""
        # Your speed is 50
        # Target's spreads all result in speeds >= 100
        target_spreads = [
            {"nature": "Jolly", "evs": {"speed": 252}, "usage": 100.0},
        ]
        # Base 142 (Dragapult), Jolly 252 = 213
        result = calculate_outspeed_probability(50, 142, target_spreads, "Dragapult")

        assert result.outspeed_probability == 0.0
        assert result.underspeed_probability == 100.0

    def test_mixed_spreads_usage_weighted(self):
        """Outspeed rate correctly weighted by spread usage %."""
        # Your speed is exactly between two spread results
        target_spreads = [
            {"nature": "Modest", "evs": {"speed": 0}, "usage": 60.0},  # Slower
            {"nature": "Timid", "evs": {"speed": 252}, "usage": 40.0},  # Faster
        ]
        # Let's say your speed is 130, base 100
        # Modest 0 = 120 (you outspeed)
        # Timid 252 = 152 (they outspeed)
        result = calculate_outspeed_probability(130, 100, target_spreads, "Target")

        assert result.outspeed_probability == 60.0
        assert result.underspeed_probability == 40.0

    def test_empty_spreads(self):
        """Empty spread list should return 0% outspeed."""
        result = calculate_outspeed_probability(150, 100, [], "Target")
        assert result.outspeed_probability == 0.0
        assert result.underspeed_probability == 100.0


class TestMetaOutspeedRate:
    """Test meta-wide outspeed rate calculations."""

    def test_meta_outspeed_calculation(self):
        """Test calculating overall meta outspeed rate."""
        top_pokemon_data = [
            {
                "name": "Flutter Mane",
                "base_speed": 135,
                "usage_percent": 25.0,
                "spreads": [
                    {"nature": "Timid", "evs": {"speed": 252}, "usage": 80.0},
                    {"nature": "Modest", "evs": {"speed": 252}, "usage": 20.0},
                ]
            },
            {
                "name": "Incineroar",
                "base_speed": 60,
                "usage_percent": 20.0,
                "spreads": [
                    {"nature": "Adamant", "evs": {"speed": 0}, "usage": 100.0},
                ]
            },
        ]

        # With 150 speed, should outspeed Incineroar (80) but not Flutter Mane (205/186)
        result = calculate_meta_outspeed_rate(150, "Test Pokemon", top_pokemon_data)

        # Should have reasonable outspeed rate
        assert 0 <= result.total_outspeed_rate <= 100
        assert len(result.pokemon_analysis) == 2


class TestSpeedCreepCalculator:
    """Test speed creep EV calculations."""

    def test_find_evs_to_outspeed_100_pct(self):
        """Find EVs to outspeed 100% of spreads."""
        target_spreads = [
            {"nature": "Adamant", "evs": {"speed": 0}, "usage": 100.0},
        ]
        # Base 80 Adamant 0 = 96 speed
        # Need to hit 97+ to outspeed

        result = calculate_speed_creep_evs(
            your_base_speed=100,  # Your base
            your_nature="Jolly",  # +Speed nature
            target_base_speed=80,  # Target base
            target_spreads=target_spreads,
            desired_outspeed_pct=100.0
        )

        assert result["evs_needed"] is not None
        assert result["actual_outspeed_pct"] == 100.0

    def test_cannot_achieve_outspeed(self):
        """Test when target is much faster and can't be outsped."""
        target_spreads = [
            {"nature": "Timid", "evs": {"speed": 252}, "usage": 100.0},
        ]
        # Base 142 Timid 252 = 213 (Dragapult max)

        result = calculate_speed_creep_evs(
            your_base_speed=60,  # Slow base like Incineroar
            your_nature="Jolly",
            target_base_speed=142,
            target_spreads=target_spreads,
            desired_outspeed_pct=100.0
        )

        # Should indicate can't achieve
        assert result.get("cannot_achieve", False) or result.get("actual_outspeed_pct", 0) < 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
