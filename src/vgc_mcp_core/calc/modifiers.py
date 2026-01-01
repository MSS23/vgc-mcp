"""Damage modifiers including type effectiveness, weather, terrain, etc."""

from dataclasses import dataclass, field
from typing import Optional


# Complete Gen 9 Type Chart
# Key = attacking type, Value = dict of defending type -> multiplier
TYPE_CHART: dict[str, dict[str, float]] = {
    "Normal": {
        "Rock": 0.5, "Ghost": 0, "Steel": 0.5
    },
    "Fire": {
        "Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 2, "Bug": 2,
        "Rock": 0.5, "Dragon": 0.5, "Steel": 2
    },
    "Water": {
        "Fire": 2, "Water": 0.5, "Grass": 0.5, "Ground": 2, "Rock": 2, "Dragon": 0.5
    },
    "Electric": {
        "Water": 2, "Electric": 0.5, "Grass": 0.5, "Ground": 0,
        "Flying": 2, "Dragon": 0.5
    },
    "Grass": {
        "Fire": 0.5, "Water": 2, "Grass": 0.5, "Poison": 0.5, "Ground": 2,
        "Flying": 0.5, "Bug": 0.5, "Rock": 2, "Dragon": 0.5, "Steel": 0.5
    },
    "Ice": {
        "Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 0.5, "Ground": 2,
        "Flying": 2, "Dragon": 2, "Steel": 0.5
    },
    "Fighting": {
        "Normal": 2, "Ice": 2, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5,
        "Bug": 0.5, "Rock": 2, "Ghost": 0, "Dark": 2, "Steel": 2, "Fairy": 0.5
    },
    "Poison": {
        "Grass": 2, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5,
        "Ghost": 0.5, "Steel": 0, "Fairy": 2
    },
    "Ground": {
        "Fire": 2, "Electric": 2, "Grass": 0.5, "Poison": 2,
        "Flying": 0, "Bug": 0.5, "Rock": 2, "Steel": 2
    },
    "Flying": {
        "Electric": 0.5, "Grass": 2, "Fighting": 2, "Bug": 2,
        "Rock": 0.5, "Steel": 0.5
    },
    "Psychic": {
        "Fighting": 2, "Poison": 2, "Psychic": 0.5, "Dark": 0, "Steel": 0.5
    },
    "Bug": {
        "Fire": 0.5, "Grass": 2, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5,
        "Psychic": 2, "Ghost": 0.5, "Dark": 2, "Steel": 0.5, "Fairy": 0.5
    },
    "Rock": {
        "Fire": 2, "Ice": 2, "Fighting": 0.5, "Ground": 0.5,
        "Flying": 2, "Bug": 2, "Steel": 0.5
    },
    "Ghost": {
        "Normal": 0, "Psychic": 2, "Ghost": 2, "Dark": 0.5
    },
    "Dragon": {
        "Dragon": 2, "Steel": 0.5, "Fairy": 0
    },
    "Dark": {
        "Fighting": 0.5, "Psychic": 2, "Ghost": 2, "Dark": 0.5, "Fairy": 0.5
    },
    "Steel": {
        "Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2,
        "Rock": 2, "Steel": 0.5, "Fairy": 2
    },
    "Fairy": {
        "Fire": 0.5, "Fighting": 2, "Poison": 0.5, "Dragon": 2,
        "Dark": 2, "Steel": 0.5
    },
}


def get_type_effectiveness(
    attack_type: str,
    defender_types: list[str],
    tera_type: Optional[str] = None
) -> float:
    """
    Calculate type effectiveness multiplier.

    Args:
        attack_type: Type of the attacking move
        defender_types: List of defender's types (1-2)
        tera_type: If defender is Terastallized, only this type is used

    Returns:
        Effectiveness multiplier (0, 0.25, 0.5, 1, 2, or 4)
    """
    # Normalize type names
    attack_type = attack_type.capitalize()

    # If Tera active, only consider Tera type for defense
    if tera_type:
        types_to_check = [tera_type.capitalize()]
    else:
        types_to_check = [t.capitalize() for t in defender_types]

    multiplier = 1.0
    chart = TYPE_CHART.get(attack_type, {})

    for def_type in types_to_check:
        if def_type in chart:
            multiplier *= chart[def_type]

    return multiplier


def is_super_effective(attack_type: str, defender_types: list[str]) -> bool:
    """Check if attack is super effective (2x or 4x)."""
    return get_type_effectiveness(attack_type, defender_types) >= 2.0


def is_not_very_effective(attack_type: str, defender_types: list[str]) -> bool:
    """Check if attack is not very effective (0.5x or 0.25x)."""
    eff = get_type_effectiveness(attack_type, defender_types)
    return 0 < eff < 1.0


def is_immune(attack_type: str, defender_types: list[str]) -> bool:
    """Check if defender is immune (0x)."""
    return get_type_effectiveness(attack_type, defender_types) == 0


@dataclass
class DamageModifiers:
    """All modifiers that affect damage calculation."""

    # Battle format
    is_doubles: bool = True
    multiple_targets: bool = False  # True if spread move hitting multiple targets

    # Weather
    weather: Optional[str] = None  # "sun", "rain", "sand", "snow", "harsh_sun", "heavy_rain"

    # Terrain
    terrain: Optional[str] = None  # "electric", "grassy", "psychic", "misty"
    attacker_grounded: bool = True
    defender_grounded: bool = True

    # Critical hit
    is_critical: bool = False

    # Status conditions
    attacker_burned: bool = False
    has_guts: bool = False  # Ignores burn penalty
    attacker_ability: Optional[str] = None
    defender_ability: Optional[str] = None

    # Screens
    reflect_up: bool = False
    light_screen_up: bool = False
    aurora_veil_up: bool = False

    # Stat stage modifiers (not stat values)
    attack_stage: int = 0  # -6 to +6
    defense_stage: int = 0
    special_attack_stage: int = 0
    special_defense_stage: int = 0

    # Item effects
    attacker_item: Optional[str] = None
    defender_item: Optional[str] = None

    # Terastallization
    tera_type: Optional[str] = None  # Attacker's Tera type if active
    tera_active: bool = False
    defender_tera_type: Optional[str] = None
    defender_tera_active: bool = False

    # Abilities
    has_adaptability: bool = False

    # Partner effects (doubles)
    helping_hand: bool = False
    friend_guard: bool = False  # Ally has Friend Guard

    # Other
    move_hits: int = 0  # For multi-hit moves (0 = auto-detect from move data)

    # Commander ability (Dondozo + Tatsugiri combo)
    # When active, Dondozo's stats are doubled (Attack, Defense, SpA, SpD, Speed)
    commander_active: bool = False  # Attacker has Commander (doubles offensive stat)
    defender_commander_active: bool = False  # Defender has Commander (doubles defensive stat)

    # Ruin abilities (treasures of ruin - Chi-Yu, Chien-Pao, Ting-Lu, Wo-Chien)
    # These reduce opposing Pokemon's stats by 25%
    beads_of_ruin: bool = False  # Chi-Yu: Lowers foe SpD to 0.75x
    sword_of_ruin: bool = False  # Chien-Pao: Lowers foe Def to 0.75x
    tablets_of_ruin: bool = False  # Wo-Chien: Lowers foe Atk to 0.75x
    vessel_of_ruin: bool = False  # Ting-Lu: Lowers foe SpA to 0.75x

    # Paradox abilities (stat boost when condition is met)
    # Protosynthesis: 1.3x to highest stat (1.5x for Speed) in sun or with Booster Energy
    # Quark Drive: 1.3x to highest stat (1.5x for Speed) in Electric Terrain or with Booster Energy
    protosynthesis_boost: Optional[str] = None  # Stat being boosted: "attack", "defense", "special_attack", "special_defense", "speed"
    quark_drive_boost: Optional[str] = None  # Stat being boosted
    defender_protosynthesis_boost: Optional[str] = None
    defender_quark_drive_boost: Optional[str] = None

    def get_weather_modifier(self, move_type: str) -> float:
        """Get weather damage modifier for a move type."""
        move_type = move_type.capitalize()

        if self.weather == "sun":
            if move_type == "Fire":
                return 1.5
            elif move_type == "Water":
                return 0.5
        elif self.weather == "rain":
            if move_type == "Water":
                return 1.5
            elif move_type == "Fire":
                return 0.5
        elif self.weather == "harsh_sun":
            if move_type == "Fire":
                return 1.5
            elif move_type == "Water":
                return 0  # Water moves fail
        elif self.weather == "heavy_rain":
            if move_type == "Water":
                return 1.5
            elif move_type == "Fire":
                return 0  # Fire moves fail

        return 1.0

    def get_terrain_modifier(self, move_type: str, is_physical: bool) -> float:
        """Get terrain damage modifier."""
        if not self.attacker_grounded:
            return 1.0

        move_type = move_type.capitalize()

        if self.terrain == "electric" and move_type == "Electric":
            return 1.3
        elif self.terrain == "grassy" and move_type == "Grass":
            return 1.3
        elif self.terrain == "psychic" and move_type == "Psychic":
            return 1.3
        elif self.terrain == "misty" and move_type == "Dragon":
            # Misty terrain halves Dragon damage if defender is grounded
            if self.defender_grounded:
                return 0.5

        return 1.0

    def get_screen_modifier(self, is_physical: bool) -> float:
        """Get screen damage reduction modifier."""
        if self.is_critical:
            return 1.0  # Crits ignore screens

        screen_mod = 1.0

        if self.aurora_veil_up:
            screen_mod = 2/3 if self.is_doubles else 0.5
        elif is_physical and self.reflect_up:
            screen_mod = 2/3 if self.is_doubles else 0.5
        elif not is_physical and self.light_screen_up:
            screen_mod = 2/3 if self.is_doubles else 0.5

        return screen_mod

    def get_item_modifier(self, move_type: str, is_physical: bool) -> float:
        """Get item damage modifier."""
        if not self.attacker_item:
            return 1.0

        item = self.attacker_item.lower().replace(" ", "-")
        move_type = move_type.capitalize()

        # Life Orb (applies to damage, not stat)
        if item == "life-orb":
            return 1.3

        # Expert Belt (only if super effective - caller must check)
        # Handled separately in damage calc

        # Type-boosting items (1.2x)
        type_items = {
            "charcoal": "Fire",
            "mystic-water": "Water",
            "magnet": "Electric",
            "miracle-seed": "Grass",
            "never-melt-ice": "Ice",
            "black-belt": "Fighting",
            "poison-barb": "Poison",
            "soft-sand": "Ground",
            "sharp-beak": "Flying",
            "twisted-spoon": "Psychic",
            "silver-powder": "Bug",
            "hard-stone": "Rock",
            "spell-tag": "Ghost",
            "dragon-fang": "Dragon",
            "black-glasses": "Dark",
            "metal-coat": "Steel",
            "silk-scarf": "Normal",
            "fairy-feather": "Fairy",
        }

        if item in type_items and type_items[item] == move_type:
            return 1.2

        # Plates (1.2x) - same as type items basically
        plates = {
            "flame-plate": "Fire",
            "splash-plate": "Water",
            "zap-plate": "Electric",
            "meadow-plate": "Grass",
            "icicle-plate": "Ice",
            "fist-plate": "Fighting",
            "toxic-plate": "Poison",
            "earth-plate": "Ground",
            "sky-plate": "Flying",
            "mind-plate": "Psychic",
            "insect-plate": "Bug",
            "stone-plate": "Rock",
            "spooky-plate": "Ghost",
            "draco-plate": "Dragon",
            "dread-plate": "Dark",
            "iron-plate": "Steel",
            "pixie-plate": "Fairy",
        }

        if item in plates and plates[item] == move_type:
            return 1.2

        return 1.0

    def get_stat_stage_multiplier(self, stage: int) -> float:
        """Convert stat stage (-6 to +6) to multiplier."""
        if stage >= 0:
            return (2 + stage) / 2
        else:
            return 2 / (2 - stage)


# Ability effects on damage
OFFENSIVE_ABILITIES: dict[str, dict] = {
    "adaptability": {"stab_mod": 2.0},  # STAB becomes 2x instead of 1.5x
    "aerilate": {"normal_to": "Flying", "boost": 1.2},
    "pixilate": {"normal_to": "Fairy", "boost": 1.2},
    "refrigerate": {"normal_to": "Ice", "boost": 1.2},
    "galvanize": {"normal_to": "Electric", "boost": 1.2},
    "normalize": {"all_to": "Normal"},
    "tough-claws": {"contact_boost": 1.3},
    "iron-fist": {"punch_boost": 1.2},
    "reckless": {"recoil_boost": 1.2},
    "sheer-force": {"effect_boost": 1.3},  # Removes secondary effects
    "technician": {"weak_boost": 1.5, "threshold": 60},  # Boost moves <=60 BP
    "hustle": {"physical_boost": 1.5},
    "gorilla-tactics": {"physical_boost": 1.5},  # Choice locked
    "huge-power": {"attack_double": True},
    "pure-power": {"attack_double": True},
    "beads-of-ruin": {"spd_reduction": 0.75},  # Lowers foe SpD
    "sword-of-ruin": {"def_reduction": 0.75},  # Lowers foe Def
    "tablets-of-ruin": {"atk_reduction": 0.75},  # Lowers foe Atk
    "vessel-of-ruin": {"spa_reduction": 0.75},  # Lowers foe SpA
}

DEFENSIVE_ABILITIES: dict[str, dict] = {
    "multiscale": {"full_hp_reduction": 0.5},
    "shadow-shield": {"full_hp_reduction": 0.5},
    "solid-rock": {"se_reduction": 0.75},
    "filter": {"se_reduction": 0.75},
    "prism-armor": {"se_reduction": 0.75},
    "ice-scales": {"special_reduction": 0.5},
    "thick-fat": {"fire_ice_reduction": 0.5},
    "heatproof": {"fire_reduction": 0.5},
    "water-bubble": {"fire_reduction": 0.5},
    "fluffy": {"contact_reduction": 0.5, "fire_weakness": 2.0},
    "fur-coat": {"physical_reduction": 0.5},
    "friend-guard": {"ally_reduction": 0.75},  # Reduces damage to ally
}
