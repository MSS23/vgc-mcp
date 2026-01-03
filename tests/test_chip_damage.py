"""Tests for chip damage calculations including Salt Cure."""

import pytest
from vgc_mcp_core.calc.chip_damage import (
    calculate_salt_cure_damage,
    calculate_status_damage,
    calculate_weather_chip,
)


class TestSaltCure:
    """Test Salt Cure chip damage mechanics."""

    def test_salt_cure_normal_damage(self):
        """Salt Cure deals 12.5% to non-Steel/Water types."""
        max_hp = 200
        result = calculate_salt_cure_damage(
            current_hp=200,
            max_hp=max_hp,
            pokemon_types=["Fire", "Flying"]
        )

        assert not result.immune
        assert result.damage == max_hp // 8  # 12.5%
        assert result.damage == 25
        assert result.damage_percent == 12.5

    def test_salt_cure_steel_type_double_damage(self):
        """Salt Cure deals 25% to Steel types."""
        max_hp = 200
        result = calculate_salt_cure_damage(
            current_hp=200,
            max_hp=max_hp,
            pokemon_types=["Steel", "Flying"]
        )

        assert not result.immune
        assert result.damage == max_hp // 4  # 25%
        assert result.damage == 50
        assert result.damage_percent == 25.0
        assert "Steel" in result.notes[0]

    def test_salt_cure_water_type_double_damage(self):
        """Salt Cure deals 25% to Water types."""
        max_hp = 200
        result = calculate_salt_cure_damage(
            current_hp=200,
            max_hp=max_hp,
            pokemon_types=["Water", "Ground"]
        )

        assert not result.immune
        assert result.damage == max_hp // 4  # 25%
        assert result.damage == 50
        assert result.damage_percent == 25.0
        assert "Water" in result.notes[0]

    def test_salt_cure_magic_guard_immune(self):
        """Magic Guard blocks Salt Cure damage."""
        result = calculate_salt_cure_damage(
            current_hp=200,
            max_hp=200,
            pokemon_types=["Steel"],  # Would normally take 25%
            ability="magic-guard"
        )

        assert result.immune
        assert result.damage == 0
        assert "Magic Guard" in result.immunity_reason


class TestStatusDamage:
    """Test status condition damage."""

    def test_burn_damage(self):
        """Burn deals 6.25% damage."""
        max_hp = 160
        result = calculate_status_damage(
            status="burn",
            current_hp=160,
            max_hp=max_hp
        )

        assert not result.immune
        assert result.damage == max_hp // 16  # 6.25%
        assert result.damage == 10

    def test_poison_damage(self):
        """Poison deals 12.5% damage."""
        max_hp = 200
        result = calculate_status_damage(
            status="poison",
            current_hp=200,
            max_hp=max_hp
        )

        assert not result.immune
        assert result.damage == max_hp // 8  # 12.5%
        assert result.damage == 25

    def test_toxic_damage_increases(self):
        """Toxic damage increases each turn."""
        max_hp = 160

        # Turn 1: 1/16
        result_t1 = calculate_status_damage("toxic", 160, max_hp, toxic_counter=1)
        assert result_t1.damage == 10

        # Turn 5: 5/16
        result_t5 = calculate_status_damage("toxic", 160, max_hp, toxic_counter=5)
        assert result_t5.damage == 50

        # Turn 15: 15/16 (max)
        result_t15 = calculate_status_damage("toxic", 160, max_hp, toxic_counter=15)
        assert result_t15.damage == 150

    def test_poison_heal_converts_to_healing(self):
        """Poison Heal converts poison damage to healing."""
        max_hp = 200
        result = calculate_status_damage(
            status="poison",
            current_hp=100,
            max_hp=max_hp,
            ability="poison-heal"
        )

        assert result.is_healing
        assert result.damage == -25  # Negative = healing
        assert result.hp_after == 125


class TestWeatherChip:
    """Test weather chip damage."""

    def test_sandstorm_damages_normal_types(self):
        """Sandstorm deals 6.25% to non-immune types."""
        max_hp = 160
        result = calculate_weather_chip(
            weather="sandstorm",
            current_hp=160,
            max_hp=max_hp,
            pokemon_types=["Normal"]
        )

        assert not result.immune
        assert result.damage == max_hp // 16
        assert result.damage == 10

    def test_sandstorm_immune_rock_type(self):
        """Rock types are immune to Sandstorm."""
        result = calculate_weather_chip(
            weather="sandstorm",
            current_hp=160,
            max_hp=160,
            pokemon_types=["Rock", "Ground"]
        )

        assert result.immune
        assert result.damage == 0

    def test_sun_no_damage(self):
        """Sun doesn't deal chip damage."""
        result = calculate_weather_chip(
            weather="sun",
            current_hp=160,
            max_hp=160,
            pokemon_types=["Fire"]
        )

        assert result.immune
        assert result.damage == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
