"""Tests for Life Orb optimization tools."""

import pytest
from vgc_mcp_core.calc.item_optimization import (
    compare_items_damage,
    analyze_life_orb_sustainability,
    calculate_ev_tradeoff
)
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, IVSpread, BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.calc.modifiers import DamageModifiers


class TestCompareItemsDamage:
    """Test item damage comparison."""

    def test_life_orb_vs_choice_band(self):
        """Compare Life Orb vs Choice Band damage."""
        attacker = PokemonBuild(
            name="landorus",
            base_stats=BaseStats(hp=89, attack=145, defense=90, special_attack=105, special_defense=80, speed=91),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252)
        )
        
        defender = PokemonBuild(
            name="rillaboom",
            base_stats=BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85),
            nature=Nature.ADAMANT,
            evs=EVSpread()
        )
        
        move = Move(
            name="earthquake",
            base_power=100,
            category=MoveCategory.PHYSICAL,
            type="ground"
        )
        
        modifiers = DamageModifiers(is_doubles=True)
        items = ["life-orb", "choice-band"]
        
        results = compare_items_damage(attacker, defender, move, items, modifiers, has_sheer_force=False)
        
        assert len(results) == 2
        assert results[0].item in items
        assert results[1].item in items
        # Life Orb should have recoil, Choice Band should not
        life_orb_result = next((r for r in results if r.item == "life-orb"), None)
        choice_band_result = next((r for r in results if r.item == "choice-band"), None)
        
        assert life_orb_result is not None
        assert choice_band_result is not None
        assert life_orb_result.recoil_per_attack > 0
        assert choice_band_result.recoil_per_attack == 0

    def test_sheer_force_negates_recoil(self):
        """Sheer Force should negate Life Orb recoil."""
        attacker = PokemonBuild(
            name="landorus",
            base_stats=BaseStats(hp=89, attack=145, defense=90, special_attack=105, special_defense=80, speed=91),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252)
        )
        
        defender = PokemonBuild(
            name="rillaboom",
            base_stats=BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85),
            nature=Nature.ADAMANT,
            evs=EVSpread()
        )
        
        move = Move(
            name="earth-power",
            base_power=90,
            category=MoveCategory.SPECIAL,
            type="ground"
        )
        
        modifiers = DamageModifiers(is_doubles=True)
        results = compare_items_damage(attacker, defender, move, ["life-orb"], modifiers, has_sheer_force=True)
        
        assert len(results) == 1
        assert results[0].recoil_per_attack == 0
        assert "Sheer Force" in results[0].recommendation


class TestLifeOrbSustainability:
    """Test Life Orb sustainability analysis."""

    def test_sustainability_calculation(self):
        """Test sustainability calculation with different HP investments."""
        pokemon = PokemonBuild(
            name="flutter-mane",
            base_stats=BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
            nature=Nature.TIMID,
            evs=EVSpread()
        )
        
        # Test with 0 HP EVs
        analysis_0 = analyze_life_orb_sustainability(pokemon, 0, [], moves_per_game=4)
        assert analysis_0.hp_evs == 0
        assert analysis_0.attacks_before_faint > 0
        
        # Test with 252 HP EVs
        analysis_252 = analyze_life_orb_sustainability(pokemon, 252, [], moves_per_game=4)
        assert analysis_252.hp_evs == 252
        assert analysis_252.max_hp > analysis_0.max_hp

    def test_recovery_sources(self):
        """Test recovery sources affect sustainability."""
        pokemon = PokemonBuild(
            name="flutter-mane",
            base_stats=BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
            nature=Nature.TIMID,
            evs=EVSpread()
        )
        
        # Without recovery
        analysis_no_recovery = analyze_life_orb_sustainability(pokemon, 0, [], moves_per_game=4)
        
        # With Leftovers recovery
        analysis_with_recovery = analyze_life_orb_sustainability(pokemon, 0, ["leftovers"], moves_per_game=4)
        
        # Recovery should increase sustainability
        assert analysis_with_recovery.attacks_before_faint >= analysis_no_recovery.attacks_before_faint


class TestEVTradeoff:
    """Test EV-item trade-off analysis."""

    def test_choice_vs_life_orb_evs(self):
        """Choice items should save EVs compared to Life Orb."""
        pokemon = PokemonBuild(
            name="flutter-mane",
            base_stats=BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
            nature=Nature.TIMID,
            evs=EVSpread()
        )
        
        benchmark = {}
        items = ["life-orb", "choice-specs"]
        
        results = calculate_ev_tradeoff(pokemon, benchmark, items, "special_attack")
        
        assert len(results) == 2
        # Results should be sorted by total useful stats
        assert results[0].total_useful_stats >= results[1].total_useful_stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
