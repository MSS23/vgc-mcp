"""Tests for damage calculations."""

import pytest
from vgc_mcp_core.calc.damage import calculate_damage, _get_stab_modifier
from vgc_mcp_core.calc.modifiers import (
    DamageModifiers,
    get_type_effectiveness,
    is_super_effective,
    is_immune,
)
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, BaseStats, EVSpread
from vgc_mcp_core.models.move import Move, MoveCategory


class TestTypeEffectiveness:
    """Test type effectiveness calculations."""

    def test_super_effective_single_type(self):
        """Fire is super effective against Grass."""
        eff = get_type_effectiveness("Fire", ["Grass"])
        assert eff == 2.0

    def test_super_effective_dual_type(self):
        """Fire is 4x effective against Grass/Steel."""
        eff = get_type_effectiveness("Fire", ["Grass", "Steel"])
        assert eff == 4.0

    def test_not_very_effective(self):
        """Water is not very effective against Water."""
        eff = get_type_effectiveness("Water", ["Water"])
        assert eff == 0.5

    def test_immune(self):
        """Normal is immune to Ghost."""
        eff = get_type_effectiveness("Normal", ["Ghost"])
        assert eff == 0

    def test_ground_immune_flying(self):
        """Ground doesn't affect Flying."""
        eff = get_type_effectiveness("Ground", ["Flying"])
        assert eff == 0

    def test_double_resist(self):
        """Fire is 0.25x against Water/Dragon."""
        eff = get_type_effectiveness("Fire", ["Water", "Dragon"])
        assert eff == 0.25

    def test_neutral(self):
        """Normal is neutral against most types."""
        eff = get_type_effectiveness("Normal", ["Fire"])
        assert eff == 1.0


class TestSpreadMoveModifier:
    """Test spread move damage reduction in doubles."""

    def test_spread_move_multiple_targets(self):
        """Spread moves do 0.75x when hitting multiple targets."""
        attacker = PokemonBuild(
            name="landorus",
            base_stats=BaseStats(
                hp=89, attack=125, defense=90,
                special_attack=115, special_defense=80, speed=101
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Ground", "Flying"]
        )

        defender = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, special_defense=252),
            types=["Fire", "Dark"]
        )

        earthquake = Move(
            name="earthquake",
            type="Ground",
            category=MoveCategory.PHYSICAL,
            power=100,
            accuracy=100,
            pp=10,
            target="all-adjacent"
        )

        # Single target
        mods_single = DamageModifiers(is_doubles=True, multiple_targets=False)
        result_single = calculate_damage(attacker, defender, earthquake, mods_single)

        # Multiple targets
        mods_multi = DamageModifiers(is_doubles=True, multiple_targets=True)
        result_multi = calculate_damage(attacker, defender, earthquake, mods_multi)

        # Spread should do less damage
        assert result_multi.max_damage < result_single.max_damage
        # Should be approximately 75% damage
        ratio = result_multi.max_damage / result_single.max_damage
        assert 0.74 <= ratio <= 0.76


class TestSTABModifier:
    """Test STAB (Same Type Attack Bonus) calculations."""

    def test_stab_applied(self):
        """STAB should be 1.5x for matching type."""
        attacker = PokemonBuild(
            name="charizard",
            base_stats=BaseStats(
                hp=78, attack=84, defense=78,
                special_attack=109, special_defense=85, speed=100
            ),
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252),
            types=["Fire", "Flying"]
        )

        fire_blast = Move(
            name="fire-blast",
            type="Fire",
            category=MoveCategory.SPECIAL,
            power=110,
            accuracy=85,
            pp=5
        )

        mods = DamageModifiers()
        stab = _get_stab_modifier(attacker, fire_blast, mods)
        assert stab == 1.5

    def test_no_stab_different_type(self):
        """No STAB for non-matching type."""
        attacker = PokemonBuild(
            name="charizard",
            base_stats=BaseStats(
                hp=78, attack=84, defense=78,
                special_attack=109, special_defense=85, speed=100
            ),
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252),
            types=["Fire", "Flying"]
        )

        solar_beam = Move(
            name="solar-beam",
            type="Grass",
            category=MoveCategory.SPECIAL,
            power=120,
            accuracy=100,
            pp=10
        )

        mods = DamageModifiers()
        stab = _get_stab_modifier(attacker, solar_beam, mods)
        assert stab == 1.0

    def test_tera_stab_same_type(self):
        """Tera into same type = 2x STAB."""
        attacker = PokemonBuild(
            name="charizard",
            base_stats=BaseStats(
                hp=78, attack=84, defense=78,
                special_attack=109, special_defense=85, speed=100
            ),
            nature=Nature.TIMID,
            types=["Fire", "Flying"],
            tera_type="Fire"
        )

        fire_blast = Move(
            name="fire-blast",
            type="Fire",
            category=MoveCategory.SPECIAL,
            power=110,
            accuracy=85,
            pp=5
        )

        mods = DamageModifiers(tera_type="Fire", tera_active=True)
        stab = _get_stab_modifier(attacker, fire_blast, mods)
        assert stab == 2.0

    def test_tera_stab_new_type(self):
        """Tera into new type = 1.5x STAB."""
        attacker = PokemonBuild(
            name="charizard",
            base_stats=BaseStats(
                hp=78, attack=84, defense=78,
                special_attack=109, special_defense=85, speed=100
            ),
            nature=Nature.TIMID,
            types=["Fire", "Flying"],
            tera_type="Grass"
        )

        solar_beam = Move(
            name="solar-beam",
            type="Grass",
            category=MoveCategory.SPECIAL,
            power=120,
            accuracy=100,
            pp=10
        )

        mods = DamageModifiers(tera_type="Grass", tera_active=True)
        stab = _get_stab_modifier(attacker, solar_beam, mods)
        assert stab == 1.5


class TestWeatherModifiers:
    """Test weather damage modifiers."""

    def test_sun_boosts_fire(self):
        """Sun boosts Fire moves by 1.5x."""
        mods = DamageModifiers(weather="sun")
        mod = mods.get_weather_modifier("Fire")
        assert mod == 1.5

    def test_sun_weakens_water(self):
        """Sun weakens Water moves by 0.5x."""
        mods = DamageModifiers(weather="sun")
        mod = mods.get_weather_modifier("Water")
        assert mod == 0.5

    def test_rain_boosts_water(self):
        """Rain boosts Water moves by 1.5x."""
        mods = DamageModifiers(weather="rain")
        mod = mods.get_weather_modifier("Water")
        assert mod == 1.5

    def test_rain_weakens_fire(self):
        """Rain weakens Fire moves by 0.5x."""
        mods = DamageModifiers(weather="rain")
        mod = mods.get_weather_modifier("Fire")
        assert mod == 0.5


class TestScreenModifiers:
    """Test Reflect/Light Screen damage reduction."""

    def test_reflect_reduces_physical(self):
        """Reflect reduces physical damage by 1/3 in doubles."""
        mods = DamageModifiers(is_doubles=True, reflect_up=True)
        mod = mods.get_screen_modifier(is_physical=True)
        assert mod == 2/3

    def test_light_screen_reduces_special(self):
        """Light Screen reduces special damage by 1/3 in doubles."""
        mods = DamageModifiers(is_doubles=True, light_screen_up=True)
        mod = mods.get_screen_modifier(is_physical=False)
        assert mod == 2/3

    def test_screens_singles(self):
        """Screens reduce damage by 1/2 in singles."""
        mods = DamageModifiers(is_doubles=False, reflect_up=True)
        mod = mods.get_screen_modifier(is_physical=True)
        assert mod == 0.5

    def test_crits_ignore_screens(self):
        """Critical hits ignore screens."""
        mods = DamageModifiers(is_doubles=True, reflect_up=True, is_critical=True)
        mod = mods.get_screen_modifier(is_physical=True)
        assert mod == 1.0


class TestStatDoublingAbilities:
    """Test abilities that double stats (Commander, Huge Power, Pure Power)."""

    def test_commander_doubles_attack(self):
        """Commander doubles Dondozo's attack stat."""
        # Dondozo base stats
        dondozo = PokemonBuild(
            name="dondozo",
            base_stats=BaseStats(
                hp=150, attack=100, defense=115,
                special_attack=65, special_defense=65, speed=35
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, hp=252),
            types=["Water"]
        )

        defender = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, defense=4),
            types=["Fire", "Dark"]
        )

        wave_crash = Move(
            name="wave-crash",
            type="Water",
            category=MoveCategory.PHYSICAL,
            power=120,
            accuracy=100,
            pp=10
        )

        # Without Commander
        mods_normal = DamageModifiers(commander_active=False)
        result_normal = calculate_damage(dondozo, defender, wave_crash, mods_normal)

        # With Commander
        mods_commander = DamageModifiers(commander_active=True)
        result_commander = calculate_damage(dondozo, defender, wave_crash, mods_commander)

        # Commander should do significantly more damage (roughly 2x attack stat)
        assert result_commander.max_damage > result_normal.max_damage
        # The damage ratio should be close to 2x
        ratio = result_commander.max_damage / result_normal.max_damage
        assert 1.9 <= ratio <= 2.1

    def test_commander_in_modifiers_list(self):
        """Commander should appear in applied modifiers list."""
        dondozo = PokemonBuild(
            name="dondozo",
            base_stats=BaseStats(
                hp=150, attack=100, defense=115,
                special_attack=65, special_defense=65, speed=35
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252),
            types=["Water"]
        )

        defender = PokemonBuild(
            name="pikachu",
            base_stats=BaseStats(
                hp=35, attack=55, defense=40,
                special_attack=50, special_defense=50, speed=90
            ),
            nature=Nature.TIMID,
            types=["Electric"]
        )

        wave_crash = Move(
            name="wave-crash",
            type="Water",
            category=MoveCategory.PHYSICAL,
            power=120,
            accuracy=100,
            pp=10
        )

        mods = DamageModifiers(commander_active=True)
        result = calculate_damage(dondozo, defender, wave_crash, mods)

        assert "Commander (2x all stats)" in result.details.get("modifiers_applied", [])

    def test_huge_power_doubles_physical_attack(self):
        """Huge Power doubles the attack stat for physical moves."""
        azumarill = PokemonBuild(
            name="azumarill",
            base_stats=BaseStats(
                hp=100, attack=50, defense=80,
                special_attack=60, special_defense=80, speed=50
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, hp=252),
            types=["Water", "Fairy"]
        )

        defender = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252),
            types=["Fire", "Dark"]
        )

        aqua_jet = Move(
            name="aqua-jet",
            type="Water",
            category=MoveCategory.PHYSICAL,
            power=40,
            accuracy=100,
            pp=20
        )

        # Without Huge Power
        mods_normal = DamageModifiers()
        result_normal = calculate_damage(azumarill, defender, aqua_jet, mods_normal)

        # With Huge Power
        mods_hp = DamageModifiers(attacker_ability="huge-power")
        result_hp = calculate_damage(azumarill, defender, aqua_jet, mods_hp)

        # Huge Power should do significantly more damage
        assert result_hp.max_damage > result_normal.max_damage
        ratio = result_hp.max_damage / result_normal.max_damage
        assert 1.9 <= ratio <= 2.1

    def test_pure_power_doubles_physical_attack(self):
        """Pure Power doubles the attack stat for physical moves."""
        medicham = PokemonBuild(
            name="medicham",
            base_stats=BaseStats(
                hp=60, attack=60, defense=75,
                special_attack=60, special_defense=75, speed=80
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Fighting", "Psychic"]
        )

        defender = PokemonBuild(
            name="tyranitar",
            base_stats=BaseStats(
                hp=100, attack=134, defense=110,
                special_attack=95, special_defense=100, speed=61
            ),
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252),
            types=["Rock", "Dark"]
        )

        high_jump_kick = Move(
            name="high-jump-kick",
            type="Fighting",
            category=MoveCategory.PHYSICAL,
            power=130,
            accuracy=90,
            pp=10
        )

        # Without Pure Power
        mods_normal = DamageModifiers()
        result_normal = calculate_damage(medicham, defender, high_jump_kick, mods_normal)

        # With Pure Power
        mods_pp = DamageModifiers(attacker_ability="pure-power")
        result_pp = calculate_damage(medicham, defender, high_jump_kick, mods_pp)

        # Pure Power should do significantly more damage
        assert result_pp.max_damage > result_normal.max_damage
        ratio = result_pp.max_damage / result_normal.max_damage
        assert 1.9 <= ratio <= 2.1

    def test_huge_power_does_not_affect_special(self):
        """Huge Power should not affect special moves."""
        azumarill = PokemonBuild(
            name="azumarill",
            base_stats=BaseStats(
                hp=100, attack=50, defense=80,
                special_attack=60, special_defense=80, speed=50
            ),
            nature=Nature.MODEST,
            evs=EVSpread(special_attack=252),
            types=["Water", "Fairy"]
        )

        defender = PokemonBuild(
            name="charizard",
            base_stats=BaseStats(
                hp=78, attack=84, defense=78,
                special_attack=109, special_defense=85, speed=100
            ),
            nature=Nature.TIMID,
            types=["Fire", "Flying"]
        )

        surf = Move(
            name="surf",
            type="Water",
            category=MoveCategory.SPECIAL,
            power=90,
            accuracy=100,
            pp=15
        )

        # Without Huge Power
        mods_normal = DamageModifiers()
        result_normal = calculate_damage(azumarill, defender, surf, mods_normal)

        # With Huge Power (shouldn't affect special moves)
        mods_hp = DamageModifiers(attacker_ability="huge-power")
        result_hp = calculate_damage(azumarill, defender, surf, mods_hp)

        # Damage should be the same since Huge Power only affects physical
        assert result_hp.max_damage == result_normal.max_damage


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
