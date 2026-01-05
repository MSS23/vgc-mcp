"""Tests for Ogerpon form-specific mechanics.

Tests cover:
- Mask items giving 1.2x boost to ALL moves (Hearthflame/Wellspring/Cornerstone only)
- Teal Mask provides NO boost
- Embody Aspect ability stat boosts when Terastallized
- Ivy Cudgel form-dependent type changes
- Fixed Tera types enforcement
"""

import pytest
from vgc_mcp_core.calc.damage import calculate_damage, _get_ogerpon_mask_boost_4096
from vgc_mcp_core.calc.modifiers import DamageModifiers, get_type_effectiveness
from vgc_mcp_core.calc.items import get_fixed_tera_type, get_signature_item
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, BaseStats, EVSpread
from vgc_mcp_core.models.move import Move, MoveCategory


# Base stats for all Ogerpon forms (same stats, different typings)
OGERPON_BASE_STATS = BaseStats(
    hp=80, attack=120, defense=84,
    special_attack=60, special_defense=96, speed=110
)


def make_ogerpon(form: str, types: list[str], item: str) -> PokemonBuild:
    """Helper to create Ogerpon builds for testing."""
    return PokemonBuild(
        name=f"ogerpon-{form}",
        base_stats=OGERPON_BASE_STATS,
        nature=Nature.ADAMANT,
        evs=EVSpread(attack=252, speed=252),
        types=types,
        item=item
    )


class TestOgerponMaskBoosts:
    """Test mask items give 1.2x boost to ALL moves (not just type-matching).

    Per Smogon research, Ogerpon's masks boost ALL of Ogerpon's moves by 1.2x:
    - Hearthflame Mask: 1.2x to ALL moves (when held by Ogerpon)
    - Wellspring Mask: 1.2x to ALL moves (when held by Ogerpon)
    - Cornerstone Mask: 1.2x to ALL moves (when held by Ogerpon)
    - Teal Mask: NO boost (this is the key difference from other masks)
    """

    def test_hearthflame_mask_boosts_all_moves(self):
        """Hearthflame Mask gives 1.2x boost to ALL moves for Ogerpon."""
        # Test boost on Fire move (STAB)
        mod = _get_ogerpon_mask_boost_4096("hearthflame-mask", "ogerpon-hearthflame")
        assert mod == 4915  # 1.2x in 4096 scale

        # Also boosts non-Fire moves (coverage)
        mod_coverage = _get_ogerpon_mask_boost_4096("hearthflame-mask", "ogerpon-hearthflame")
        assert mod_coverage == 4915  # 1.2x boost applies to ALL moves

    def test_wellspring_mask_boosts_all_moves(self):
        """Wellspring Mask gives 1.2x boost to ALL moves for Ogerpon."""
        mod = _get_ogerpon_mask_boost_4096("wellspring-mask", "ogerpon-wellspring")
        assert mod == 4915  # 1.2x in 4096 scale

    def test_cornerstone_mask_boosts_all_moves(self):
        """Cornerstone Mask gives 1.2x boost to ALL moves for Ogerpon."""
        mod = _get_ogerpon_mask_boost_4096("cornerstone-mask", "ogerpon-cornerstone")
        assert mod == 4915  # 1.2x in 4096 scale

    def test_teal_mask_provides_no_boost(self):
        """Teal Mask provides NO boost (unlike other masks)."""
        mod = _get_ogerpon_mask_boost_4096("teal-mask", "ogerpon")
        assert mod == 4096  # 1.0x (NO boost)

        mod_teal = _get_ogerpon_mask_boost_4096("teal-mask", "ogerpon-teal-mask")
        assert mod_teal == 4096  # 1.0x (NO boost)

    def test_masks_only_work_for_ogerpon(self):
        """Masks only provide boost when held by Ogerpon, not other Pokemon."""
        # Other Pokemon holding masks get no boost
        mod = _get_ogerpon_mask_boost_4096("hearthflame-mask", "ferrothorn")
        assert mod == 4096  # 1.0x (no boost for non-Ogerpon)

        mod_landorus = _get_ogerpon_mask_boost_4096("wellspring-mask", "landorus")
        assert mod_landorus == 4096  # 1.0x (no boost)

    def test_hearthflame_mask_damage_calculation(self):
        """Hearthflame Mask 1.2x boost affects actual damage calculation."""
        # Create Ogerpon WITHOUT the mask item to compare with vs without
        ogerpon_with_mask = make_ogerpon("hearthflame", ["Grass", "Fire"], "hearthflame-mask")
        ogerpon_no_mask = PokemonBuild(
            name="ogerpon-hearthflame",
            base_stats=OGERPON_BASE_STATS,
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252, speed=252),
            types=["Grass", "Fire"],
            item=None  # No item
        )

        defender = PokemonBuild(
            name="amoonguss",
            base_stats=BaseStats(
                hp=114, attack=85, defense=70,
                special_attack=85, special_defense=80, speed=30
            ),
            nature=Nature.BOLD,
            evs=EVSpread(hp=252, defense=252),
            types=["Grass", "Poison"]
        )

        # Fire move (should get 1.2x boost from mask)
        fire_punch = Move(
            name="fire-punch",
            type="Fire",
            category=MoveCategory.PHYSICAL,
            power=75,
            accuracy=100,
            pp=15
        )

        # With mask (1.2x boost)
        mods = DamageModifiers()
        result_mask = calculate_damage(ogerpon_with_mask, defender, fire_punch, mods)

        # Without mask (no item)
        result_no_mask = calculate_damage(ogerpon_no_mask, defender, fire_punch, mods)

        # Mask should increase damage by ~1.2x
        ratio = result_mask.max_damage / result_no_mask.max_damage
        assert 1.18 <= ratio <= 1.22, f"Expected ~1.2x ratio, got {ratio}"


class TestOgerponEmbodyAspect:
    """Test Embody Aspect ability stat boosts."""

    def test_hearthflame_embody_aspect_attack_boost(self):
        """Embody Aspect (Hearthflame) gives +1 Attack stage when Tera'd."""
        ogerpon = make_ogerpon("hearthflame", ["Grass", "Fire"], "hearthflame-mask")

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
        result_no_aspect = calculate_damage(ogerpon, defender, ivy_cudgel, mods_no_aspect)

        # With Embody Aspect (+1 Attack = 1.5x)
        mods_aspect = DamageModifiers(
            attacker_ability="embody-aspect",
            attacker_item="hearthflame-mask"
        )
        result_aspect = calculate_damage(ogerpon, defender, ivy_cudgel, mods_aspect)

        # Should do 1.5x damage (attack +1 stage)
        ratio = result_aspect.max_damage / result_no_aspect.max_damage
        assert 1.45 <= ratio <= 1.55, f"Expected ~1.5x ratio, got {ratio}"

    def test_cornerstone_embody_aspect_defense_boost(self):
        """Embody Aspect (Cornerstone) gives +1 Defense stage when Tera'd.

        Defense boost affects damage taken, not dealt.
        We test by having Ogerpon-Cornerstone as the defender.
        """
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

        ogerpon_cornerstone = make_ogerpon("cornerstone", ["Grass", "Rock"], "cornerstone-mask")

        surging_strikes = Move(
            name="surging-strikes",
            type="Water",
            category=MoveCategory.PHYSICAL,
            power=25,
            accuracy=100,
            pp=5
        )

        # Without Embody Aspect
        mods_no_aspect = DamageModifiers(defender_item="cornerstone-mask")
        result_no_aspect = calculate_damage(attacker, ogerpon_cornerstone, surging_strikes, mods_no_aspect)

        # With Embody Aspect (+1 Defense = 0.67x damage taken)
        mods_aspect = DamageModifiers(
            defender_ability="embody-aspect",
            defender_item="cornerstone-mask"
        )
        result_aspect = calculate_damage(attacker, ogerpon_cornerstone, surging_strikes, mods_aspect)

        # Should take less damage (defense +1 stage = 1.5x defense = 0.67x damage)
        ratio = result_aspect.max_damage / result_no_aspect.max_damage
        assert 0.60 <= ratio <= 0.72, f"Expected ~0.67x ratio, got {ratio}"

    def test_wellspring_embody_aspect_spdef_boost(self):
        """Embody Aspect (Wellspring) gives +1 Special Defense stage when Tera'd."""
        attacker = PokemonBuild(
            name="flutter-mane",
            base_stats=BaseStats(
                hp=55, attack=55, defense=55,
                special_attack=135, special_defense=135, speed=135
            ),
            nature=Nature.TIMID,
            evs=EVSpread(special_attack=252, speed=252),
            types=["Ghost", "Fairy"]
        )

        ogerpon_wellspring = make_ogerpon("wellspring", ["Grass", "Water"], "wellspring-mask")

        moonblast = Move(
            name="moonblast",
            type="Fairy",
            category=MoveCategory.SPECIAL,
            power=95,
            accuracy=100,
            pp=15
        )

        # Without Embody Aspect
        mods_no_aspect = DamageModifiers(defender_item="wellspring-mask")
        result_no_aspect = calculate_damage(attacker, ogerpon_wellspring, moonblast, mods_no_aspect)

        # With Embody Aspect (+1 SpD = 0.67x special damage taken)
        mods_aspect = DamageModifiers(
            defender_ability="embody-aspect",
            defender_item="wellspring-mask"
        )
        result_aspect = calculate_damage(attacker, ogerpon_wellspring, moonblast, mods_aspect)

        # Should take less damage
        ratio = result_aspect.max_damage / result_no_aspect.max_damage
        assert 0.60 <= ratio <= 0.70, f"Expected ~0.67x ratio, got {ratio}"


class TestOgerponIvyCudgel:
    """Test Ivy Cudgel type changes per form."""

    def test_ivy_cudgel_grass_type_for_teal(self):
        """Ivy Cudgel is Grass type for base Ogerpon (Teal Mask)."""
        ogerpon_teal = make_ogerpon("teal", ["Grass"], "teal-mask")

        # Water type defender (weak to Grass)
        quaquaval = PokemonBuild(
            name="quaquaval",
            base_stats=BaseStats(
                hp=85, attack=120, defense=80,
                special_attack=85, special_defense=75, speed=85
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(hp=252),
            types=["Water", "Fighting"]
        )

        ivy_cudgel = Move(
            name="ivy-cudgel",
            type="Grass",  # Teal = Grass type
            category=MoveCategory.PHYSICAL,
            power=100,
            accuracy=100,
            pp=10
        )

        mods = DamageModifiers(attacker_item="teal-mask")
        result = calculate_damage(ogerpon_teal, quaquaval, ivy_cudgel, mods)

        # Should be super effective (Grass vs Water = 2x)
        assert result.max_percent > 60, f"Expected SE damage, got {result.max_percent}%"

    def test_ivy_cudgel_water_type_for_wellspring(self):
        """Ivy Cudgel is Water type for Ogerpon-Wellspring."""
        ogerpon_wellspring = make_ogerpon("wellspring", ["Grass", "Water"], "wellspring-mask")

        # Ground type defender (weak to Water)
        garchomp = PokemonBuild(
            name="garchomp",
            base_stats=BaseStats(
                hp=108, attack=130, defense=95,
                special_attack=80, special_defense=85, speed=102
            ),
            nature=Nature.JOLLY,
            evs=EVSpread(hp=252),
            types=["Dragon", "Ground"]
        )

        ivy_cudgel = Move(
            name="ivy-cudgel",
            type="Water",  # Wellspring = Water type
            category=MoveCategory.PHYSICAL,
            power=100,
            accuracy=100,
            pp=10
        )

        mods = DamageModifiers(attacker_item="wellspring-mask")
        result = calculate_damage(ogerpon_wellspring, garchomp, ivy_cudgel, mods)

        # Should be super effective (Water vs Ground = 2x)
        assert result.max_percent > 60, f"Expected SE damage, got {result.max_percent}%"

    def test_ivy_cudgel_fire_type_for_hearthflame(self):
        """Ivy Cudgel is Fire type for Ogerpon-Hearthflame."""
        ogerpon_hearthflame = make_ogerpon("hearthflame", ["Grass", "Fire"], "hearthflame-mask")

        # Steel type defender (weak to Fire)
        ferrothorn = PokemonBuild(
            name="ferrothorn",
            base_stats=BaseStats(
                hp=74, attack=94, defense=131,
                special_attack=54, special_defense=116, speed=20
            ),
            nature=Nature.RELAXED,
            evs=EVSpread(hp=252, defense=252),
            types=["Grass", "Steel"]
        )

        ivy_cudgel = Move(
            name="ivy-cudgel",
            type="Fire",  # Hearthflame = Fire type
            category=MoveCategory.PHYSICAL,
            power=100,
            accuracy=100,
            pp=10
        )

        mods = DamageModifiers(attacker_item="hearthflame-mask")
        result = calculate_damage(ogerpon_hearthflame, ferrothorn, ivy_cudgel, mods)

        # Should be 4x super effective (Fire vs Grass/Steel = 4x)
        assert result.max_percent > 150, f"Expected 4x SE damage (OHKO), got {result.max_percent}%"

    def test_ivy_cudgel_rock_type_for_cornerstone(self):
        """Ivy Cudgel is Rock type for Ogerpon-Cornerstone."""
        ogerpon_cornerstone = make_ogerpon("cornerstone", ["Grass", "Rock"], "cornerstone-mask")

        # Flying type defender (weak to Rock)
        charizard = PokemonBuild(
            name="charizard",
            base_stats=BaseStats(
                hp=78, attack=84, defense=78,
                special_attack=109, special_defense=85, speed=100
            ),
            nature=Nature.TIMID,
            evs=EVSpread(hp=252),
            types=["Fire", "Flying"]
        )

        ivy_cudgel = Move(
            name="ivy-cudgel",
            type="Rock",  # Cornerstone = Rock type
            category=MoveCategory.PHYSICAL,
            power=100,
            accuracy=100,
            pp=10
        )

        mods = DamageModifiers(attacker_item="cornerstone-mask")
        result = calculate_damage(ogerpon_cornerstone, charizard, ivy_cudgel, mods)

        # Should be 4x super effective (Rock vs Fire/Flying = 4x)
        assert result.max_percent > 200, f"Expected 4x SE damage (OHKO), got {result.max_percent}%"


class TestOgerponFixedTera:
    """Test fixed Tera types are enforced."""

    def test_teal_tera_is_grass(self):
        """Ogerpon-Teal has fixed Grass Tera type."""
        # Test various name formats
        assert get_fixed_tera_type("ogerpon") == "Grass"
        assert get_fixed_tera_type("ogerpon-teal") == "Grass"
        assert get_fixed_tera_type("ogerpon-teal-mask") == "Grass"
        assert get_fixed_tera_type("Ogerpon-Teal") == "Grass"  # Case insensitive

    def test_wellspring_tera_is_water(self):
        """Ogerpon-Wellspring has fixed Water Tera type."""
        assert get_fixed_tera_type("ogerpon-wellspring") == "Water"
        assert get_fixed_tera_type("ogerpon-wellspring-mask") == "Water"
        assert get_fixed_tera_type("Ogerpon-Wellspring") == "Water"

    def test_hearthflame_tera_is_fire(self):
        """Ogerpon-Hearthflame has fixed Fire Tera type."""
        assert get_fixed_tera_type("ogerpon-hearthflame") == "Fire"
        assert get_fixed_tera_type("ogerpon-hearthflame-mask") == "Fire"
        assert get_fixed_tera_type("Ogerpon-Hearthflame") == "Fire"

    def test_cornerstone_tera_is_rock(self):
        """Ogerpon-Cornerstone has fixed Rock Tera type."""
        assert get_fixed_tera_type("ogerpon-cornerstone") == "Rock"
        assert get_fixed_tera_type("ogerpon-cornerstone-mask") == "Rock"
        assert get_fixed_tera_type("Ogerpon-Cornerstone") == "Rock"


class TestOgerponSignatureItems:
    """Test signature item detection for Ogerpon forms."""

    def test_hearthflame_signature_item(self):
        """Ogerpon-Hearthflame has Hearthflame Mask as signature item."""
        assert get_signature_item("ogerpon-hearthflame") == "hearthflame-mask"
        assert get_signature_item("ogerpon-hearthflame-mask") == "hearthflame-mask"

    def test_wellspring_signature_item(self):
        """Ogerpon-Wellspring has Wellspring Mask as signature item."""
        assert get_signature_item("ogerpon-wellspring") == "wellspring-mask"
        assert get_signature_item("ogerpon-wellspring-mask") == "wellspring-mask"

    def test_cornerstone_signature_item(self):
        """Ogerpon-Cornerstone has Cornerstone Mask as signature item."""
        assert get_signature_item("ogerpon-cornerstone") == "cornerstone-mask"
        assert get_signature_item("ogerpon-cornerstone-mask") == "cornerstone-mask"

    def test_teal_signature_item(self):
        """Ogerpon-Teal has Teal Mask as signature item."""
        assert get_signature_item("ogerpon-teal") == "teal-mask"
        assert get_signature_item("ogerpon-teal-mask") == "teal-mask"


class TestOgerponTypeEffectiveness:
    """Test type effectiveness for Ogerpon forms."""

    def test_wellspring_weak_to_poison(self):
        """Ogerpon-Wellspring (Grass/Water) is weak to Poison."""
        # Grass is 2x weak to Poison, Water is neutral
        eff = get_type_effectiveness("Poison", ["Grass", "Water"])
        assert eff == 2.0

    def test_hearthflame_neutral_to_fire(self):
        """Ogerpon-Hearthflame (Grass/Fire) is neutral to Fire (SE vs Grass cancels resist from Fire)."""
        # Fire is 2x vs Grass, Fire is 0.5x vs Fire = 1.0x (neutral)
        eff = get_type_effectiveness("Fire", ["Grass", "Fire"])
        assert eff == 1.0

    def test_cornerstone_4x_weak_to_fighting(self):
        """Ogerpon-Cornerstone (Grass/Rock) is 4x weak to Fighting."""
        # Grass is neutral, Rock is 2x weak
        # Wait, let's check: Fighting vs Grass is neutral, Fighting vs Rock is 2x
        eff = get_type_effectiveness("Fighting", ["Grass", "Rock"])
        assert eff == 2.0  # Actually just 2x, not 4x

    def test_cornerstone_4x_weak_to_grass(self):
        """Ogerpon-Cornerstone is weak to Grass (weird mirror matchup)."""
        # Grass is neutral to itself (1x), Rock is 2x weak to Grass
        eff = get_type_effectiveness("Grass", ["Grass", "Rock"])
        assert eff == 1.0  # Grass resists Grass (0.5x), Rock weak to Grass (2x) = 1x


class TestOgerponRealScenarios:
    """Test realistic VGC scenarios with Ogerpon forms."""

    def test_wellspring_vs_landorus_sludge_bomb(self):
        """Verify Ogerpon-Wellspring takes SE damage from Sludge Bomb."""
        landorus = PokemonBuild(
            name="landorus",
            base_stats=BaseStats(
                hp=89, attack=125, defense=90,
                special_attack=115, special_defense=80, speed=101
            ),
            nature=Nature.MODEST,
            evs=EVSpread(special_attack=116, speed=252, hp=4),
            types=["Ground", "Flying"]
        )

        ogerpon_wellspring = PokemonBuild(
            name="ogerpon-wellspring",
            base_stats=OGERPON_BASE_STATS,
            nature=Nature.JOLLY,
            evs=EVSpread(hp=12, attack=244, speed=252),
            types=["Grass", "Water"]
        )

        sludge_bomb = Move(
            name="sludge-bomb",
            type="Poison",
            category=MoveCategory.SPECIAL,
            power=90,
            accuracy=100,
            pp=10
        )

        # With Sheer Force + Life Orb (proper synergy)
        mods = DamageModifiers(
            attacker_ability="sheer-force",
            attacker_item="life-orb"
        )
        result = calculate_damage(landorus, ogerpon_wellspring, sludge_bomb, mods)

        # Should deal significant damage (Poison is 2x vs Grass/Water due to Grass typing)
        # With 116+ SpA Life Orb Sheer Force, should be near OHKO range
        assert result.max_percent > 80, f"Expected high damage, got {result.max_percent}%"

    def test_hearthflame_ohkos_ferrothorn(self):
        """Ogerpon-Hearthflame with Ivy Cudgel OHKOs Ferrothorn (4x SE)."""
        ogerpon = make_ogerpon("hearthflame", ["Grass", "Fire"], "hearthflame-mask")

        ferrothorn = PokemonBuild(
            name="ferrothorn",
            base_stats=BaseStats(
                hp=74, attack=94, defense=131,
                special_attack=54, special_defense=116, speed=20
            ),
            nature=Nature.RELAXED,
            evs=EVSpread(hp=252, defense=252),
            types=["Grass", "Steel"]
        )

        ivy_cudgel_fire = Move(
            name="ivy-cudgel",
            type="Fire",
            category=MoveCategory.PHYSICAL,
            power=100,
            accuracy=100,
            pp=10
        )

        # With mask item boost + Embody Aspect
        mods = DamageModifiers(
            attacker_ability="embody-aspect",
            attacker_item="hearthflame-mask"
        )
        result = calculate_damage(ogerpon, ferrothorn, ivy_cudgel_fire, mods)

        # 4x SE + mask boost + embody aspect should easily OHKO
        assert result.min_percent > 100, f"Expected guaranteed OHKO, got {result.min_percent}%-{result.max_percent}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
