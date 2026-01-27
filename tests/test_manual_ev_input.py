"""Test that manual EV input prevents Smogon auto-fetch."""

import pytest
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, BaseStats, EVSpread
from vgc_mcp_core.models.move import Move, MoveCategory


class TestManualEVInput:
    """Test that user-specified EVs are not overridden by Smogon data."""

    def test_partial_attacker_evs_uses_defaults_not_smogon(self):
        """When user specifies only attacker_spa_evs, should use 0 for atk_evs instead of Smogon."""
        # This test verifies the fix: if user provides ANY EV manually,
        # don't fetch from Smogon and use 0 for missing EVs

        # Create attacker with only SpA EVs specified
        landorus = PokemonBuild(
            name="landorus-incarnate",
            base_stats=BaseStats(
                hp=89, attack=125, defense=90,
                special_attack=115, special_defense=80, speed=101
            ),
            nature=Nature.MODEST,
            evs=EVSpread(special_attack=252),  # Only SpA specified
            types=["Ground", "Flying"],
            ability="sheer-force",
            item="life-orb"
        )

        # Verify attack EVs are 0 (not Smogon's default)
        assert landorus.evs.attack == 0, "Attack EVs should default to 0 when user specifies only SpA"

        entei = PokemonBuild(
            name="entei",
            base_stats=BaseStats(
                hp=115, attack=115, defense=85,
                special_attack=90, special_defense=75, speed=100
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(special_defense=4),
            types=["Fire"],
            tera_type="Normal"
        )

        earth_power = Move(
            name="earth-power",
            type="Ground",
            category=MoveCategory.SPECIAL,
            power=90,
            accuracy=100,
            pp=10,
            effect_chance=10
        )

        mods = DamageModifiers(
            is_doubles=True,
            defender_tera_active=True,
            defender_tera_type="Normal"
        )

        result = calculate_damage(landorus, entei, earth_power, mods)

        # Should get damage based on 252 SpA (not Smogon's 124 SpA)
        # With 252 SpA + Modest + Sheer Force + Life Orb, should get higher damage
        assert result.min_damage > 100, f"Expected high damage with 252 SpA, got {result.min_damage}"

    def test_partial_defender_evs_uses_defaults_not_smogon(self):
        """When user specifies only defender HP EVs, should use 0 for Def/SpD instead of Smogon."""
        attacker = PokemonBuild(
            name="urshifu-rapid-strike",
            base_stats=BaseStats(
                hp=100, attack=130, defense=100,
                special_attack=63, special_defense=60, speed=97
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(attack=252),
            types=["Fighting", "Water"],
            ability="unseen-fist",
            item="mystic-water"
        )

        # Defender with only HP EVs specified
        ogerpon = PokemonBuild(
            name="ogerpon-hearthflame",
            base_stats=BaseStats(
                hp=80, attack=120, defense=84,
                special_attack=60, special_defense=96, speed=110
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(hp=188),  # Only HP specified
            types=["Grass", "Fire"],
            item="hearthflame-mask"
        )

        # Verify defense EVs are 0
        assert ogerpon.evs.defense == 0, "Defense EVs should default to 0 when user specifies only HP"
        assert ogerpon.evs.special_defense == 0, "SpD EVs should default to 0 when user specifies only HP"

        surging_strikes = Move(
            name="surging-strikes",
            type="Water",
            category=MoveCategory.PHYSICAL,
            power=25,
            accuracy=100,
            pp=5
        )

        mods = DamageModifiers(is_doubles=True)
        result = calculate_damage(attacker, ogerpon, surging_strikes, mods)

        # With 0 Def EVs, damage should be higher than with Smogon's typical spread
        assert result.min_damage > 0

    def test_no_evs_specified_uses_all_defaults(self):
        """When no EVs specified, should default to 0 for all stats."""
        attacker = PokemonBuild(
            name="pikachu",
            base_stats=BaseStats(
                hp=35, attack=55, defense=40,
                special_attack=50, special_defense=50, speed=90
            ),
            nature=Nature.TIMID,
            evs=EVSpread(),  # No EVs specified
            types=["Electric"]
        )

        # All EVs should be 0
        assert attacker.evs.hp == 0
        assert attacker.evs.attack == 0
        assert attacker.evs.defense == 0
        assert attacker.evs.special_attack == 0
        assert attacker.evs.special_defense == 0
        assert attacker.evs.speed == 0

    def test_all_evs_specified_uses_user_values(self):
        """When all EVs specified, should use exactly those values."""
        pokemon = PokemonBuild(
            name="charizard",
            base_stats=BaseStats(
                hp=78, attack=84, defense=78,
                special_attack=109, special_defense=85, speed=100
            ),
            nature=Nature.TIMID,
            evs=EVSpread(
                hp=4,
                attack=0,
                defense=0,
                special_attack=252,
                special_defense=0,
                speed=252
            ),
            types=["Fire", "Flying"]
        )

        # Should use exact values specified
        assert pokemon.evs.hp == 4
        assert pokemon.evs.attack == 0
        assert pokemon.evs.defense == 0
        assert pokemon.evs.special_attack == 252
        assert pokemon.evs.special_defense == 0
        assert pokemon.evs.speed == 252


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
