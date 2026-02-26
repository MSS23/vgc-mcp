"""Tests for damage calculations."""

import pytest
from vgc_mcp_core.calc.damage import calculate_damage, _get_stab_mod_4096
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
        stab = _get_stab_mod_4096(attacker, fire_blast, mods)
        assert stab == 6144  # 1.5x in 4096 scale

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
        stab = _get_stab_mod_4096(attacker, solar_beam, mods)
        assert stab == 4096  # 1.0x in 4096 scale

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
        stab = _get_stab_mod_4096(attacker, fire_blast, mods)
        assert stab == 8192  # 2.0x in 4096 scale

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
        stab = _get_stab_mod_4096(attacker, solar_beam, mods)
        assert stab == 6144  # 1.5x in 4096 scale


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


class TestGen9Abilities:
    """Test Gen 9 VGC-critical abilities."""

    def test_rocky_payload_boosts_rock(self):
        """Rocky Payload gives 1.5x boost to Rock moves (Ogerpon-Cornerstone)."""
        ogerpon = PokemonBuild(
            name="ogerpon-cornerstone",
            base_stats=BaseStats(
                hp=80, attack=120, defense=84,
                special_attack=60, special_defense=96, speed=110
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Grass", "Rock"]
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

        stone_edge = Move(
            name="stone-edge",
            type="Rock",
            category=MoveCategory.PHYSICAL,
            power=100,
            accuracy=80,
            pp=5
        )

        # Without Rocky Payload
        mods_normal = DamageModifiers()
        result_normal = calculate_damage(ogerpon, defender, stone_edge, mods_normal)

        # With Rocky Payload
        mods_rocky = DamageModifiers(attacker_ability="rocky-payload")
        result_rocky = calculate_damage(ogerpon, defender, stone_edge, mods_rocky)

        # Rocky Payload should do ~1.5x damage
        assert result_rocky.max_damage > result_normal.max_damage
        ratio = result_rocky.max_damage / result_normal.max_damage
        assert 1.45 <= ratio <= 1.55

    def test_sharpness_boosts_slicing(self):
        """Sharpness gives 1.5x boost to slicing moves."""
        gallade = PokemonBuild(
            name="gallade",
            base_stats=BaseStats(
                hp=68, attack=125, defense=65,
                special_attack=65, special_defense=115, speed=80
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Psychic", "Fighting"]
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

        sacred_sword = Move(
            name="sacred-sword",
            type="Fighting",
            category=MoveCategory.PHYSICAL,
            power=90,
            accuracy=100,
            pp=15
        )

        # Without Sharpness
        mods_normal = DamageModifiers()
        result_normal = calculate_damage(gallade, defender, sacred_sword, mods_normal)

        # With Sharpness
        mods_sharp = DamageModifiers(attacker_ability="sharpness")
        result_sharp = calculate_damage(gallade, defender, sacred_sword, mods_sharp)

        # Sharpness should do ~1.5x damage
        assert result_sharp.max_damage > result_normal.max_damage
        ratio = result_sharp.max_damage / result_normal.max_damage
        assert 1.45 <= ratio <= 1.55

    def test_strong_jaw_boosts_biting(self):
        """Strong Jaw gives 1.5x boost to biting moves."""
        tyrantrum = PokemonBuild(
            name="tyrantrum",
            base_stats=BaseStats(
                hp=82, attack=121, defense=119,
                special_attack=69, special_defense=59, speed=71
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Rock", "Dragon"]
        )

        defender = PokemonBuild(
            name="garchomp",
            base_stats=BaseStats(
                hp=108, attack=130, defense=95,
                special_attack=80, special_defense=85, speed=102
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(hp=252),
            types=["Dragon", "Ground"]
        )

        crunch = Move(
            name="crunch",
            type="Dark",
            category=MoveCategory.PHYSICAL,
            power=80,
            accuracy=100,
            pp=15
        )

        # Without Strong Jaw
        mods_normal = DamageModifiers()
        result_normal = calculate_damage(tyrantrum, defender, crunch, mods_normal)

        # With Strong Jaw
        mods_jaw = DamageModifiers(attacker_ability="strong-jaw")
        result_jaw = calculate_damage(tyrantrum, defender, crunch, mods_jaw)

        # Strong Jaw should do ~1.5x damage
        assert result_jaw.max_damage > result_normal.max_damage
        ratio = result_jaw.max_damage / result_normal.max_damage
        assert 1.45 <= ratio <= 1.55

    def test_supreme_overlord_stacking(self):
        """Supreme Overlord gives +10% per fainted ally (Kingambit)."""
        kingambit = PokemonBuild(
            name="kingambit",
            base_stats=BaseStats(
                hp=100, attack=135, defense=120,
                special_attack=60, special_defense=85, speed=50
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, hp=252),
            types=["Dark", "Steel"]
        )

        defender = PokemonBuild(
            name="garchomp",
            base_stats=BaseStats(
                hp=108, attack=130, defense=95,
                special_attack=80, special_defense=85, speed=102
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(hp=252),
            types=["Dragon", "Ground"]
        )

        iron_head = Move(
            name="iron-head",
            type="Steel",
            category=MoveCategory.PHYSICAL,
            power=80,
            accuracy=100,
            pp=15
        )

        # Without Supreme Overlord (0 fainted)
        mods_0 = DamageModifiers(attacker_ability="supreme-overlord", supreme_overlord_count=0)
        result_0 = calculate_damage(kingambit, defender, iron_head, mods_0)

        # With 3 fainted allies (+30%)
        mods_3 = DamageModifiers(attacker_ability="supreme-overlord", supreme_overlord_count=3)
        result_3 = calculate_damage(kingambit, defender, iron_head, mods_3)

        # With 5 fainted allies (+50% max)
        mods_5 = DamageModifiers(attacker_ability="supreme-overlord", supreme_overlord_count=5)
        result_5 = calculate_damage(kingambit, defender, iron_head, mods_5)

        # 3 allies should do more than 0
        assert result_3.max_damage > result_0.max_damage
        ratio_3 = result_3.max_damage / result_0.max_damage
        assert 1.25 <= ratio_3 <= 1.35  # ~1.3x

        # 5 allies should do more than 3
        assert result_5.max_damage > result_3.max_damage
        ratio_5 = result_5.max_damage / result_0.max_damage
        assert 1.45 <= ratio_5 <= 1.55  # ~1.5x

    def test_orichalcum_pulse_in_sun(self):
        """Orichalcum Pulse gives 1.333x Attack in sun (Koraidon)."""
        koraidon = PokemonBuild(
            name="koraidon",
            base_stats=BaseStats(
                hp=100, attack=135, defense=115,
                special_attack=85, special_defense=100, speed=135
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Fighting", "Dragon"]
        )

        defender = PokemonBuild(
            name="iron-bundle",
            base_stats=BaseStats(
                hp=56, attack=80, defense=114,
                special_attack=124, special_defense=60, speed=136
            ),
            nature=Nature.TIMID,
            evs=EVSpread(hp=252),
            types=["Ice", "Water"]
        )

        close_combat = Move(
            name="close-combat",
            type="Fighting",
            category=MoveCategory.PHYSICAL,
            power=120,
            accuracy=100,
            pp=5
        )

        # Without sun
        mods_normal = DamageModifiers(attacker_ability="orichalcum-pulse")
        result_normal = calculate_damage(koraidon, defender, close_combat, mods_normal)

        # With sun
        mods_sun = DamageModifiers(attacker_ability="orichalcum-pulse", weather="sun")
        result_sun = calculate_damage(koraidon, defender, close_combat, mods_sun)

        # In sun, should do ~1.333x damage
        assert result_sun.max_damage > result_normal.max_damage
        ratio = result_sun.max_damage / result_normal.max_damage
        assert 1.28 <= ratio <= 1.38

    def test_hadron_engine_in_electric_terrain(self):
        """Hadron Engine gives 1.333x SpA in Electric Terrain (Miraidon)."""
        miraidon = PokemonBuild(
            name="miraidon",
            base_stats=BaseStats(
                hp=100, attack=85, defense=100,
                special_attack=135, special_defense=115, speed=135
            ),
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252),
            types=["Electric", "Dragon"]
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

        draco_meteor = Move(
            name="draco-meteor",
            type="Dragon",
            category=MoveCategory.SPECIAL,
            power=130,
            accuracy=90,
            pp=5
        )

        # Without terrain
        mods_normal = DamageModifiers(attacker_ability="hadron-engine")
        result_normal = calculate_damage(miraidon, defender, draco_meteor, mods_normal)

        # With Electric Terrain
        mods_terrain = DamageModifiers(attacker_ability="hadron-engine", terrain="electric")
        result_terrain = calculate_damage(miraidon, defender, draco_meteor, mods_terrain)

        # In terrain, should do ~1.333x damage
        assert result_terrain.max_damage > result_normal.max_damage
        ratio = result_terrain.max_damage / result_normal.max_damage
        assert 1.28 <= ratio <= 1.38


class TestGen9DefenderAbilities:
    """Test Gen 9 defender abilities."""

    def test_tera_shell_at_full_hp(self):
        """Tera Shell makes all hits not very effective at full HP (Terapagos)."""
        attacker = PokemonBuild(
            name="urshifu",
            base_stats=BaseStats(
                hp=100, attack=130, defense=100,
                special_attack=63, special_defense=60, speed=97
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Fighting", "Water"]
        )

        terapagos = PokemonBuild(
            name="terapagos",
            base_stats=BaseStats(
                hp=90, attack=65, defense=85,
                special_attack=120, special_defense=105, speed=85
            ),
            nature=Nature.CALM,
            evs=EVSpread(hp=252, special_defense=252),
            types=["Normal"]
        )

        close_combat = Move(
            name="close-combat",
            type="Fighting",
            category=MoveCategory.PHYSICAL,
            power=120,
            accuracy=100,
            pp=5
        )

        # Without Tera Shell (super effective)
        mods_normal = DamageModifiers(defender_at_full_hp=True)
        result_normal = calculate_damage(attacker, terapagos, close_combat, mods_normal)

        # With Tera Shell at full HP (forced 0.5x)
        mods_shell = DamageModifiers(defender_ability="tera-shell", defender_at_full_hp=True)
        result_shell = calculate_damage(attacker, terapagos, close_combat, mods_shell)

        # Tera Shell should reduce damage significantly (2x SE -> 0.5x NVE = 4x reduction)
        assert result_shell.max_damage < result_normal.max_damage
        ratio = result_shell.max_damage / result_normal.max_damage
        assert 0.2 <= ratio <= 0.3  # ~0.25x (2x -> 0.5x)

    def test_tera_shell_not_at_full_hp(self):
        """Tera Shell doesn't work when not at full HP."""
        attacker = PokemonBuild(
            name="urshifu",
            base_stats=BaseStats(
                hp=100, attack=130, defense=100,
                special_attack=63, special_defense=60, speed=97
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Fighting", "Water"]
        )

        terapagos = PokemonBuild(
            name="terapagos",
            base_stats=BaseStats(
                hp=90, attack=65, defense=85,
                special_attack=120, special_defense=105, speed=85
            ),
            nature=Nature.CALM,
            evs=EVSpread(hp=252, special_defense=252),
            types=["Normal"]
        )

        close_combat = Move(
            name="close-combat",
            type="Fighting",
            category=MoveCategory.PHYSICAL,
            power=120,
            accuracy=100,
            pp=5
        )

        # Without Tera Shell (super effective)
        mods_normal = DamageModifiers(defender_at_full_hp=False)
        result_normal = calculate_damage(attacker, terapagos, close_combat, mods_normal)

        # With Tera Shell but NOT at full HP (should not activate)
        mods_shell = DamageModifiers(defender_ability="tera-shell", defender_at_full_hp=False)
        result_shell = calculate_damage(attacker, terapagos, close_combat, mods_shell)

        # Damage should be the same
        assert result_shell.max_damage == result_normal.max_damage

    def test_purifying_salt_halves_ghost(self):
        """Purifying Salt halves Ghost damage (Garganacl)."""
        attacker = PokemonBuild(
            name="dragapult",
            base_stats=BaseStats(
                hp=88, attack=120, defense=75,
                special_attack=100, special_defense=75, speed=142
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Dragon", "Ghost"]
        )

        garganacl = PokemonBuild(
            name="garganacl",
            base_stats=BaseStats(
                hp=100, attack=100, defense=130,
                special_attack=45, special_defense=90, speed=35
            ),
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, special_defense=252),
            types=["Rock"]
        )

        phantom_force = Move(
            name="phantom-force",
            type="Ghost",
            category=MoveCategory.PHYSICAL,
            power=90,
            accuracy=100,
            pp=10
        )

        # Without Purifying Salt
        mods_normal = DamageModifiers()
        result_normal = calculate_damage(attacker, garganacl, phantom_force, mods_normal)

        # With Purifying Salt
        mods_salt = DamageModifiers(defender_ability="purifying-salt")
        result_salt = calculate_damage(attacker, garganacl, phantom_force, mods_salt)

        # Purifying Salt should halve damage
        assert result_salt.max_damage < result_normal.max_damage
        ratio = result_salt.max_damage / result_normal.max_damage
        assert 0.48 <= ratio <= 0.52


class TestGen9Items:
    """Test Gen 9 VGC items."""

    def test_punching_glove_boosts_punch(self):
        """Punching Glove gives 1.1x boost to punch moves."""
        iron_hands = PokemonBuild(
            name="iron-hands",
            base_stats=BaseStats(
                hp=154, attack=140, defense=108,
                special_attack=50, special_defense=68, speed=50
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, hp=252),
            types=["Fighting", "Electric"]
        )

        defender = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, defense=252),
            types=["Fire", "Dark"]
        )

        drain_punch = Move(
            name="drain-punch",
            type="Fighting",
            category=MoveCategory.PHYSICAL,
            power=75,
            accuracy=100,
            pp=10
        )

        # Without Punching Glove
        mods_normal = DamageModifiers()
        result_normal = calculate_damage(iron_hands, defender, drain_punch, mods_normal)

        # With Punching Glove
        mods_glove = DamageModifiers(attacker_item="punching-glove")
        result_glove = calculate_damage(iron_hands, defender, drain_punch, mods_glove)

        # Punching Glove should do ~1.1x damage
        assert result_glove.max_damage > result_normal.max_damage
        ratio = result_glove.max_damage / result_normal.max_damage
        assert 1.08 <= ratio <= 1.12

    def test_punching_glove_no_boost_non_punch(self):
        """Punching Glove doesn't boost non-punch moves."""
        iron_hands = PokemonBuild(
            name="iron-hands",
            base_stats=BaseStats(
                hp=154, attack=140, defense=108,
                special_attack=50, special_defense=68, speed=50
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, hp=252),
            types=["Fighting", "Electric"]
        )

        defender = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, defense=252),
            types=["Fire", "Dark"]
        )

        wild_charge = Move(
            name="wild-charge",
            type="Electric",
            category=MoveCategory.PHYSICAL,
            power=90,
            accuracy=100,
            pp=15
        )

        # Without Punching Glove
        mods_normal = DamageModifiers()
        result_normal = calculate_damage(iron_hands, defender, wild_charge, mods_normal)

        # With Punching Glove (shouldn't boost non-punch)
        mods_glove = DamageModifiers(attacker_item="punching-glove")
        result_glove = calculate_damage(iron_hands, defender, wild_charge, mods_glove)

        # Damage should be the same
        assert result_glove.max_damage == result_normal.max_damage


class TestStellarType:
    """Test Stellar Tera type mechanics."""

    def test_stellar_type_in_chart(self):
        """Stellar type exists and is neutral defensively."""
        # Stellar should be neutral to all types
        eff = get_type_effectiveness("Fire", ["Stellar"])
        assert eff == 1.0

        eff = get_type_effectiveness("Dragon", ["Stellar"])
        assert eff == 1.0

    def test_stellar_offensive_vs_tera(self):
        """Stellar Tera deals 2x damage to Terastallized Pokemon."""
        eff = get_type_effectiveness(
            "Fire",
            ["Water"],  # Defender types
            tera_type="Water",  # Defender is Tera Water
            attacker_tera_stellar=True  # Attacker is Tera Stellar
        )
        assert eff == 2.0


class TestTeraBlast:
    """Test Tera Blast type and category changes."""

    def test_tera_blast_type_change(self):
        """Tera Blast becomes the attacker's Tera type when Terastallized."""
        flutter_mane = PokemonBuild(
            name="flutter-mane",
            base_stats=BaseStats(
                hp=55, attack=55, defense=55,
                special_attack=135, special_defense=135, speed=135
            ),
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252),
            types=["Ghost", "Fairy"]
        )

        # Ice type defender (weak to Fire)
        avalugg = PokemonBuild(
            name="avalugg",
            base_stats=BaseStats(
                hp=95, attack=117, defense=184,
                special_attack=44, special_defense=46, speed=28
            ),
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, special_defense=252),
            types=["Ice"]
        )

        tera_blast = Move(
            name="tera-blast",
            type="Normal",
            category=MoveCategory.SPECIAL,
            power=80,
            accuracy=100,
            pp=10
        )

        # Without Tera - Normal type (not very effective vs Ice? No, neutral)
        mods_no_tera = DamageModifiers()
        result_no_tera = calculate_damage(flutter_mane, avalugg, tera_blast, mods_no_tera)

        # With Fire Tera - Fire type (super effective vs Ice)
        mods_fire_tera = DamageModifiers(
            tera_active=True,
            tera_type="Fire"
        )
        result_fire_tera = calculate_damage(flutter_mane, avalugg, tera_blast, mods_fire_tera)

        # Fire Tera Blast should do more damage (super effective)
        assert result_fire_tera.max_damage > result_no_tera.max_damage

    def test_tera_blast_physical_when_atk_higher(self):
        """Tera Blast becomes physical when Attack > Special Attack."""
        # Physical attacker with higher Attack than SpA
        ursaluna = PokemonBuild(
            name="ursaluna",
            base_stats=BaseStats(
                hp=130, attack=140, defense=105,
                special_attack=45, special_defense=80, speed=50
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, hp=252),
            types=["Ground", "Normal"]
        )

        # High Def, low SpD - damage will be higher if attack targets special defense
        chansey = PokemonBuild(
            name="chansey",
            base_stats=BaseStats(
                hp=250, attack=5, defense=5,
                special_attack=35, special_defense=105, speed=50
            ),
            nature=Nature.BOLD,
            evs=EVSpread(defense=252, special_defense=4),
            types=["Normal"]
        )

        tera_blast = Move(
            name="tera-blast",
            type="Normal",
            category=MoveCategory.SPECIAL,  # Default is special
            power=80,
            accuracy=100,
            pp=10
        )

        # With Tera active, Tera Blast should become physical (Atk > SpA)
        mods_tera = DamageModifiers(
            tera_active=True,
            tera_type="Ground"
        )
        result = calculate_damage(ursaluna, chansey, tera_blast, mods_tera)

        # High damage expected because physical attacks target Chansey's terrible 5 base Def
        # If it were special, it would target the 105 SpD
        assert result.max_damage > 100  # Should do significant damage


class TestMindsEye:
    """Test Mind's Eye Ghost immunity bypass."""

    def test_minds_eye_hits_ghost_with_normal(self):
        """Mind's Eye allows Normal moves to hit Ghost types."""
        ursaluna_bloodmoon = PokemonBuild(
            name="ursaluna-bloodmoon",
            base_stats=BaseStats(
                hp=113, attack=70, defense=120,
                special_attack=135, special_defense=65, speed=52
            ),
            nature=Nature.MODEST,
            evs=EVSpread(special_attack=252, hp=252),
            types=["Ground", "Normal"]
        )

        gengar = PokemonBuild(
            name="gengar",
            base_stats=BaseStats(
                hp=60, attack=65, defense=60,
                special_attack=130, special_defense=75, speed=110
            ),
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252),
            types=["Ghost", "Poison"]
        )

        hyper_voice = Move(
            name="hyper-voice",
            type="Normal",
            category=MoveCategory.SPECIAL,
            power=90,
            accuracy=100,
            pp=10
        )

        # Without Mind's Eye - immune
        mods_no_ability = DamageModifiers()
        result_no_ability = calculate_damage(ursaluna_bloodmoon, gengar, hyper_voice, mods_no_ability)
        assert result_no_ability.max_damage == 0

        # With Mind's Eye - should hit
        mods_minds_eye = DamageModifiers(attacker_ability="minds-eye")
        result_minds_eye = calculate_damage(ursaluna_bloodmoon, gengar, hyper_voice, mods_minds_eye)
        assert result_minds_eye.max_damage > 0


class TestEmbodyAspect:
    """Test Embody Aspect stat boosts for Ogerpon masks."""

    def test_hearthflame_attack_boost(self):
        """Hearthflame Mask Ogerpon gets Attack boost from Embody Aspect."""
        ogerpon_hearthflame = PokemonBuild(
            name="ogerpon-hearthflame",
            base_stats=BaseStats(
                hp=80, attack=120, defense=84,
                special_attack=60, special_defense=96, speed=110
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Grass", "Fire"]
        )

        defender = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, defense=252),
            types=["Fire", "Dark"]
        )

        ivy_cudgel = Move(
            name="ivy-cudgel",
            type="Fire",  # Hearthflame type
            category=MoveCategory.PHYSICAL,
            power=100,
            accuracy=100,
            pp=10
        )

        # Without Embody Aspect
        mods_no_aspect = DamageModifiers(attacker_item="hearthflame-mask")
        result_no_aspect = calculate_damage(ogerpon_hearthflame, defender, ivy_cudgel, mods_no_aspect)

        # With Embody Aspect (+1 Attack = 1.5x)
        mods_aspect = DamageModifiers(
            attacker_ability="embody-aspect",
            attacker_item="hearthflame-mask"
        )
        result_aspect = calculate_damage(ogerpon_hearthflame, defender, ivy_cudgel, mods_aspect)

        # Should do 1.5x damage
        assert result_aspect.max_damage > result_no_aspect.max_damage
        ratio = result_aspect.max_damage / result_no_aspect.max_damage
        assert 1.4 <= ratio <= 1.55


class TestIvyCudgel:
    """Test Ivy Cudgel form-dependent type changes."""

    def test_ivy_cudgel_hearthflame_fire(self):
        """Ivy Cudgel is Fire type for Ogerpon-Hearthflame."""
        ogerpon_hearthflame = PokemonBuild(
            name="ogerpon-hearthflame",
            base_stats=BaseStats(
                hp=80, attack=120, defense=84,
                special_attack=60, special_defense=96, speed=110
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Grass", "Fire"]
        )

        # Grass defender (weak to Fire, resists Grass)
        venusaur = PokemonBuild(
            name="venusaur",
            base_stats=BaseStats(
                hp=80, attack=82, defense=83,
                special_attack=100, special_defense=100, speed=80
            ),
            nature=Nature.CALM,
            evs=EVSpread(hp=252, special_defense=252),
            types=["Grass", "Poison"]
        )

        # Ivy Cudgel base type is Grass, but should become Fire for Hearthflame
        ivy_cudgel = Move(
            name="ivy-cudgel",
            type="Grass",  # Base type
            category=MoveCategory.PHYSICAL,
            power=100,
            accuracy=100,
            pp=10
        )

        mods = DamageModifiers()
        result = calculate_damage(ogerpon_hearthflame, venusaur, ivy_cudgel, mods)

        # Should do super effective damage (Fire vs Grass)
        # If it stayed Grass type, it would be not very effective
        assert result.max_percent > 40  # Significant damage expected


class TestPsyblade:
    """Test Psyblade Psychic Terrain boost."""

    def test_psyblade_terrain_boost(self):
        """Psyblade gets 1.5x in Psychic Terrain (not the standard 1.3x)."""
        iron_valiant = PokemonBuild(
            name="iron-valiant",
            base_stats=BaseStats(
                hp=74, attack=130, defense=90,
                special_attack=120, special_defense=60, speed=116
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Fairy", "Fighting"]
        )

        # Use a Pokemon that isn't immune to Psychic (not Dark type)
        defender = PokemonBuild(
            name="garchomp",
            base_stats=BaseStats(
                hp=108, attack=130, defense=95,
                special_attack=80, special_defense=85, speed=102
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(hp=252, defense=252),
            types=["Dragon", "Ground"]
        )

        psyblade = Move(
            name="psyblade",
            type="Psychic",
            category=MoveCategory.PHYSICAL,
            power=80,
            accuracy=100,
            pp=15
        )

        # Without terrain
        mods_no_terrain = DamageModifiers()
        result_no_terrain = calculate_damage(iron_valiant, defender, psyblade, mods_no_terrain)

        # With Psychic Terrain (should get 1.5x boost)
        mods_terrain = DamageModifiers(terrain="psychic")
        result_terrain = calculate_damage(iron_valiant, defender, psyblade, mods_terrain)

        # Should do 1.5x damage
        assert result_terrain.max_damage > result_no_terrain.max_damage
        ratio = result_terrain.max_damage / result_no_terrain.max_damage
        assert 1.45 <= ratio <= 1.55


class TestAutoFillFromBuild:
    """Test that item and ability are auto-filled from PokemonBuild."""

    def test_ability_auto_filled_from_build(self):
        """Ability from PokemonBuild should be auto-applied when modifiers don't specify it."""
        # Landorus-I with Sheer Force
        lando_base = BaseStats(
            hp=89, attack=125, defense=90,
            special_attack=115, special_defense=80, speed=101
        )

        lando_with_sf = PokemonBuild(
            name="landorus-incarnate",
            base_stats=lando_base,
            types=["Ground", "Flying"],
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252),
            ability="sheer-force"
        )

        lando_no_ability = PokemonBuild(
            name="landorus-incarnate",
            base_stats=lando_base,
            types=["Ground", "Flying"],
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252)
        )

        defender = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            types=["Fire", "Dark"],
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, special_defense=252)
        )

        # Sludge Bomb has effect_chance so Sheer Force applies
        sludge_bomb = Move(
            name="sludge-bomb",
            type="Poison",
            category=MoveCategory.SPECIAL,
            power=90,
            accuracy=100,
            pp=10,
            effect_chance=30
        )

        # Empty modifiers - should auto-fill ability from build
        mods = DamageModifiers()

        result_with_sf = calculate_damage(lando_with_sf, defender, sludge_bomb, mods)
        result_no_sf = calculate_damage(lando_no_ability, defender, sludge_bomb, mods)

        # Sheer Force should boost damage by 1.3x
        ratio = result_with_sf.max_damage / result_no_sf.max_damage
        assert 1.25 <= ratio <= 1.35, f"Expected ~1.3x ratio, got {ratio}"

    def test_item_auto_filled_from_build(self):
        """Item from PokemonBuild should be auto-applied when modifiers don't specify it."""
        flutter_base = BaseStats(
            hp=55, attack=55, defense=55,
            special_attack=135, special_defense=135, speed=135
        )

        flutter_with_lo = PokemonBuild(
            name="flutter-mane",
            base_stats=flutter_base,
            types=["Ghost", "Fairy"],
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252),
            item="life-orb"
        )

        flutter_no_item = PokemonBuild(
            name="flutter-mane",
            base_stats=flutter_base,
            types=["Ghost", "Fairy"],
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252)
        )

        defender = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            types=["Fire", "Dark"],
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, special_defense=252)
        )

        moonblast = Move(
            name="moonblast",
            type="Fairy",
            category=MoveCategory.SPECIAL,
            power=95,
            accuracy=100,
            pp=15
        )

        mods = DamageModifiers()

        result_with_lo = calculate_damage(flutter_with_lo, defender, moonblast, mods)
        result_no_lo = calculate_damage(flutter_no_item, defender, moonblast, mods)

        # Life Orb should boost damage by 1.3x
        ratio = result_with_lo.max_damage / result_no_lo.max_damage
        assert 1.25 <= ratio <= 1.35, f"Expected ~1.3x ratio, got {ratio}"

    def test_item_and_ability_both_auto_filled(self):
        """Both item and ability should be auto-filled together."""
        lando_base = BaseStats(
            hp=89, attack=125, defense=90,
            special_attack=115, special_defense=80, speed=101
        )

        lando_full = PokemonBuild(
            name="landorus-incarnate",
            base_stats=lando_base,
            types=["Ground", "Flying"],
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252),
            item="life-orb",
            ability="sheer-force"
        )

        lando_empty = PokemonBuild(
            name="landorus-incarnate",
            base_stats=lando_base,
            types=["Ground", "Flying"],
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252)
        )

        defender = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            types=["Fire", "Dark"],
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, special_defense=252)
        )

        sludge_bomb = Move(
            name="sludge-bomb",
            type="Poison",
            category=MoveCategory.SPECIAL,
            power=90,
            accuracy=100,
            pp=10,
            effect_chance=30
        )

        mods = DamageModifiers()

        result_full = calculate_damage(lando_full, defender, sludge_bomb, mods)
        result_empty = calculate_damage(lando_empty, defender, sludge_bomb, mods)

        # Both SF (1.3x) and Life Orb (1.3x) should boost = ~1.69x
        ratio = result_full.max_damage / result_empty.max_damage
        assert 1.60 <= ratio <= 1.75, f"Expected ~1.69x ratio, got {ratio}"

    def test_always_crit_does_not_mutate_modifiers(self):
        """Verify that always-crit moves don't mutate original modifiers (Bug #1 fix)."""
        # Create modifiers with is_critical=False
        modifiers = DamageModifiers(is_critical=False)
        original_crit_status = modifiers.is_critical

        # Create Urshifu and Ogerpon builds
        urshifu = PokemonBuild(
            name="urshifu-rapid-strike",
            base_stats=BaseStats(
                hp=100, attack=130, defense=100,
                special_attack=63, special_defense=60, speed=97
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(attack=252),
            types=["Fighting", "Water"],
            ability="unseen-fist"
        )

        ogerpon = PokemonBuild(
            name="ogerpon",
            base_stats=BaseStats(
                hp=80, attack=120, defense=84,
                special_attack=60, special_defense=96, speed=110
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(hp=252),
            types=["Grass"]
        )

        # Surging Strikes always crits
        surging_strikes = Move(
            name="surging-strikes",
            type="Water",
            category=MoveCategory.PHYSICAL,
            power=25,
            accuracy=100,
            pp=5
        )

        # Calculate damage - this triggers the always_crit logic
        result = calculate_damage(urshifu, ogerpon, surging_strikes, modifiers)

        # Original modifiers should be unchanged (not mutated)
        assert modifiers.is_critical == original_crit_status, (
            "Modifiers were mutated! always_crit should create new modifiers, not mutate original"
        )


class TestSwordOfRuinWithCrits:
    """Sword of Ruin is a field effect, NOT a stat stage.
    It must always apply even on critical hits."""

    def _make_urshifu(self):
        return PokemonBuild(
            name="urshifu-rapid-strike",
            base_stats=BaseStats(
                hp=100, attack=130, defense=100,
                special_attack=63, special_defense=60, speed=97
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252, hp=4),
            types=["Fighting", "Water"],
            ability="unseen-fist"
        )

    def _make_ogerpon(self):
        return PokemonBuild(
            name="ogerpon-hearthflame",
            base_stats=BaseStats(
                hp=80, attack=120, defense=84,
                special_attack=60, special_defense=96, speed=110
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(hp=252, speed=252, defense=4),
            types=["Grass", "Fire"]
        )

    def _make_surging_strikes(self):
        return Move(
            name="surging-strikes",
            type="Water",
            category=MoveCategory.PHYSICAL,
            power=25,
            accuracy=100,
            pp=5,
        )

    def test_sword_of_ruin_applies_on_always_crit_moves(self):
        """Sword of Ruin defense reduction must apply even when move always crits."""
        urshifu = self._make_urshifu()
        ogerpon = self._make_ogerpon()
        surging_strikes = self._make_surging_strikes()

        result_no_ruin = calculate_damage(
            urshifu, ogerpon, surging_strikes,
            DamageModifiers(is_doubles=True, sword_of_ruin=False)
        )
        result_with_ruin = calculate_damage(
            urshifu, ogerpon, surging_strikes,
            DamageModifiers(is_doubles=True, sword_of_ruin=True)
        )

        # Sword of Ruin should increase damage (0.75x defense = ~1.33x damage)
        assert result_with_ruin.max_damage > result_no_ruin.max_damage, (
            "Sword of Ruin must increase damage even on always-crit moves like Surging Strikes"
        )

    def test_sword_of_ruin_auto_detected_from_attacker_ability(self):
        """Sword of Ruin should be auto-detected from the attacker's ability name."""
        chien_pao = PokemonBuild(
            name="chien-pao",
            base_stats=BaseStats(
                hp=80, attack=120, defense=80,
                special_attack=90, special_defense=65, speed=135
            ),
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252, hp=4),
            types=["Dark", "Ice"],
            ability="sword-of-ruin"
        )
        ogerpon = self._make_ogerpon()
        icicle_crash = Move(
            name="icicle-crash", type="Ice",
            category=MoveCategory.PHYSICAL, power=85, accuracy=90, pp=10
        )

        # No explicit flag — should auto-detect from ability
        result_auto = calculate_damage(
            chien_pao, ogerpon, icicle_crash,
            DamageModifiers(is_doubles=True)
        )
        result_explicit = calculate_damage(
            chien_pao, ogerpon, icicle_crash,
            DamageModifiers(is_doubles=True, sword_of_ruin=True)
        )

        assert result_auto.max_damage == result_explicit.max_damage, (
            "Auto-detected Sword of Ruin should match explicitly set flag"
        )

    def test_beads_of_ruin_auto_detected_from_attacker_ability(self):
        """Beads of Ruin should be auto-detected from the attacker's ability name."""
        chi_yu = PokemonBuild(
            name="chi-yu",
            base_stats=BaseStats(
                hp=55, attack=80, defense=80,
                special_attack=135, special_defense=120, speed=100
            ),
            nature=Nature.MODEST,
            evs=EVSpread(special_attack=252, speed=252, hp=4),
            types=["Dark", "Fire"],
            ability="beads-of-ruin"
        )
        ogerpon = self._make_ogerpon()
        heat_wave = Move(
            name="heat-wave", type="Fire",
            category=MoveCategory.SPECIAL, power=95, accuracy=90, pp=10,
            target="all-other-pokemon"
        )

        result_auto = calculate_damage(
            chi_yu, ogerpon, heat_wave,
            DamageModifiers(is_doubles=True)
        )
        result_explicit = calculate_damage(
            chi_yu, ogerpon, heat_wave,
            DamageModifiers(is_doubles=True, beads_of_ruin=True)
        )

        assert result_auto.max_damage == result_explicit.max_damage, (
            "Auto-detected Beads of Ruin should match explicitly set flag"
        )

    def test_tablets_of_ruin_auto_detected_from_defender_ability(self):
        """Tablets of Ruin should be auto-detected from the defender's ability name."""
        urshifu = self._make_urshifu()
        wo_chien = PokemonBuild(
            name="wo-chien",
            base_stats=BaseStats(
                hp=85, attack=85, defense=100,
                special_attack=95, special_defense=135, speed=70
            ),
            nature=Nature.BOLD,
            evs=EVSpread(hp=252, defense=252, special_defense=4),
            types=["Dark", "Grass"],
            ability="tablets-of-ruin"
        )
        close_combat = Move(
            name="close-combat", type="Fighting",
            category=MoveCategory.PHYSICAL, power=120, accuracy=100, pp=5
        )

        result_auto = calculate_damage(
            urshifu, wo_chien, close_combat,
            DamageModifiers(is_doubles=True)
        )
        result_explicit = calculate_damage(
            urshifu, wo_chien, close_combat,
            DamageModifiers(is_doubles=True, tablets_of_ruin=True)
        )

        assert result_auto.max_damage == result_explicit.max_damage, (
            "Auto-detected Tablets of Ruin should match explicitly set flag"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
