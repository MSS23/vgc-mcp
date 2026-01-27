"""Tests for Surging Strikes damage calculation against Ogerpon.

This test verifies the user-reported issue where Surging Strikes damage
was calculated as 93.8%-110.6% instead of the expected 93.8%-113.9%.
"""

import pytest
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, BaseStats, EVSpread
from vgc_mcp_core.models.move import Move, MoveCategory


class TestSurgingStrikesVsOgerpon:
    """Test Surging Strikes damage calculations against Ogerpon-Hearthflame."""

    def test_urshifu_surging_strikes_vs_ogerpon_hearthflame(self):
        """Test the exact scenario from user's Showdown calc.

        Expected from Showdown:
        152 Atk Mystic Water Tera-Water Urshifu-Rapid-Strike Surging Strikes (3 hits)
        vs. 188 HP / 0 Def Ogerpon-Hearthflame on a critical hit:
        168-204 (93.8-113.9%) -- 85.77% chance to OHKO

        Key details:
        - Urshifu IS Tera Water (2.0x STAB)
        - Ogerpon is NOT Tera'd (stays Grass/Fire, which is neutral to Water)
        - 188 HP EVs gives Ogerpon 179 HP at level 50
        - Water vs Grass/Fire: 2.0x (Fire) × 0.5x (Grass) = 1.0x neutral
        """
        # Urshifu-Rapid-Strike: 100/130/100/63/60/97 base stats
        urshifu = PokemonBuild(
            name="urshifu-rapid-strike",
            base_stats=BaseStats(
                hp=100, attack=130, defense=100,
                special_attack=63, special_defense=60, speed=97
            ),
            nature=Nature.JOLLY,  # Neutral Attack
            evs=EVSpread(attack=152),  # Exact EVs from user's calc
            types=["Fighting", "Water"],
            ability="unseen-fist",
            item="mystic-water"
        )

        # Ogerpon-Hearthflame: 80/120/84/60/96/110 base stats
        # With 188 HP EVs = 179 HP (as clarified by user)
        ogerpon = PokemonBuild(
            name="ogerpon-hearthflame",
            base_stats=BaseStats(
                hp=80, attack=120, defense=84,
                special_attack=60, special_defense=96, speed=110
            ),
            nature=Nature.JOLLY,  # Neutral Defense
            evs=EVSpread(hp=188),  # 188 HP EVs, 0 Def EVs as specified
            types=["Grass", "Fire"],
            ability="mold-breaker",
            item="hearthflame-mask"
        )

        # Surging Strikes: 25 BP per hit, 3 hits, always crits
        surging_strikes = Move(
            name="surging-strikes",
            type="Water",
            category=MoveCategory.PHYSICAL,
            power=25,  # Per hit
            accuracy=100,
            pp=5
        )

        # Urshifu is Tera Water, but Ogerpon is NOT Tera'd (stays Grass/Fire = neutral to Water)
        mods = DamageModifiers(
            attacker_item="mystic-water",
            attacker_ability="unseen-fist",
            defender_item="hearthflame-mask",
            defender_ability="mold-breaker",
            tera_active=True,  # Urshifu Tera Water
            tera_type="Water",
            defender_tera_active=False,  # Ogerpon is NOT Tera'd in this calc
            # Note: Don't set is_critical manually - Surging Strikes sets it automatically
        )

        result = calculate_damage(urshifu, ogerpon, surging_strikes, mods)

        # Print results for debugging
        print(f"\nUrshifu Tera Water Surging Strikes vs Ogerpon-Hearthflame Tera Fire")
        print(f"Ogerpon HP: {result.defender_hp}")
        print(f"Damage: {result.min_damage}-{result.max_damage}")
        print(f"Percent: {result.min_percent:.1f}%-{result.max_percent:.1f}%")
        print(f"KO Chance: {result.ko_chance}")
        print(f"Rolls that OHKO: {result.ko_probability.rolls_that_ohko}/16")
        print(f"\nExpected from Showdown: 168-204 (93.8%-113.9%), 85.77% OHKO (~14/16 rolls)")
        print(f"Our calculation: {result.min_damage}-{result.max_damage} ({result.min_percent:.1f}%-{result.max_percent:.1f}%), {result.ko_probability.ohko_chance:.2f}% OHKO ({result.ko_probability.rolls_that_ohko}/16 rolls)")

        # Verify damage range matches Showdown: 168-204
        assert result.min_damage == 168, f"Min damage should be 168, got {result.min_damage}"
        assert result.max_damage == 204, f"Max damage should be 204, got {result.max_damage}"

        # Verify KO chance: 85.77% OHKO means 13-14 out of 16 rolls kill
        # With 179 HP, we need 180+ damage to OHKO
        # Expected: most rolls KO, but not all (around 13-14/16)
        assert 12 <= result.ko_probability.rolls_that_ohko <= 15, (
            f"Expected 12-15 rolls to OHKO (around 85%), got {result.ko_probability.rolls_that_ohko}/16"
        )

    def test_surging_strikes_damage_range_variance(self):
        """Verify that Surging Strikes has correct damage variance from random rolls.

        The variance from min (85%) to max (100%) random roll should be 100/85 = 1.176x.
        User reported max% was 110.6% but expected 113.9%.
        This suggests the max damage might not be scaling correctly with the random factor.
        """
        # Simple scenario to test variance
        urshifu = PokemonBuild(
            name="urshifu-rapid-strike",
            base_stats=BaseStats(hp=100, attack=130, defense=100, special_attack=63, special_defense=60, speed=97),
            nature=Nature.ADAMANT,  # +Atk
            evs=EVSpread(attack=252),
            types=["Fighting", "Water"],
            ability="unseen-fist",
            item="mystic-water"
        )

        # Bulky defender
        rillaboom = PokemonBuild(
            name="rillaboom",
            base_stats=BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85),
            nature=Nature.CAREFUL,  # +SpD
            evs=EVSpread(hp=252, special_defense=252),
            types=["Grass"],
            item="assault-vest"
        )

        surging_strikes = Move(name="surging-strikes", type="Water", category=MoveCategory.PHYSICAL, power=25, accuracy=100, pp=5)

        mods = DamageModifiers(attacker_item="mystic-water", defender_item="assault-vest")
        result = calculate_damage(urshifu, rillaboom, surging_strikes, mods)

        # Calculate actual variance
        variance_ratio = result.max_damage / result.min_damage
        expected_variance = 100 / 85  # 1.176

        print(f"\nDamage variance test:")
        print(f"Min damage: {result.min_damage} (at 85% roll)")
        print(f"Max damage: {result.max_damage} (at 100% roll)")
        print(f"Variance ratio: {variance_ratio:.3f}")
        print(f"Expected variance: {expected_variance:.3f}")

        # Variance should be close to 1.176 (within rounding error from multi-hit calc)
        # Due to rounding at each step, actual variance can be slightly higher
        assert 1.10 <= variance_ratio <= 1.25, (
            f"Damage variance {variance_ratio:.3f} is outside expected range 1.10-1.25"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to see print output
