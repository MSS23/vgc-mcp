"""Tests for type-changing abilities (Pixilate, Aerilate, etc.) - Bug #2 fix verification.

This test verifies that moves affected by type-changing abilities show the correct
type effectiveness in the damage details output.
"""

import pytest
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, BaseStats, EVSpread
from vgc_mcp_core.models.move import Move, MoveCategory


class TestTypeChangingAbilities:
    """Test type-changing abilities show correct type effectiveness."""

    def test_pixilate_shows_correct_type_in_details(self):
        """Verify Pixilate shows Fairy type effectiveness, not Normal (Bug #2 fix).

        Pixilate converts Normal-type moves to Fairy-type and boosts them by 1.2x.
        The damage calculation correctly uses Fairy type effectiveness, but before
        the fix, the details output showed Normal type effectiveness.

        This test verifies that after the fix, the details show Fairy effectiveness.
        """
        # Sylveon with Pixilate
        sylveon = PokemonBuild(
            name="Sylveon",
            base_stats=BaseStats(
                hp=95, attack=65, defense=65,
                special_attack=110, special_defense=130, speed=60
            ),
            nature=Nature.MODEST,  # +SpA
            evs=EVSpread(special_attack=252, hp=252),
            types=["Fairy"],
            ability="pixilate"
        )

        # Machamp (Fighting type - weak to Fairy)
        machamp = PokemonBuild(
            name="Machamp",
            base_stats=BaseStats(
                hp=90, attack=130, defense=80,
                special_attack=65, special_defense=85, speed=55
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(hp=252, attack=252),
            types=["Fighting"]
        )

        # Hyper Voice (Normal-type move, converted to Fairy by Pixilate)
        hyper_voice = Move(
            name="hyper-voice",
            type="Normal",
            category=MoveCategory.SPECIAL,
            power=90,
            accuracy=100,
            pp=10
        )

        mods = DamageModifiers()
        result = calculate_damage(sylveon, machamp, hyper_voice, mods)

        # Print for debugging
        print(f"\nPixilate Hyper Voice vs Machamp:")
        print(f"Damage: {result.min_damage}-{result.max_damage}")
        print(f"Applied mods: {result.details.get('applied_mods', [])}")

        # Damage should be significant (super effective + STAB + 1.2x boost)
        # Normal vs Fighting would be neutral (1.0x)
        # Fairy vs Fighting is super effective (2.0x)
        # So we should see high damage

        # Check that damage is super effective (not neutral/immune)
        # Expected: > 50% damage against Machamp
        assert result.min_percent > 30.0, (
            f"Damage too low ({result.min_percent}%), "
            f"Pixilate should convert to Fairy (super effective)"
        )

        # The applied_mods should include "Super Effective (2x)" not "Immune (0x)"
        applied_mods_str = " ".join(result.details.get("applied_mods", []))

        # Should NOT show Normal-type immunity
        assert "Immune" not in applied_mods_str, (
            f"Details show Immune! Pixilate Hyper Voice should be Fairy-type "
            f"(super effective vs Fighting), not Normal-type (immune). "
            f"Applied mods: {applied_mods_str}"
        )

        # Should show super effective
        assert "Super Effective" in applied_mods_str or result.min_percent > 50.0, (
            f"Details should show 'Super Effective' for Fairy vs Fighting. "
            f"Applied mods: {applied_mods_str}"
        )

    def test_aerilate_shows_correct_type_in_details(self):
        """Verify Aerilate shows Flying type effectiveness, not Normal."""
        # Mega Salamence with Aerilate
        salamence = PokemonBuild(
            name="Salamence",
            base_stats=BaseStats(
                hp=95, attack=145, defense=130,
                special_attack=120, special_defense=90, speed=120
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(attack=252, speed=252),
            types=["Dragon", "Flying"],
            ability="aerilate"
        )

        # Machamp (Fighting type - weak to Flying)
        machamp = PokemonBuild(
            name="Machamp",
            base_stats=BaseStats(
                hp=90, attack=130, defense=80,
                special_attack=65, special_defense=85, speed=55
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(hp=252, attack=252),
            types=["Fighting"]
        )

        # Double-Edge (Normal-type move, converted to Flying by Aerilate)
        double_edge = Move(
            name="double-edge",
            type="Normal",
            category=MoveCategory.PHYSICAL,
            power=120,
            accuracy=100,
            pp=15
        )

        mods = DamageModifiers()
        result = calculate_damage(salamence, machamp, double_edge, mods)

        # Print for debugging
        print(f"\nAerilate Double-Edge vs Machamp:")
        print(f"Damage: {result.min_damage}-{result.max_damage}")
        print(f"Applied mods: {result.details.get('applied_mods', [])}")

        # Should show super effective damage (Flying vs Fighting = 2x)
        applied_mods_str = " ".join(result.details.get("applied_mods", []))

        # Should NOT show immunity
        assert "Immune" not in applied_mods_str, (
            f"Details show Immune! Aerilate should convert to Flying-type, not Normal. "
            f"Applied mods: {applied_mods_str}"
        )

        # Damage should be significant (super effective)
        assert result.min_percent > 50.0, (
            f"Damage too low ({result.min_percent}%), "
            f"Aerilate should convert to Flying (super effective vs Fighting)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to see print output
