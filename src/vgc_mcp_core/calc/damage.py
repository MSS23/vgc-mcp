"""Full Gen 9 VGC damage calculator.

Damage Formula (Gen 5+):
Base = floor(floor(floor(floor(2*Level/5+2) * Power * Atk/Def) / 50) + 2)

Then apply modifiers in order using pokeRound (rounds DOWN on 0.5):
1. Spread move (3072/4096 = 0.75x)
2. Weather (6144/4096 = 1.5x boost, 2048/4096 = 0.5x reduce)
3. Critical hit (6144/4096 = 1.5x)
4. Random factor (85-100, as damage * random / 100)
5. STAB (6144/4096 = 1.5x, or 8192/4096 = 2.0x)
6. Type effectiveness (integer multiplier)
7. Burn (2048/4096 = 0.5x on physical)
8. Final modifier chain (screens, items, abilities)

Pokemon uses 4096-based fractions for modifiers, applying pokeRound after each.
pokeRound: if decimal > 0.5, round UP; otherwise round DOWN (0.5 rounds DOWN).

Reference: https://bulbapedia.bulbagarden.net/wiki/Damage
"""

import math
from dataclasses import dataclass, replace
from typing import Optional

from ..config import EV_BREAKPOINTS_LV50
from ..models.move import (
    GEN9_SPECIAL_MOVES,
    Move,
    MoveCategory,
    get_move_type_for_user,
    get_multi_hit_info,
)
from ..models.pokemon import PokemonBuild
from ..utils.damage_verdicts import (
    KOProbability,
    calculate_ko_probability,
    calculate_multi_hit_ko_probability,
)
from ..utils.normalize import normalize_ability, normalize_item, normalize_move
from .modifiers import (
    DamageModifiers,
    get_type_effectiveness,
)
from .stats import calculate_all_stats

# =============================================================================
# Pokemon-accurate rounding and modifier application
# =============================================================================

def poke_round(num: float) -> int:
    """
    Pokemon-style rounding: rounds DOWN on exactly 0.5, otherwise normal rounding.

    This is used throughout Pokemon's damage calculation. Unlike standard math
    rounding (which rounds 0.5 UP), Pokemon rounds 0.5 DOWN.

    Examples:
        poke_round(10.4) -> 10  (normal floor)
        poke_round(10.5) -> 10  (rounds DOWN - this is the key difference!)
        poke_round(10.6) -> 11  (normal ceil)
    """
    decimal = num % 1
    if decimal > 0.5:
        return math.ceil(num)
    return math.floor(num)


def apply_stat_stage(stat: int, stage: int) -> int:
    """Apply a stat stage multiplier using Showdown's exact integer math.

    Showdown does NOT use rounded 4096 fractions for stat stages; it uses exact
    integer fractions with FLOOR (gen789.ts `modifyStat` / boost table):
        stage > 0:  floor(stat * (2 + stage) / 2)
        stage < 0:  floor(stat * 2 / (2 - stage))
        stage == 0: unchanged

    Example: 100 Attack at -1 stage = floor(100 * 2 / 3) = 66 (NOT 67).
    """
    if stage == 0:
        return stat
    if stage > 0:
        stage = min(stage, 6)
        return (stat * (2 + stage)) // 2
    stage = max(stage, -6)
    return (stat * 2) // (2 - stage)


def apply_mod(value: int, modifier: int) -> int:
    """
    Apply a 4096-based modifier to a value with pokeRound.

    Pokemon internally represents multipliers as fractions with 4096 denominator:
    - 1.5x = 6144/4096
    - 1.3x = 5324/4096 (Life Orb)
    - 1.2x = 4915/4096 (type-boosting items)
    - 0.75x = 3072/4096
    - 0.5x = 2048/4096

    Args:
        value: The damage value to modify
        modifier: The 4096-based modifier (4096 = 1.0x, no change)

    Returns:
        Modified value with proper Pokemon rounding
    """
    if modifier == 4096:
        return value
    return poke_round(value * modifier / 4096)


def chain_mods(mods: list[int]) -> int:
    """
    Chain multiple 4096-based modifiers together.

    When combining multiple modifiers of the same category (e.g., multiple
    final damage modifiers), Pokemon chains them with a specific rounding method.

    Args:
        mods: List of 4096-based modifiers

    Returns:
        Combined modifier (4096-based)
    """
    result = 4096
    for mod in mods:
        if mod != 4096:
            # (result * mod + 2048) >> 12 is equivalent to rounding (result * mod / 4096)
            result = (result * mod + 2048) >> 12
    return result


# 4096-based modifier constants (matching Pokemon's internal values)
MOD_NEUTRAL = 4096       # 1.0x (no change)
MOD_SPREAD = 3072        # 0.75x (spread move in doubles)
MOD_WEATHER_BOOST = 6144 # 1.5x (Fire in Sun, Water in Rain)
MOD_WEATHER_NERF = 2048  # 0.5x (Fire in Rain, Water in Sun)
MOD_CRIT = 6144          # 1.5x (critical hit)
MOD_STAB = 6144          # 1.5x (Same Type Attack Bonus)
MOD_STAB_BOOSTED = 8192  # 2.0x (Tera STAB into same type, or Adaptability)
MOD_STAB_TERA_ADAPT = 9216  # 2.25x (Tera STAB into same type WITH Adaptability)
MOD_STAB_TERA_NEW = 6144 # 1.5x (Tera into different type)
MOD_BURN = 2048          # 0.5x (burned, physical move)
MOD_LIFE_ORB = 5324      # ~1.3x (Life Orb boost)
MOD_EXPERT_BELT = 4915   # ~1.2x (Expert Belt on super effective)
MOD_TYPE_BOOST = 4915    # ~1.2x (type-boosting items like Charcoal)
MOD_SCREEN_SINGLES = 2048    # 0.5x (Reflect/Light Screen in singles)
MOD_SCREEN_DOUBLES = 2732    # ~0.667x (Reflect/Light Screen in doubles)
MOD_HELPING_HAND = 6144      # 1.5x (Helping Hand)
MOD_FRIEND_GUARD = 3072      # 0.75x (Friend Guard)
MOD_TOUGH_CLAWS = 5325       # ~1.3x (Tough Claws on contact moves)
MOD_IRON_FIST = 4915         # ~1.2x (Iron Fist on punch moves)
MOD_MULTISCALE = 2048        # 0.5x (Multiscale/Shadow Shield at full HP)
MOD_ICE_SCALES = 2048        # 0.5x (Ice Scales on special moves)
MOD_SOLID_ROCK = 3072        # 0.75x (Solid Rock/Filter on super effective)
MOD_FLUFFY_CONTACT = 2048    # 0.5x (Fluffy on contact moves)
MOD_FLUFFY_FIRE = 8192       # 2.0x (Fluffy weakness to Fire)
MOD_THICK_FAT = 2048         # 0.5x (Thick Fat on Fire/Ice moves)
MOD_RESISTANCE_BERRY = 2048  # 0.5x (Resistance berries on super effective)
MOD_ATE_ABILITY = 4915       # ~1.2x (Aerilate, Pixilate, Refrigerate, Galvanize)

# Type-changing abilities that convert Normal moves to another type
ATE_ABILITIES: dict[str, str] = {
    "aerilate": "Flying",
    "pixilate": "Fairy",
    "refrigerate": "Ice",
    "galvanize": "Electric",
}

# Type immunity abilities - maps ability to list of immune types
IMMUNITY_ABILITIES: dict[str, list[str]] = {
    "levitate": ["Ground"],
    "flash-fire": ["Fire"],
    "volt-absorb": ["Electric"],
    "motor-drive": ["Electric"],
    "lightning-rod": ["Electric"],
    "water-absorb": ["Water"],
    "storm-drain": ["Water"],
    "dry-skin": ["Water"],
    "sap-sipper": ["Grass"],
    "earth-eater": ["Ground"],
    "well-baked-body": ["Fire"],
    "wind-rider": [],  # Only immune to wind moves, handled separately
    "bulletproof": [],  # Immune to ball/bomb moves, handled separately
    "soundproof": [],  # Immune to sound moves, handled separately
}

# Abilities that bypass defender's abilities (Mold Breaker and variants)
MOLD_BREAKER_ABILITIES = {
    "mold-breaker", "teravolt", "turboblaze",
    "mycelium-might",  # Only for status moves, but include for completeness
}

# Wind moves for Wind Rider ability
WIND_MOVES = {
    "bleakwind-storm", "fairy-wind", "gust", "hurricane", "petal-blizzard",
    "sandstorm", "tailwind", "twister", "whirlwind", "wildbolt-storm",
}

# Sound moves for Soundproof ability
SOUND_MOVES = {
    "boomburst", "bug-buzz", "chatter", "clanging-scales", "clangorous-soul",
    "clangorous-soulblaze", "confide", "disarming-voice", "echoed-voice",
    "eerie-spell", "grass-whistle", "growl", "heal-bell", "howl", "hyper-voice",
    "metal-sound", "noble-roar", "overdrive", "parting-shot", "perish-song",
    "relic-song", "roar", "round", "screech", "shadow-force", "sing",
    "snarl", "snore", "sonic-boom", "sparkling-aria", "supersonic",
    "torch-song", "uproar",
}

# Ball/Bomb moves for Bulletproof ability
BALL_BOMB_MOVES = {
    "acid-spray", "aura-sphere", "barrage", "beak-blast", "bullet-seed",
    "egg-bomb", "electro-ball", "energy-ball", "focus-blast", "gyro-ball",
    "ice-ball", "magnet-bomb", "mist-ball", "mud-bomb", "octazooka",
    "pollen-puff", "pyro-ball", "rock-blast", "rock-wrecker", "seed-bomb",
    "shadow-ball", "sludge-bomb", "weather-ball", "zap-cannon",
}

# Pulse moves for Mega Launcher ability (1.5x)
PULSE_MOVES = {
    "aura-sphere", "dark-pulse", "dragon-pulse", "heal-pulse",
    "origin-pulse", "terrain-pulse", "water-pulse",
}

# Recoil moves for Reckless ability (1.2x)
RECOIL_MOVES = {
    "brave-bird", "double-edge", "flare-blitz", "head-charge",
    "head-smash", "high-jump-kick", "submission", "take-down",
    "volt-tackle", "wild-charge", "wood-hammer", "wave-crash",
}


# Punch moves for Iron Fist ability
PUNCH_MOVES = {
    "ice-punch", "fire-punch", "thunder-punch", "mach-punch", "mega-punch",
    "focus-punch", "comet-punch", "dizzy-punch", "dynamic-punch", "meteor-mash",
    "shadow-punch", "sky-uppercut", "drain-punch", "bullet-punch", "hammer-arm",
    "power-up-punch", "plasma-fists", "double-iron-bash", "surging-strikes",
    "wicked-blow", "jet-punch", "rage-fist",
}

# Slicing moves for Sharpness ability (1.5x boost)
SLICING_MOVES = {
    "aerial-ace", "air-cutter", "air-slash", "aqua-cutter", "behemoth-blade",
    "ceaseless-edge", "cross-poison", "cut", "fury-cutter", "kowtow-cleave",
    "leaf-blade", "night-slash", "population-bomb", "psycho-cut", "razor-leaf",
    "razor-shell", "sacred-sword", "secret-sword", "slash", "solar-blade",
    "stone-axe", "x-scissor",
}

# Biting moves for Strong Jaw ability (1.5x boost)
BITING_MOVES = {
    "bite", "crunch", "fire-fang", "ice-fang", "thunder-fang", "poison-fang",
    "psychic-fangs", "hyper-fang", "super-fang", "jaw-lock", "fishious-rend",
}

# New 4096-based modifier constants
MOD_ROCKY_PAYLOAD = 6144    # 1.5x (Rocky Payload - Rock moves)
MOD_SHARPNESS = 6144        # 1.5x (Sharpness - slicing moves)
MOD_STRONG_JAW = 6144       # 1.5x (Strong Jaw - biting moves)
MOD_PUNCHING_GLOVE = 4506   # ~1.1x (Punching Glove - punch moves)
MOD_PURIFYING_SALT = 2048   # 0.5x (Purifying Salt - Ghost damage reduction)
MOD_TINTED_LENS = 8192      # 2.0x (Tinted Lens - on resisted hits)
MOD_SNIPER_CRIT = 9216      # 2.25x (Sniper - crit damage instead of 1.5x)
MOD_ORICHALCUM = 5461       # ~1.333x (Orichalcum Pulse - Attack in Sun)
MOD_HADRON = 5461           # ~1.333x (Hadron Engine - SpA in Electric Terrain)

# Stat stage modifiers (4096-based)
STAT_STAGE_MODS = {
    -6: 1024,   # 0.25x
    -5: 1170,   # 0.286x (rounded)
    -4: 1365,   # 0.333x (rounded)
    -3: 1638,   # 0.4x
    -2: 2048,   # 0.5x
    -1: 2731,   # 0.667x (rounded)
    0: 4096,    # 1.0x (neutral)
    1: 6144,    # 1.5x
    2: 8192,    # 2.0x
    3: 10240,   # 2.5x
    4: 12288,   # 3.0x
    5: 14336,   # 3.5x
    6: 16384,   # 4.0x
}

# Ability/Item modifiers for stat calculations
MOD_STAT_DOUBLE = 8192      # 2.0x (Huge Power, Pure Power, Commander)
MOD_CHOICE_BOOST = 6144     # 1.5x (Choice Band/Specs)
MOD_ASSAULT_VEST = 6144     # 1.5x SpD
MOD_RUIN = 3072             # 0.75x (Sword/Beads/Tablets/Vessel of Ruin)
MOD_PARADOX_1_3 = 5325      # ~1.3x (Protosynthesis/Quark Drive non-speed)
MOD_PARADOX_1_5 = 6144      # 1.5x (Protosynthesis/Quark Drive speed)
MOD_EMBODY_ASPECT = 6144    # 1.5x (+1 stage equivalent)

# New offensive ability modifiers
MOD_GUTS = 6144             # 1.5x (Guts - Attack when statused)
MOD_SAND_FORCE = 5325       # ~1.3x (Sand Force - Ground/Rock/Steel in sand)
MOD_MEGA_LAUNCHER = 6144    # 1.5x (Mega Launcher - pulse moves)
MOD_STEELY_SPIRIT = 6144    # 1.5x (Steely Spirit - Steel moves)
MOD_TRANSISTOR = 6144       # 1.5x (Transistor - Electric moves in Gen 9)
MOD_DRAGONS_MAW = 6144      # 1.5x (Dragon's Maw - Dragon moves)
MOD_RECKLESS = 4915         # ~1.2x (Reckless - recoil moves)
MOD_ANALYTIC = 5325         # ~1.3x (Analytic - moving last)
MOD_WATER_BUBBLE_ATK = 8192 # 2.0x (Water Bubble - Water moves)
MOD_NEUROFORCE = 5120       # 1.25x (Neuroforce - super effective)
MOD_PUNK_ROCK_ATK = 5325    # ~1.3x (Punk Rock - sound moves)

# New defensive ability modifiers
MOD_HEATPROOF = 2048        # 0.5x (Heatproof - Fire damage)
MOD_WATER_BUBBLE_DEF = 2048 # 0.5x (Water Bubble - Fire damage taken)
MOD_DRY_SKIN_FIRE = 5120    # 1.25x (Dry Skin - Fire damage taken)
MOD_FUR_COAT = 2048         # 0.5x (Fur Coat - physical damage)
MOD_PUNK_ROCK_DEF = 2048    # 0.5x (Punk Rock - sound damage taken)

# New item modifiers
MOD_MUSCLE_BAND = 4505      # ~1.1x (Muscle Band - physical moves)
MOD_WISE_GLASSES = 4505     # ~1.1x (Wise Glasses - special moves)
MOD_SHEER_FORCE = 5325      # ~1.3x (Sheer Force - moves with secondary effect)
MOD_NORMAL_GEM = 6144       # 1.5x (Normal Gem - first Normal move, one-time use)

# Resistance berries - reduce super-effective damage by 50%
RESISTANCE_BERRIES = {
    "occa-berry": "Fire",
    "passho-berry": "Water",
    "wacan-berry": "Electric",
    "rindo-berry": "Grass",
    "yache-berry": "Ice",
    "chople-berry": "Fighting",
    "kebia-berry": "Poison",
    "shuca-berry": "Ground",
    "coba-berry": "Flying",
    "payapa-berry": "Psychic",
    "tanga-berry": "Bug",
    "charti-berry": "Rock",
    "kasib-berry": "Ghost",
    "haban-berry": "Dragon",
    "colbur-berry": "Dark",
    "babiri-berry": "Steel",
    "roseli-berry": "Fairy",
}


# =============================================================================
# Variable base power calculations
# =============================================================================

def _calculate_variable_bp(
    move_name: str,
    base_power: int,
    special_move_data: dict,
    attacker_speed: int,
    defender_speed: int,
    modifiers: "DamageModifiers",
) -> int:
    """
    Calculate variable base power for special moves.

    Args:
        move_name: Normalized move name
        base_power: Move's base power from data
        special_move_data: Special move data dict from GEN9_SPECIAL_MOVES
        attacker_speed: Attacker's calculated Speed stat
        defender_speed: Defender's calculated Speed stat
        modifiers: Current damage modifiers

    Returns:
        Calculated base power
    """
    variable_bp_type = special_move_data.get("variable_bp")

    if not variable_bp_type:
        # Check for scaling moves (Rage Fist, Last Respects)
        scaling_type = special_move_data.get("scaling")
        if scaling_type == "times_hit":
            # Rage Fist: +50 BP per time hit, capped at 350
            return min(350, base_power + (50 * modifiers.times_hit))
        elif scaling_type == "fainted_allies":
            # Last Respects: +50 BP per fainted party member, capped at 300
            return min(300, base_power + (50 * modifiers.fainted_party_count))
        return base_power

    if variable_bp_type == "gyro_ball":
        # Gyro Ball: BP = min(150, 1 + floor(25 * target_speed / user_speed))
        if attacker_speed <= 0:
            return 150
        return min(150, 1 + math.floor(25 * defender_speed / attacker_speed))

    elif variable_bp_type == "electro_ball":
        # Electro Ball: BP based on speed ratio (user speed / target speed)
        if defender_speed <= 0:
            return 150
        ratio = attacker_speed / defender_speed
        if ratio >= 4:
            return 150
        elif ratio >= 3:
            return 120
        elif ratio >= 2:
            return 80
        elif ratio >= 1:
            return 60
        else:
            return 40

    elif variable_bp_type == "hp_scaling":
        # Eruption/Water Spout: BP = max(1, floor(150 * current_hp / max_hp))
        if modifiers.attacker_current_hp is not None and modifiers.attacker_max_hp:
            return max(1, math.floor(150 * modifiers.attacker_current_hp / modifiers.attacker_max_hp))
        return base_power  # Return base (150) if HP not specified

    elif variable_bp_type == "reversal":
        # Reversal/Flail: BP scales inversely with remaining HP %
        if modifiers.attacker_current_hp is not None and modifiers.attacker_max_hp:
            hp_percent = modifiers.attacker_current_hp / modifiers.attacker_max_hp
            if hp_percent <= 0.0417:  # <= 4.17%
                return 200
            elif hp_percent <= 0.1042:  # <= 10.42%
                return 150
            elif hp_percent <= 0.2083:  # <= 20.83%
                return 100
            elif hp_percent <= 0.3542:  # <= 35.42%
                return 80
            elif hp_percent <= 0.6875:  # <= 68.75%
                return 40
            else:
                return 20
        return 20  # Default to minimum if HP not specified

    elif variable_bp_type == "hex":
        # Hex: 65 BP, doubled to 130 when target is statused
        # Infernal Parade: 60 BP, doubled to 120 when target is statused
        if modifiers.defender_statused:
            return base_power * 2
        return base_power

    elif variable_bp_type == "facade":
        # Facade: 70 BP, doubled to 140 when user is burned/paralyzed/poisoned
        if modifiers.attacker_statused or modifiers.attacker_burned:
            return base_power * 2
        return base_power

    elif variable_bp_type == "acrobatics":
        # Acrobatics: 55 BP, 110 BP when user has no held item
        if not modifiers.attacker_item:
            return 110
        return base_power

    elif variable_bp_type == "stored_power":
        # Stored Power/Power Trip: 20 + 20 per positive stat stage
        return 20 + (20 * modifiers.total_positive_stages)

    elif variable_bp_type == "knock_off":
        # Knock Off: 65 BP, boosted 1.5x (floor -> 97) when the target is
        # holding a removable item. We treat any held item as removable, which
        # covers all common VGC items (AV, Leftovers, Choice, berries, masks).
        if modifiers.defender_item:
            return math.floor(base_power * 1.5)
        return base_power

    elif variable_bp_type == "weight_ratio":
        # Heavy Slam/Heat Crash: BP based on weight ratio (user / target)
        if modifiers.attacker_weight and modifiers.defender_weight:
            if modifiers.defender_weight <= 0:
                return 120
            ratio = modifiers.attacker_weight / modifiers.defender_weight
            if ratio >= 5:
                return 120
            elif ratio >= 4:
                return 100
            elif ratio >= 3:
                return 80
            elif ratio >= 2:
                return 60
            else:
                return 40
        return 60  # Default if weights not specified

    return base_power


def _calculate_multi_hit_rolls(
    damages_per_hit: list[int],
    hit_count: int
) -> list[int]:
    """
    Calculate representative damage rolls for multi-hit moves.

    For multi-hit moves, each hit gets an independent random roll (85-100%).
    This means there are 16^hit_count possible combinations.

    For display purposes, we return 16 representative rolls spanning the
    min-max range. For KO probability, all combinations must be considered.

    Args:
        damages_per_hit: List of 16 damage values (one per random roll)
        hit_count: Number of hits

    Returns:
        List of 16 representative total damage values
    """
    min_per_hit = min(damages_per_hit)
    max_per_hit = max(damages_per_hit)

    min_total = min_per_hit * hit_count
    max_total = max_per_hit * hit_count

    # Generate 16 representative rolls evenly distributed
    rolls = []
    for i in range(16):
        # Interpolate between min and max
        total = min_total + int((max_total - min_total) * i / 15)
        rolls.append(total)

    return rolls


def format_percent(value: float) -> str:
    """
    Format percentage to match Pokemon Showdown's display.
    - Strips trailing .0 (e.g., 101.0% → 101%)
    - Keeps one decimal place otherwise (e.g., 117.3%)
    """
    formatted = f"{value:.1f}"
    # Strip trailing .0
    if formatted.endswith('.0'):
        return formatted[:-2]
    return formatted


@dataclass
class DamageResult:
    """Result of damage calculation."""
    min_damage: int
    max_damage: int
    min_percent: float
    max_percent: float
    rolls: list[int]
    defender_hp: int
    ko_chance: str
    is_guaranteed_ohko: bool
    is_possible_ohko: bool
    details: dict
    ko_probability: Optional[KOProbability] = None  # Detailed KO probability analysis

    @property
    def damage_range(self) -> str:
        """Formatted damage range string."""
        min_pct = format_percent(self.min_percent)
        max_pct = format_percent(self.max_percent)
        return f"{self.min_damage}-{self.max_damage} ({min_pct}%-{max_pct}%)"


def calculate_damage(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move: Move,
    modifiers: Optional[DamageModifiers] = None
) -> DamageResult:
    """
    Calculate damage from one Pokemon to another.

    Args:
        attacker: Attacking Pokemon with full build
        defender: Defending Pokemon with full build
        move: Move being used
        modifiers: Battle conditions and modifiers

    Returns:
        DamageResult with damage range, percentages, and KO probability
    """
    if modifiers is None:
        modifiers = DamageModifiers()

    # Auto-fill attacker/defender items from Pokemon builds if not specified
    if modifiers.attacker_item is None and attacker.item:
        modifiers = replace(modifiers, attacker_item=attacker.item)
    if modifiers.defender_item is None and defender.item:
        modifiers = replace(modifiers, defender_item=defender.item)

    # Auto-fill attacker/defender abilities from Pokemon builds if not specified
    if modifiers.attacker_ability is None and attacker.ability:
        modifiers = replace(modifiers, attacker_ability=attacker.ability)
    if modifiers.defender_ability is None and defender.ability:
        modifiers = replace(modifiers, defender_ability=defender.ability)

    # Auto-set has_adaptability from attacker_ability so callers don't need to
    # know about the separate flag. Adaptability boosts STAB from 1.5x to 2x.
    if not modifiers.has_adaptability and modifiers.attacker_ability:
        if normalize_ability(modifiers.attacker_ability) == "adaptability":
            modifiers = replace(modifiers, has_adaptability=True)

    # Auto-derive Protosynthesis / Quark Drive boost stats so callers don't
    # need to recompute the highest-stat logic per tool. Booster Energy
    # always activates them; sun activates Protosynthesis; electric terrain
    # activates Quark Drive. Speed wins ties (Game-mechanic accurate).
    def _highest_non_hp_stat(p: PokemonBuild) -> str:
        # Format-aware: delegate to calculate_all_stats so Champions builds
        # (which carry SPs, not EVs) pick the actually-invested stat rather
        # than the highest base stat. Speed wins ties (game-accurate).
        from .stats import calculate_all_stats
        stats = {k: v for k, v in calculate_all_stats(p).items() if k != "hp"}
        max_value = max(stats.values())
        tied = [s for s, v in stats.items() if v == max_value]
        return "speed" if "speed" in tied else tied[0]

    def _paradox_active(ability_norm: str, item_norm: str | None, weather: str | None, terrain: str | None) -> bool:
        if ability_norm == "protosynthesis":
            return item_norm == "booster-energy" or weather == "sun"
        if ability_norm == "quark-drive":
            return item_norm == "booster-energy" or terrain == "electric"
        return False

    if modifiers.attacker_ability:
        atk_ab_norm = normalize_ability(modifiers.attacker_ability)
        atk_item_norm = normalize_item(modifiers.attacker_item) if modifiers.attacker_item else None
        if atk_ab_norm == "protosynthesis" and modifiers.protosynthesis_boost is None:
            if _paradox_active(atk_ab_norm, atk_item_norm, modifiers.weather, modifiers.terrain):
                modifiers = replace(modifiers, protosynthesis_boost=_highest_non_hp_stat(attacker))
        elif atk_ab_norm == "quark-drive" and modifiers.quark_drive_boost is None:
            if _paradox_active(atk_ab_norm, atk_item_norm, modifiers.weather, modifiers.terrain):
                modifiers = replace(modifiers, quark_drive_boost=_highest_non_hp_stat(attacker))

    if modifiers.defender_ability:
        def_ab_norm = normalize_ability(modifiers.defender_ability)
        def_item_norm = normalize_item(modifiers.defender_item) if modifiers.defender_item else None
        if def_ab_norm == "protosynthesis" and modifiers.defender_protosynthesis_boost is None:
            if _paradox_active(def_ab_norm, def_item_norm, modifiers.weather, modifiers.terrain):
                modifiers = replace(modifiers, defender_protosynthesis_boost=_highest_non_hp_stat(defender))
        elif def_ab_norm == "quark-drive" and modifiers.defender_quark_drive_boost is None:
            if _paradox_active(def_ab_norm, def_item_norm, modifiers.weather, modifiers.terrain):
                modifiers = replace(modifiers, defender_quark_drive_boost=_highest_non_hp_stat(defender))

    # Auto-apply attacker switch-in / Tera-on stat-stage abilities. These are
    # mechanically guaranteed when the ability is present, so callers don't need
    # to remember to encode them. Stack additively with any caller-supplied stage.
    #   - Intrepid Sword: +1 Atk on switch-in (Zacian-Crowned)
    #   - Embody Aspect (Hearthflame): +1 Atk on Tera (Ogerpon-Hearthflame)
    if modifiers.attacker_ability:
        ab_norm = normalize_ability(modifiers.attacker_ability)
        atk_name_norm = (attacker.name or "").lower().replace(" ", "-")
        atk_bonus = 0
        if ab_norm == "intrepid-sword":
            atk_bonus = 1
        elif ab_norm in ("embody-aspect", "embody-aspect-hearthflame") and modifiers.tera_active:
            if "hearthflame" in atk_name_norm or ab_norm == "embody-aspect-hearthflame":
                atk_bonus = 1
        if atk_bonus:
            modifiers = replace(modifiers, attack_stage=modifiers.attack_stage + atk_bonus)

    # Auto-detect Ruin abilities from attacker/defender ability names.
    # Ruin abilities are field effects (not stat stages), so they always apply
    # even on critical hits. Only auto-detect if the flags aren't already set.
    if modifiers.attacker_ability:
        atk_ab = normalize_ability(modifiers.attacker_ability)
        if atk_ab == "sword-of-ruin" and not modifiers.sword_of_ruin:
            modifiers = replace(modifiers, sword_of_ruin=True)
        elif atk_ab == "beads-of-ruin" and not modifiers.beads_of_ruin:
            modifiers = replace(modifiers, beads_of_ruin=True)
    if modifiers.defender_ability:
        def_ab = normalize_ability(modifiers.defender_ability)
        if def_ab == "tablets-of-ruin" and not modifiers.tablets_of_ruin:
            modifiers = replace(modifiers, tablets_of_ruin=True)
        elif def_ab == "vessel-of-ruin" and not modifiers.vessel_of_ruin:
            modifiers = replace(modifiers, vessel_of_ruin=True)

    # Check for multi-hit move mechanics
    multi_hit_info = get_multi_hit_info(move.name)
    hit_count = 1
    always_crit = move.always_crit  # Check Move object first (includes single-hit always-crit moves)
    if multi_hit_info:
        min_hits, max_hits, multi_hit_always_crit = multi_hit_info
        # Use specified hit count from modifiers, or default to max hits for calc
        if modifiers.move_hits > 0:
            hit_count = modifiers.move_hits
        else:
            hit_count = max_hits  # Show max damage potential by default
        # Multi-hit moves may have always_crit flag
        if multi_hit_always_crit:
            always_crit = True

    # Apply always-crit for moves like Surging Strikes, Wicked Blow, Frost Breath
    if always_crit:
        modifiers = replace(modifiers, is_critical=True)

    # Non-damaging moves
    if not move.is_damaging:
        return DamageResult(
            min_damage=0,
            max_damage=0,
            min_percent=0,
            max_percent=0,
            rolls=[0] * 16,
            defender_hp=1,
            ko_chance="N/A (Status move)",
            is_guaranteed_ohko=False,
            is_possible_ohko=False,
            details={"reason": "Status move"}
        )

    # Handle type-changing abilities (Aerilate, Pixilate, Refrigerate, Galvanize)
    # These change Normal-type moves to another type and apply a 1.2x power boost
    effective_move_type = move.type.capitalize()
    ate_ability_boost = False
    if modifiers.attacker_ability:
        ability = normalize_ability(modifiers.attacker_ability)
        if ability in ATE_ABILITIES and move.type.capitalize() == "Normal":
            effective_move_type = ATE_ABILITIES[ability]
            ate_ability_boost = True

    # Get normalized move name for immunity checks
    move_name_normalized = normalize_move(move.name)

    # Handle form-dependent move types (Ivy Cudgel changes type based on Ogerpon form)
    if attacker and move_name_normalized == "ivy-cudgel":
        effective_move_type = get_move_type_for_user(move.name, attacker.name, effective_move_type)

    # Handle Tera Blast: type and category change when Terastallized
    # When Terastallized, Tera Blast becomes the attacker's Tera type
    # Also becomes physical if Attack > Special Attack
    tera_blast_physical = False
    if move_name_normalized == "tera-blast" and modifiers.tera_active and modifiers.tera_type:
        effective_move_type = modifiers.tera_type.capitalize()
        # Check if should be physical (Atk > SpA after all modifiers)
        if attacker:
            stats = calculate_all_stats(attacker)
            if stats["attack"] > stats["special_attack"]:
                tera_blast_physical = True

    # Determine if move is physical (accounting for Tera Blast category change)
    # This variable should be used instead of move.category == MoveCategory.PHYSICAL
    is_physical = tera_blast_physical or move.category == MoveCategory.PHYSICAL

    # Weather Ball changes type and doubles power in weather
    weather_ball_boosted = False
    if move_name_normalized == "weather-ball" and modifiers.weather:
        weather_type_map = {
            "sun": "Fire",
            "rain": "Water",
            "sand": "Rock",
            "snow": "Ice",
        }
        if modifiers.weather in weather_type_map:
            effective_move_type = weather_type_map[modifiers.weather]
            weather_ball_boosted = True

    # Check if attacker has Mold Breaker or similar (bypasses defender abilities)
    attacker_ignores_abilities = False
    if modifiers.attacker_ability:
        atk_ability = normalize_ability(modifiers.attacker_ability)
        attacker_ignores_abilities = atk_ability in MOLD_BREAKER_ABILITIES

    # Check for ability-based type immunities (unless attacker ignores abilities)
    if modifiers.defender_ability and not attacker_ignores_abilities:
        def_ability = normalize_ability(modifiers.defender_ability)

        # Check type-based immunities
        if def_ability in IMMUNITY_ABILITIES:
            immune_types = IMMUNITY_ABILITIES[def_ability]
            if effective_move_type in immune_types:
                return DamageResult(
                    min_damage=0,
                    max_damage=0,
                    min_percent=0,
                    max_percent=0,
                    rolls=[0] * 16,
                    defender_hp=1,
                    ko_chance=f"Immune ({def_ability.replace('-', ' ').title()})",
                    is_guaranteed_ohko=False,
                    is_possible_ohko=False,
                    details={"reason": f"Immune due to {def_ability.replace('-', ' ').title()}"}
                )

        # Wind Rider immunity to wind moves
        if def_ability == "wind-rider" and move_name_normalized in WIND_MOVES:
            return DamageResult(
                min_damage=0, max_damage=0, min_percent=0, max_percent=0,
                rolls=[0] * 16, defender_hp=1,
                ko_chance="Immune (Wind Rider)",
                is_guaranteed_ohko=False, is_possible_ohko=False,
                details={"reason": "Immune due to Wind Rider"}
            )

        # Soundproof immunity to sound moves
        if def_ability == "soundproof" and move_name_normalized in SOUND_MOVES:
            return DamageResult(
                min_damage=0, max_damage=0, min_percent=0, max_percent=0,
                rolls=[0] * 16, defender_hp=1,
                ko_chance="Immune (Soundproof)",
                is_guaranteed_ohko=False, is_possible_ohko=False,
                details={"reason": "Immune due to Soundproof"}
            )

        # Bulletproof immunity to ball/bomb moves
        if def_ability == "bulletproof" and move_name_normalized in BALL_BOMB_MOVES:
            return DamageResult(
                min_damage=0, max_damage=0, min_percent=0, max_percent=0,
                rolls=[0] * 16, defender_hp=1,
                ko_chance="Immune (Bulletproof)",
                is_guaranteed_ohko=False, is_possible_ohko=False,
                details={"reason": "Immune due to Bulletproof"}
            )

    # Check for Air Balloon item immunity to Ground
    if modifiers.defender_item:
        def_item = normalize_item(modifiers.defender_item)
        if def_item == "air-balloon" and effective_move_type == "Ground":
            return DamageResult(
                min_damage=0, max_damage=0, min_percent=0, max_percent=0,
                rolls=[0] * 16, defender_hp=1,
                ko_chance="Immune (Air Balloon)",
                is_guaranteed_ohko=False, is_possible_ohko=False,
                details={"reason": "Immune due to Air Balloon"}
            )

    # Calculate stats
    attacker_stats = calculate_all_stats(attacker)
    defender_stats = calculate_all_stats(defender)

    # Check for special move mechanics from GEN9_SPECIAL_MOVES
    # (move_name_normalized already defined above for immunity checks)
    special_move_data = GEN9_SPECIAL_MOVES.get(move_name_normalized, {})

    # Determine attacking and defending stats
    # Handle stat-swapping moves first
    if special_move_data.get("uses_target_attack"):
        # Foul Play: Uses defender's Attack stat for damage
        attack_stat_name = "attack"
        attack_stat = defender_stats["attack"]
        defense_stat_name = "defense" if is_physical else "special_defense"
        defense_stat = defender_stats[defense_stat_name]
    elif special_move_data.get("uses_user_defense"):
        # Body Press: Uses user's Defense stat instead of Attack
        attack_stat_name = "defense"
        attack_stat = attacker_stats["defense"]
        defense_stat_name = "defense"
        defense_stat = defender_stats["defense"]
    elif special_move_data.get("targets_physical_defense"):
        # Psyshock, Psystrike, Secret Sword: Special moves that target physical Defense
        attack_stat_name = "special_attack"
        attack_stat = attacker_stats["special_attack"]
        defense_stat_name = "defense"
        defense_stat = defender_stats["defense"]
    elif is_physical:
        attack_stat_name = "attack"
        defense_stat_name = "defense"
        attack_stat = attacker_stats[attack_stat_name]
        defense_stat = defender_stats[defense_stat_name]
    else:
        attack_stat_name = "special_attack"
        defense_stat_name = "special_defense"
        attack_stat = attacker_stats[attack_stat_name]
        defense_stat = defender_stats[defense_stat_name]

    # Apply stat stage modifiers
    # Critical hits ignore:
    # - Attacker's negative Attack/SpA stages (e.g., Intimidate drops)
    # - Defender's positive Defense/SpD stages (boosts)
    if is_physical:
        # Crits ignore negative attack stages (Intimidate)
        if modifiers.is_critical and modifiers.attack_stage < 0:
            pass  # Don't apply negative attack stage on crit
        else:
            attack_stat = apply_stat_stage(attack_stat, modifiers.attack_stage)
        # Crits ignore positive defense stages
        if not modifiers.is_critical or modifiers.defense_stage < 0:
            defense_stat = apply_stat_stage(defense_stat, modifiers.defense_stage)
    else:
        # Crits ignore negative special attack stages
        if modifiers.is_critical and modifiers.special_attack_stage < 0:
            pass  # Don't apply negative SpA stage on crit
        else:
            attack_stat = apply_stat_stage(attack_stat, modifiers.special_attack_stage)
        # Crits ignore positive special defense stages
        if not modifiers.is_critical or modifiers.special_defense_stage < 0:
            defense_stat = apply_stat_stage(defense_stat, modifiers.special_defense_stage)

    # Apply Choice Band/Specs (to stat, not damage)
    if modifiers.attacker_item:
        item = normalize_item(modifiers.attacker_item)
        if item == "choice-band" and is_physical:
            attack_stat = apply_mod(attack_stat, MOD_CHOICE_BOOST)
        elif item == "choice-specs" and not is_physical:
            attack_stat = apply_mod(attack_stat, MOD_CHOICE_BOOST)

    # Apply stat-modifying abilities
    if modifiers.attacker_ability:
        ability = normalize_ability(modifiers.attacker_ability)
        # Huge Power / Pure Power double Attack stat
        if ability in ("huge-power", "pure-power") and is_physical:
            attack_stat = apply_mod(attack_stat, MOD_STAT_DOUBLE)
        # Guts (1.5x Attack when statused) - Ursaluna, Conkeldurr, Heracross
        elif ability == "guts" and modifiers.attacker_statused and is_physical:
            attack_stat = apply_mod(attack_stat, MOD_GUTS)
        # Gorilla Tactics (1.5x Attack, locked into move) - Darmanitan-Galar
        elif ability == "gorilla-tactics" and is_physical:
            attack_stat = apply_mod(attack_stat, MOD_CHOICE_BOOST)
        # Flare Boost (1.5x SpA when burned) - Drifloon/Drifblim
        elif ability == "flare-boost" and modifiers.attacker_burned and not is_physical:
            attack_stat = apply_mod(attack_stat, MOD_CHOICE_BOOST)
        # Toxic Boost (1.5x Atk when poisoned) - Zangoose
        elif ability == "toxic-boost" and modifiers.attacker_statused and is_physical:
            # Note: Toxic Boost is specifically for poison, but we use attacker_statused for simplicity
            attack_stat = apply_mod(attack_stat, MOD_CHOICE_BOOST)
        # Orichalcum Pulse (1.333x Attack in Sun) - Koraidon
        elif ability == "orichalcum-pulse" and modifiers.weather == "sun":
            if is_physical:
                attack_stat = apply_mod(attack_stat, MOD_ORICHALCUM)
        # Hadron Engine (1.333x SpA in Electric Terrain) - Miraidon
        elif ability == "hadron-engine" and modifiers.terrain == "electric":
            if not is_physical:
                attack_stat = apply_mod(attack_stat, MOD_HADRON)

    # Embody Aspect (Ogerpon): +1 to a specific stat based on mask form
    # This is a stat stage boost that activates on entry
    # - Teal Mask: +1 Speed (doesn't affect damage calc directly)
    # - Hearthflame Mask: +1 Attack
    # - Wellspring Mask: +1 Special Defense
    # - Cornerstone Mask: +1 Defense
    #
    # NOTE: Hearthflame's +1 Attack is applied EXACTLY ONCE via the automatic
    # attack_stage bump near the top of this function (see "Embody Aspect" stage
    # bump). It must NOT also be applied here, or it would be double-counted
    # (~2.24x instead of 1.5x). Only the defender-side masks (Wellspring SpD /
    # Cornerstone Def) are applied here, since there is no stage bump for those.
    if modifiers.defender_ability:
        def_ability = normalize_ability(modifiers.defender_ability)
        if def_ability == "embody-aspect":
            def_item = normalize_item(modifiers.defender_item or "")
            if def_item == "wellspring-mask" and not is_physical:
                # +1 Special Defense stage = floor(stat * 3 / 2)
                defense_stat = apply_stat_stage(defense_stat, 1)
            elif def_item == "cornerstone-mask" and is_physical:
                # +1 Defense stage = floor(stat * 3 / 2)
                defense_stat = apply_stat_stage(defense_stat, 1)

    # Commander ability (Dondozo + Tatsugiri combo)
    # When Commander is active, Dondozo's Attack, Defense, SpA, SpD, and Speed are doubled
    # For offensive calcs: doubles Dondozo's attacking stat (Attack or SpA)
    # For defensive calcs: doubles Dondozo's defensive stat (Defense or SpD)
    commander_boost_applied = False
    if modifiers.commander_active:
        attack_stat = apply_mod(attack_stat, MOD_STAT_DOUBLE)
        commander_boost_applied = True

    # Defender has Commander active - doubles their defensive stat
    if modifiers.defender_commander_active:
        defense_stat = apply_mod(defense_stat, MOD_STAT_DOUBLE)

    # Apply Ruin abilities (field effects, NOT stat stages).
    # These always apply even on critical hits because crits only ignore
    # stat stage changes, not ability-based multipliers.
    # Sword of Ruin (Chien-Pao): Lowers foe Defense to 0.75x
    if modifiers.sword_of_ruin and is_physical:
        defense_stat = apply_mod(defense_stat, MOD_RUIN)

    # Beads of Ruin (Chi-Yu): Lowers foe Special Defense to 0.75x
    if modifiers.beads_of_ruin and not is_physical:
        defense_stat = apply_mod(defense_stat, MOD_RUIN)

    # Tablets of Ruin (Wo-Chien): Lowers foe Attack to 0.75x
    if modifiers.tablets_of_ruin and is_physical:
        attack_stat = apply_mod(attack_stat, MOD_RUIN)

    # Vessel of Ruin (Ting-Lu): Lowers foe Special Attack to 0.75x
    if modifiers.vessel_of_ruin and not is_physical:
        attack_stat = apply_mod(attack_stat, MOD_RUIN)

    # Apply Protosynthesis/Quark Drive boosts (1.3x, or 1.5x for Speed)
    # These boost the attacker's relevant stat if it matches the boosted stat
    for boost_stat in [modifiers.protosynthesis_boost, modifiers.quark_drive_boost]:
        if boost_stat:
            boost_mod = MOD_PARADOX_1_5 if boost_stat == "speed" else MOD_PARADOX_1_3
            if boost_stat == "attack" and is_physical:
                attack_stat = apply_mod(attack_stat, boost_mod)
            elif boost_stat == "special_attack" and not is_physical:
                attack_stat = apply_mod(attack_stat, boost_mod)

    # Apply defender's Protosynthesis/Quark Drive boosts
    for boost_stat in [modifiers.defender_protosynthesis_boost, modifiers.defender_quark_drive_boost]:
        if boost_stat:
            boost_mod = MOD_PARADOX_1_5 if boost_stat == "speed" else MOD_PARADOX_1_3
            if boost_stat == "defense" and is_physical:
                defense_stat = apply_mod(defense_stat, boost_mod)
            elif boost_stat == "special_defense" and not is_physical:
                defense_stat = apply_mod(defense_stat, boost_mod)

    # Apply Assault Vest (1.5x SpD for special moves)
    if modifiers.defender_item:
        def_item = normalize_item(modifiers.defender_item)
        if def_item == "assault-vest" and not is_physical:
            defense_stat = apply_mod(defense_stat, MOD_ASSAULT_VEST)

    # Get base power (may be variable for special moves)
    power = move.power

    # Weather Ball doubles power in weather (50 -> 100)
    if weather_ball_boosted:
        power = power * 2

    # Calculate variable base power for special moves (Gyro Ball, Eruption, etc.)
    if special_move_data:
        power = _calculate_variable_bp(
            move_name_normalized,
            power,
            special_move_data,
            attacker_stats.get("speed", 100),  # Use calculated speed stats
            defender_stats.get("speed", 100),
            modifiers,
        )

    # Pre-compute type effectiveness here (before the base-power chain) because
    # Collision Course / Electro Drift's 1.3333x super-effective boost is a
    # BASE-POWER modifier in Showdown and needs type_eff available now.
    defender_types = defender.types
    if modifiers.defender_tera_active and modifiers.defender_tera_type:
        defender_types = [modifiers.defender_tera_type]
    type_eff = get_type_effectiveness(effective_move_type, defender_types)

    # Tera Shell (all hits not very effective at full HP) - Terapagos
    if modifiers.defender_ability:
        def_ability_pre = normalize_ability(modifiers.defender_ability)
        if def_ability_pre == "tera-shell" and modifiers.defender_at_full_hp:
            if type_eff > 0:
                type_eff = 0.5

    # Mind's Eye / Scrappy: Normal and Fighting hit Ghost types
    if modifiers.attacker_ability:
        att_ability_pre = normalize_ability(modifiers.attacker_ability)
        if att_ability_pre in ("minds-eye", "scrappy") and type_eff == 0:
            if effective_move_type in ("Normal", "Fighting") and "Ghost" in defender_types:
                type_eff = 1.0

    # Collect BASE-POWER modifiers into a list. Per Showdown (gen789.ts) all
    # base-power mods are chained together and applied to `power` exactly ONCE
    # via poke_round, BEFORE the base-damage formula. Applying them per-step
    # (each with its own poke_round) produces off-by-one errors when several
    # stack (e.g. Tough Claws + type-boost item).
    bp_mods: list[int] = []

    # Apply power modifiers from abilities (Technician, etc.)
    if modifiers.attacker_ability:
        ability = normalize_ability(modifiers.attacker_ability)
        if ability == "technician" and power <= 60:
            bp_mods.append(MOD_CHOICE_BOOST)  # 1.5x
        elif ability == "sheer-force" and move.effect_chance:
            bp_mods.append(MOD_SHEER_FORCE)  # 1.3x (5325/4096)
        elif ability == "tough-claws" and move.makes_contact:
            bp_mods.append(MOD_TOUGH_CLAWS)
        elif ability == "iron-fist" and normalize_move(move.name) in PUNCH_MOVES:
            bp_mods.append(MOD_IRON_FIST)
        # Rocky Payload (1.5x Rock damage) - Ogerpon-Cornerstone
        elif ability == "rocky-payload" and effective_move_type == "Rock":
            bp_mods.append(MOD_ROCKY_PAYLOAD)
        # Sharpness (1.5x slicing moves) - Gallade, Kartana, Samurott-Hisui
        elif ability == "sharpness" and normalize_move(move.name) in SLICING_MOVES:
            bp_mods.append(MOD_SHARPNESS)
        # Strong Jaw (1.5x biting moves) - Dracovish, Tyrantrum, Boltund
        elif ability == "strong-jaw" and normalize_move(move.name) in BITING_MOVES:
            bp_mods.append(MOD_STRONG_JAW)
        # Supreme Overlord (+10% per fainted ally, up to +50%) - Kingambit
        elif ability == "supreme-overlord" and modifiers.supreme_overlord_count > 0:
            # +10% per ally = 410/4096 per ally
            boost = 4096 + (410 * min(5, modifiers.supreme_overlord_count))
            bp_mods.append(boost)
        # Tinted Lens (2x damage on resisted hits) - handled in final modifiers
        elif ability == "tinted-lens":
            pass  # Applied as a FINAL modifier after type effectiveness
        # Mega Launcher (1.5x pulse moves) - Blastoise, Clawitzer
        elif ability == "mega-launcher" and move_name_normalized in PULSE_MOVES:
            bp_mods.append(MOD_MEGA_LAUNCHER)
        # Reckless (1.2x recoil moves) - Bouffalant, Staraptor
        elif ability == "reckless" and move_name_normalized in RECOIL_MOVES:
            bp_mods.append(MOD_RECKLESS)
        # Sand Force (1.3x Ground/Rock/Steel in sand) - Excadrill, Landorus
        elif ability == "sand-force" and modifiers.weather == "sand":
            if effective_move_type in ("Ground", "Rock", "Steel"):
                bp_mods.append(MOD_SAND_FORCE)
        # Steely Spirit (1.5x Steel moves) - Perrserker, Duraludon
        elif ability == "steely-spirit" and effective_move_type == "Steel":
            bp_mods.append(MOD_STEELY_SPIRIT)
        # Transistor (1.5x Electric in Gen 9) - Regieleki
        elif ability == "transistor" and effective_move_type == "Electric":
            bp_mods.append(MOD_TRANSISTOR)
        # Dragon's Maw (1.5x Dragon) - Regidrago
        elif ability == "dragons-maw" and effective_move_type == "Dragon":
            bp_mods.append(MOD_DRAGONS_MAW)
        # Water Bubble (2x Water moves) - Araquanid
        elif ability == "water-bubble" and effective_move_type == "Water":
            bp_mods.append(MOD_WATER_BUBBLE_ATK)
        # Punk Rock (1.3x sound moves) - Toxtricity
        elif ability == "punk-rock" and move_name_normalized in SOUND_MOVES:
            bp_mods.append(MOD_PUNK_ROCK_ATK)
        # Analytic (1.3x when moving last) - Magnezone, Porygon-Z
        elif ability == "analytic" and modifiers.moving_last:
            bp_mods.append(MOD_ANALYTIC)

    # Ally Steely Spirit boost (1.5x Steel if ally has Steely Spirit)
    if modifiers.ally_steely_spirit and effective_move_type == "Steel":
        bp_mods.append(MOD_STEELY_SPIRIT)

    # Apply -ate ability boost (1.2x) if Normal move was converted
    if ate_ability_boost:
        bp_mods.append(MOD_ATE_ABILITY)

    # Helping Hand (1.5x) is a BASE-POWER modifier in Showdown.
    if modifiers.helping_hand:
        bp_mods.append(MOD_HELPING_HAND)

    # Tera BP boost: Tera-type moves with base power < 60 are boosted to 60.
    # This is a flat floor on the raw base power (read before bp mods are
    # chained, matching the existing behaviour and Showdown's basePower edit).
    if modifiers.tera_active and modifiers.tera_type:
        tera_type = modifiers.tera_type.capitalize()
        if effective_move_type == tera_type:
            is_multi_hit = multi_hit_info is not None
            is_priority = move.priority > 0
            if power < 60 and not is_multi_hit and not is_priority:
                power = 60

    # Type-boosting items (Charcoal, plates) are base-power mods in Showdown.
    bp_item_mod_4096 = _get_type_boost_item_mod_4096(modifiers.attacker_item, effective_move_type)
    if bp_item_mod_4096 != MOD_NEUTRAL:
        bp_mods.append(bp_item_mod_4096)

    # Ogerpon mask boost (1.2x to ALL moves, not just type-matching).
    attacker_name = attacker.name if attacker else None
    ogerpon_mask_mod_4096 = _get_ogerpon_mask_boost_4096(modifiers.attacker_item, attacker_name)
    if ogerpon_mask_mod_4096 != MOD_NEUTRAL:
        bp_mods.append(ogerpon_mask_mod_4096)

    # Muscle Band (1.1x physical) / Wise Glasses (1.1x special) / Punching Glove
    # (1.1x punch) are base-power mods in Showdown, NOT final-damage mods.
    if modifiers.attacker_item:
        att_item_bp = normalize_item(modifiers.attacker_item)
        if att_item_bp == "muscle-band" and is_physical:
            bp_mods.append(MOD_MUSCLE_BAND)
        elif att_item_bp == "wise-glasses" and not is_physical:
            bp_mods.append(MOD_WISE_GLASSES)
        if att_item_bp == "punching-glove" and move_name_normalized in PUNCH_MOVES:
            bp_mods.append(MOD_PUNCHING_GLOVE)

    # Terrain boost / Misty nerf / Psyblade override are ALL base-power mods in
    # Showdown (gen789.ts) — they must multiply `power` before the base-damage
    # formula, not the post-formula base_damage.
    terrain_mod_4096 = _get_terrain_mod_4096(
        modifiers.terrain,
        effective_move_type,
        modifiers.attacker_grounded,
        modifiers.defender_grounded,
    )
    # Psyblade: 1.5x in Psychic Terrain (overrides the standard ~1.3x boost)
    if move_name_normalized == "psyblade" and modifiers.terrain == "psychic":
        terrain_mod_4096 = 6144  # 1.5x
    if terrain_mod_4096 != MOD_NEUTRAL:
        bp_mods.append(terrain_mod_4096)

    # Collision Course / Electro Drift: 1.3333x on super-effective hits is a
    # base-power mod in Showdown.
    if move_name_normalized in ("collision-course", "electro-drift") and type_eff > 1.0:
        bp_mods.append(5461)  # ~1.3333x

    # Apply ALL collected base-power mods at once (chain, then poke_round once).
    if bp_mods:
        chained_bp = chain_mods(bp_mods)
        power = max(1, poke_round(power * chained_bp / 4096))

    # Level constant for level 50: floor(2*50/5+2) = 22
    level_factor = 22

    # Base damage formula
    # floor(floor(floor(level_factor * power * atk / def) / 50) + 2)
    base_damage = math.floor(
        math.floor(
            math.floor(level_factor * power * attack_stat / defense_stat) / 50
        ) + 2
    )

    # Track applied modifiers for details
    applied_mods = []

    # 1. Spread move modifier (3072/4096 = 0.75x in doubles when hitting multiple)
    if move.is_spread and modifiers.is_doubles and modifiers.multiple_targets:
        base_damage = apply_mod(base_damage, MOD_SPREAD)
        applied_mods.append("Spread (0.75x)")

    # 2. Weather modifier (6144/4096 = 1.5x boost, 2048/4096 = 0.5x nerf)
    weather_mod_4096 = _get_weather_mod_4096(modifiers.weather, effective_move_type)
    if weather_mod_4096 != MOD_NEUTRAL:
        base_damage = apply_mod(base_damage, weather_mod_4096)
        weather_mult = weather_mod_4096 / 4096
        applied_mods.append(f"Weather ({weather_mult:.1f}x)")

    # NOTE: Terrain (boost / Misty nerf / Psyblade override) is now applied as a
    # BASE-POWER modifier earlier in this function (Showdown gen789.ts), not here.

    # 3. Critical hit (6144/4096 = 1.5x in Gen 9)
    if modifiers.is_critical:
        base_damage = apply_mod(base_damage, MOD_CRIT)
        applied_mods.append("Critical (1.5x)")

    # Pre-calculate STAB modifier (4096-based)
    # Pass effective_move_type to account for type-changing abilities
    stab_mod_4096 = _get_stab_mod_4096(attacker, move, modifiers, effective_move_type)

    # type_eff (and Tera Shell / Mind's Eye adjustments) were computed earlier,
    # before the base-power chain (needed for Collision Course). Reuse it here.

    # Burn must be applied as a DISCRETE floor(d/2) step (NOT in the final-mods
    # chain) — Showdown applies it as its own integer halving after type
    # effectiveness, distinct from the chained final modifiers.
    burn_applies = False
    if modifiers.attacker_burned and is_physical:
        has_guts_ability = (
            modifiers.attacker_ability and
            normalize_ability(modifiers.attacker_ability) == "guts"
        )
        if not modifiers.has_guts and not has_guts_ability and move.name.lower() != "facade":
            burn_applies = True

    # Pre-calculate final modifier chain (screens, items, abilities)
    final_mods = []

    # Screens — IGNORED on a critical hit (Reflect/Light Screen/Aurora Veil).
    if not modifiers.is_critical:
        screen_mod_4096 = _get_screen_mod_4096(modifiers, is_physical)
        if screen_mod_4096 != MOD_NEUTRAL:
            final_mods.append(screen_mod_4096)

    # Item modifiers (Life Orb, type-boosting items)
    item_mod_4096 = _get_item_mod_4096(modifiers.attacker_item, effective_move_type)
    if item_mod_4096 != MOD_NEUTRAL:
        final_mods.append(item_mod_4096)

    # Expert Belt (only if super effective)
    if modifiers.attacker_item and normalize_item(modifiers.attacker_item) == "expert-belt":
        if type_eff >= 2.0:
            final_mods.append(MOD_EXPERT_BELT)

    # Tinted Lens (2x on RESISTED hits, not immunities) - Yanmega, Butterfree.
    # This is a final-damage modifier applied after type effectiveness.
    if modifiers.attacker_ability:
        if normalize_ability(modifiers.attacker_ability) == "tinted-lens":
            if 0 < type_eff < 1.0:
                final_mods.append(MOD_TINTED_LENS)

    # Helping Hand is now applied as a base-power modifier earlier (Showdown).

    # Friend Guard (3072/4096 = 0.75x)
    if modifiers.friend_guard:
        final_mods.append(MOD_FRIEND_GUARD)

    # Defender ability effects
    if modifiers.defender_ability:
        def_ability = normalize_ability(modifiers.defender_ability)

        # Multiscale / Shadow Shield (0.5x at full HP)
        if def_ability in ("multiscale", "shadow-shield") and modifiers.defender_at_full_hp:
            final_mods.append(MOD_MULTISCALE)

        # Ice Scales (0.5x special damage)
        if def_ability == "ice-scales" and not is_physical:
            final_mods.append(MOD_ICE_SCALES)

        # Solid Rock / Filter / Prism Armor (0.75x super-effective damage)
        if def_ability in ("solid-rock", "filter", "prism-armor") and type_eff >= 2.0:
            final_mods.append(MOD_SOLID_ROCK)

        # Fluffy (0.5x contact damage, 2x Fire damage)
        if def_ability == "fluffy":
            if move.makes_contact:
                final_mods.append(MOD_FLUFFY_CONTACT)
            if effective_move_type == "Fire":
                final_mods.append(MOD_FLUFFY_FIRE)

        # Thick Fat (0.5x Fire and Ice damage)
        if def_ability == "thick-fat" and effective_move_type in ("Fire", "Ice"):
            final_mods.append(MOD_THICK_FAT)

        # Purifying Salt (0.5x Ghost damage) - Garganacl
        if def_ability == "purifying-salt" and effective_move_type == "Ghost":
            final_mods.append(MOD_PURIFYING_SALT)

        # Heatproof (0.5x Fire damage) - Bronzong
        if def_ability == "heatproof" and effective_move_type == "Fire":
            final_mods.append(MOD_HEATPROOF)

        # Water Bubble (0.5x Fire damage taken) - Araquanid
        if def_ability == "water-bubble" and effective_move_type == "Fire":
            final_mods.append(MOD_WATER_BUBBLE_DEF)

        # Dry Skin (1.25x Fire damage taken) - Toxicroak, Heliolisk
        if def_ability == "dry-skin" and effective_move_type == "Fire":
            final_mods.append(MOD_DRY_SKIN_FIRE)

        # Fur Coat (0.5x physical damage) - Alolan Persian, Furfrou
        if def_ability == "fur-coat" and is_physical:
            final_mods.append(MOD_FUR_COAT)

        # Punk Rock (0.5x sound damage taken) - Toxtricity
        if def_ability == "punk-rock" and move_name_normalized in SOUND_MOVES:
            final_mods.append(MOD_PUNK_ROCK_DEF)

        # Neuroforce (1.25x on super-effective) - Necrozma-Ultra
        # Note: This is an offensive ability for the attacker
    if modifiers.attacker_ability:
        att_ability = normalize_ability(modifiers.attacker_ability)
        if att_ability == "neuroforce" and type_eff >= 2.0:
            final_mods.append(MOD_NEUROFORCE)

    # Attacker item effects (final damage modifiers)
    # NOTE: Punching Glove / Muscle Band / Wise Glasses are now base-power mods
    # (applied earlier), matching Showdown — they are no longer final mods.
    if modifiers.attacker_item:
        att_item = normalize_item(modifiers.attacker_item)

        # Normal Gem (1.5x first Normal move - one-time use)
        if att_item == "normal-gem" and effective_move_type == "Normal":
            final_mods.append(MOD_NORMAL_GEM)

    # Defender item effects
    if modifiers.defender_item:
        def_item = normalize_item(modifiers.defender_item)

        # Resistance berries (0.5x super-effective damage of matching type)
        if def_item in RESISTANCE_BERRIES:
            berry_type = RESISTANCE_BERRIES[def_item]
            if effective_move_type == berry_type and type_eff >= 2.0:
                final_mods.append(MOD_RESISTANCE_BERRY)

    # Chain all final modifiers together
    final_mod_4096 = chain_mods(final_mods) if final_mods else MOD_NEUTRAL

    # Calculate 16 damage rolls (random factor 85-100)
    rolls = []
    damages_per_hit = []  # For multi-hit KO probability calculation

    if hit_count == 1:
        # Single-hit move: standard calculation
        for i in range(16):
            # 4. Random factor: floor(damage * random / 100)
            # Uses floor, NOT pokeRound (per Showdown implementation)
            random_factor = 85 + i
            damage = math.floor(base_damage * random_factor / 100)

            # 5. STAB (6144/4096 = 1.5x, 8192/4096 = 2.0x)
            if stab_mod_4096 != MOD_NEUTRAL:
                damage = apply_mod(damage, stab_mod_4096)

            # 6. Type effectiveness (integer multiplier, applied directly)
            # Immunities deal 0 damage (no further modifiers apply)
            if type_eff == 0:
                rolls.append(0)
                continue

            if type_eff != 1.0:
                # Type effectiveness uses floor, not pokeRound
                damage = int(damage * type_eff)

            # Burn: discrete floor(d/2) step, AFTER type effectiveness and
            # BEFORE the chained final modifiers (Showdown applies it as its own
            # integer halving, not as part of the final-mod chain).
            if burn_applies:
                damage = damage // 2

            # 7-10. Apply chained final modifiers (screens, items, etc.)
            if final_mod_4096 != MOD_NEUTRAL:
                damage = apply_mod(damage, final_mod_4096)

            # Minimum 1 damage per hit
            damage = max(1, damage)

            rolls.append(damage)
    else:
        # Multi-hit move: each hit gets independent random roll
        for i in range(16):
            # 4. Random factor: floor(damage * random / 100)
            random_factor = 85 + i
            damage_this_roll = math.floor(base_damage * random_factor / 100)

            # 5. STAB (6144/4096 = 1.5x, 8192/4096 = 2.0x)
            if stab_mod_4096 != MOD_NEUTRAL:
                damage_this_roll = apply_mod(damage_this_roll, stab_mod_4096)

            # 6. Type effectiveness (integer multiplier, applied directly)
            # Immunities deal 0 damage (no further modifiers apply)
            if type_eff == 0:
                damages_per_hit.append(0)
                continue

            if type_eff != 1.0:
                # Type effectiveness uses floor, not pokeRound
                damage_this_roll = int(damage_this_roll * type_eff)

            # Burn: discrete floor(d/2) step (see single-hit loop above).
            if burn_applies:
                damage_this_roll = damage_this_roll // 2

            # 7-10. Apply chained final modifiers (screens, items, etc.)
            if final_mod_4096 != MOD_NEUTRAL:
                damage_this_roll = apply_mod(damage_this_roll, final_mod_4096)

            # Minimum 1 damage per hit
            damage_this_roll = max(1, damage_this_roll)

            damages_per_hit.append(damage_this_roll)

        # Generate representative rolls for display
        rolls = _calculate_multi_hit_rolls(damages_per_hit, hit_count)

    # Parental Bond (Mega Kangaskhan): a single-strike damaging move hits a
    # second time at 0.25x power. The second hit runs through the same modifier
    # chain, so it lands at ~0.25x the first hit — model it as a per-roll +25%.
    # Parental Bond strikes only ONCE on spread moves, and doesn't apply to
    # status moves, already-multi-hit moves, or immune matchups.
    parental_bond = (
        modifiers.attacker_ability is not None
        and normalize_ability(modifiers.attacker_ability) == "parental-bond"
        and hit_count == 1
        and move.category != MoveCategory.STATUS
        and not move.is_spread
        and type_eff != 0
    )
    if parental_bond:
        rolls = [r + max(1, r // 4) for r in rolls]

    # Calculate results
    min_damage = min(rolls)
    max_damage = max(rolls)
    defender_hp = defender_stats["hp"]

    # Truncate to 1 decimal place (matching Showdown's behavior)
    # e.g., 98.49% becomes 98.4%, not 98.5%
    min_percent = int((min_damage / defender_hp) * 1000) / 10
    max_percent = int((max_damage / defender_hp) * 1000) / 10

    # KO calculations
    kos = sum(1 for r in rolls if r >= defender_hp)
    is_guaranteed_ohko = kos == 16
    is_possible_ohko = kos > 0

    # Calculate detailed KO probabilities
    if hit_count > 1 and type_eff != 0:
        # Use exact probability calculation for multi-hit moves
        ko_probs = calculate_multi_hit_ko_probability(
            damages_per_hit, hit_count, defender_hp
        )
    else:
        # Use standard probability calculation for single-hit moves
        ko_probs = calculate_ko_probability(rolls, defender_hp)

    # Check for immunity (all rolls are 0)
    is_immune = max_damage == 0

    if is_immune:
        ko_chance = "Immune (0 damage)"
    else:
        # Use the detailed verdict from probability calculation
        ko_chance = ko_probs.verdict

    # Add STAB to applied mods
    if stab_mod_4096 != MOD_NEUTRAL:
        if stab_mod_4096 == MOD_STAB_TERA_ADAPT:  # 9216 = 2.25x
            applied_mods.append("STAB (2.25x - Tera+Adaptability)")
        elif stab_mod_4096 == MOD_STAB_BOOSTED:
            applied_mods.append("STAB (2.0x - Tera/Adaptability)")
        else:
            applied_mods.append("STAB (1.5x)")

    # Add type effectiveness to mods. Use the type_eff computed at the top of
    # the function (which already reflects the Tera Shell clamp and Mind's Eye /
    # Scrappy override the rolls used) — do NOT recompute the raw value here, or
    # the reported effectiveness contradicts the actual damage.
    if type_eff == 0:
        applied_mods.append("Immune (0x)")
    elif type_eff == 0.25:
        applied_mods.append("4x Resist (0.25x)")
    elif type_eff == 0.5:
        applied_mods.append("Resist (0.5x)")
    elif type_eff == 2:
        applied_mods.append("Super Effective (2x)")
    elif type_eff == 4:
        applied_mods.append("4x Super Effective (4x)")

    # Add multi-hit info to mods
    if hit_count > 1:
        crit_note = " (always crits)" if always_crit else ""
        applied_mods.append(f"Multi-hit ({hit_count} hits{crit_note})")

    if parental_bond:
        applied_mods.append("Parental Bond (2nd hit 0.25x)")

    # Add Commander to mods
    if commander_boost_applied:
        applied_mods.append("Commander (2x all stats)")

    return DamageResult(
        min_damage=min_damage,
        max_damage=max_damage,
        min_percent=min_percent,
        max_percent=max_percent,
        rolls=rolls,
        defender_hp=defender_hp,
        ko_chance=ko_chance,
        is_guaranteed_ohko=is_guaranteed_ohko,
        is_possible_ohko=is_possible_ohko,
        details={
            "attacker_stat": attack_stat,
            "defender_stat": defense_stat,
            "base_power": power,
            "type_effectiveness": type_eff,
            "modifiers_applied": applied_mods,
            "hit_count": hit_count,
            "always_crit": always_crit,
        },
        ko_probability=ko_probs if not is_immune else None
    )


# =============================================================================
# 4096-based modifier helper functions
# =============================================================================

def _get_weather_mod_4096(weather: str | None, move_type: str) -> int:
    """Get weather modifier as 4096-based value.

    Handles regular weather (sun, rain) and primal weather (harsh_sun, heavy_rain).
    Primal weather completely nullifies opposing type moves (returns 0).
    """
    if not weather:
        return MOD_NEUTRAL

    weather = weather.lower().replace("-", "_")
    move_type = move_type.capitalize()

    if weather == "sun":
        if move_type == "Fire":
            return MOD_WEATHER_BOOST  # 6144/4096 = 1.5x
        elif move_type == "Water":
            return MOD_WEATHER_NERF   # 2048/4096 = 0.5x
    elif weather == "rain":
        if move_type == "Water":
            return MOD_WEATHER_BOOST
        elif move_type == "Fire":
            return MOD_WEATHER_NERF
    elif weather == "harsh_sun":
        # Primal Groudon's Desolate Land
        if move_type == "Fire":
            return MOD_WEATHER_BOOST  # 1.5x boost to Fire
        elif move_type == "Water":
            return 0  # Water moves completely fail
    elif weather == "heavy_rain":
        # Primal Kyogre's Primordial Sea
        if move_type == "Water":
            return MOD_WEATHER_BOOST  # 1.5x boost to Water
        elif move_type == "Fire":
            return 0  # Fire moves completely fail

    return MOD_NEUTRAL


def _get_terrain_mod_4096(
    terrain: str | None,
    move_type: str,
    attacker_grounded: bool,
    defender_grounded: bool = True
) -> int:
    """Get terrain modifier as 4096-based value.

    Handles terrain boosts (Electric, Grassy, Psychic) and Misty Terrain's
    Dragon-type damage reduction.

    Args:
        terrain: Active terrain (electric, grassy, psychic, misty)
        move_type: Type of the attacking move
        attacker_grounded: Whether the attacker is grounded (for boosts)
        defender_grounded: Whether the defender is grounded (for Misty reduction)
    """
    if not terrain:
        return MOD_NEUTRAL

    terrain = terrain.lower()
    move_type = move_type.capitalize()

    # Terrain boosts are 5325/4096 (~1.3x) in Gen 9
    MOD_TERRAIN_BOOST = 5325
    # Misty Terrain reduces Dragon damage by 50% = 2048/4096
    MOD_TERRAIN_NERF = 2048

    # Terrain boosts only apply if attacker is grounded
    if attacker_grounded:
        if terrain == "electric" and move_type == "Electric":
            return MOD_TERRAIN_BOOST
        elif terrain == "grassy" and move_type == "Grass":
            return MOD_TERRAIN_BOOST
        elif terrain == "psychic" and move_type == "Psychic":
            return MOD_TERRAIN_BOOST

    # Misty Terrain reduces Dragon damage if DEFENDER is grounded
    if terrain == "misty" and move_type == "Dragon" and defender_grounded:
        return MOD_TERRAIN_NERF

    return MOD_NEUTRAL


def _get_screen_mod_4096(modifiers: DamageModifiers, is_physical: bool) -> int:
    """Get screen modifier as 4096-based value.

    Handles Reflect (physical), Light Screen (special), and Aurora Veil (both).
    Aurora Veil is checked first and applies to both physical and special moves.
    Critical hits ignore screens (handled elsewhere in damage calc).
    """
    # Aurora Veil protects against both physical and special
    if modifiers.aurora_veil_up:
        if modifiers.is_doubles:
            return MOD_SCREEN_DOUBLES  # 2732/4096 = ~0.667x
        else:
            return MOD_SCREEN_SINGLES  # 2048/4096 = 0.5x

    # Reflect for physical, Light Screen for special
    has_screen = (is_physical and modifiers.reflect_up) or (not is_physical and modifiers.light_screen_up)

    if not has_screen:
        return MOD_NEUTRAL

    if modifiers.is_doubles:
        return MOD_SCREEN_DOUBLES  # 2732/4096 = ~0.667x
    else:
        return MOD_SCREEN_SINGLES  # 2048/4096 = 0.5x


def _get_ogerpon_mask_boost_4096(item: str | None, attacker_name: str | None) -> int:
    """
    Get Ogerpon mask boost modifier for BASE POWER.

    Ogerpon's masks (Hearthflame, Wellspring, Cornerstone) boost ALL moves by 1.2x,
    not just type-matching moves. This is different from regular type-boosting items.
    Note: Teal Mask provides NO boost.

    The boost only works when Ogerpon holds its corresponding mask.
    """
    if not item or not attacker_name:
        return MOD_NEUTRAL

    item = normalize_item(item)
    attacker = attacker_name.lower().replace(" ", "-")

    # Only Ogerpon gets the mask boost
    if not attacker.startswith("ogerpon"):
        return MOD_NEUTRAL

    # Only these three masks provide the 1.2x boost to ALL moves
    # Teal Mask provides NO boost
    ogerpon_masks = {
        "hearthflame-mask",
        "wellspring-mask",
        "cornerstone-mask",
    }

    if item in ogerpon_masks:
        return MOD_TYPE_BOOST  # 4915/4096 = ~1.2x to ALL moves

    return MOD_NEUTRAL


def _get_type_boost_item_mod_4096(item: str | None, move_type: str) -> int:
    """
    Get type-boosting item modifier for BASE POWER (not final damage).

    In Pokemon, type-boosting items like Charcoal and Mystic Water
    are applied as base power modifiers, NOT final damage modifiers.
    This matches Showdown's bpMods behavior.

    Note: Ogerpon masks are handled separately by _get_ogerpon_mask_boost_4096()
    because they boost ALL moves, not just type-matching moves.
    """
    if not item:
        return MOD_NEUTRAL

    item = normalize_item(item)
    move_type = move_type.capitalize()

    # Type-boosting items (4915/4096 = ~1.2x) - applied to BASE POWER
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
        # Note: Ogerpon masks are NOT here - they boost ALL moves, handled separately
    }

    if item in type_items and type_items[item] == move_type:
        return MOD_TYPE_BOOST  # 4915/4096 = ~1.2x

    # Plates (same boost as type items)
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
        return MOD_TYPE_BOOST

    return MOD_NEUTRAL


def _get_item_mod_4096(item: str | None, move_type: str) -> int:
    """
    Get item FINAL DAMAGE modifier as 4096-based value.

    Note: Type-boosting items (Charcoal, masks, plates) are NOT included here
    because they are applied to base power instead. Only items that modify
    final damage (like Life Orb) go here.
    """
    if not item:
        return MOD_NEUTRAL

    item = normalize_item(item)

    # Life Orb - final damage modifier
    if item == "life-orb":
        return MOD_LIFE_ORB  # 5324/4096 = ~1.3x

    return MOD_NEUTRAL


def _get_stab_mod_4096(
    attacker: PokemonBuild,
    move: Move,
    modifiers: DamageModifiers,
    effective_move_type: str | None = None
) -> int:
    """Calculate STAB modifier as 4096-based value including Tera considerations.

    Tera STAB mechanics (Gen 9):
    - Tera into same type: 2x STAB (or 2.25x with Adaptability)
    - Tera into new type: 1.5x STAB (or 2x with Adaptability)
    - Original type moves still get 1.5x when Terastallized
    - Adaptability only boosts moves matching the Tera type when Terastallized

    Args:
        attacker: The attacking Pokemon
        move: The move being used
        modifiers: Damage modifiers
        effective_move_type: The effective type of the move (after type-changing abilities)
                           If None, uses move.type
    """
    # Use effective type if provided (for type-changing abilities like Aerilate)
    move_type = (effective_move_type or move.type).capitalize()
    original_types = [t.capitalize() for t in attacker.types]

    tera_type = None
    if modifiers.tera_active and modifiers.tera_type:
        tera_type = modifiers.tera_type.capitalize()

    # Check if move type matches Tera type
    if tera_type:
        if move_type == tera_type:
            if move_type in original_types:
                # Tera into same type = 2x STAB, or 2.25x with Adaptability
                if modifiers.has_adaptability:
                    return MOD_STAB_TERA_ADAPT  # 2.25x (9216/4096)
                return MOD_STAB_BOOSTED  # 2x (8192/4096)
            else:
                # Tera into new type = 1.5x, or 2x with Adaptability
                if modifiers.has_adaptability:
                    return MOD_STAB_BOOSTED  # 2x (8192/4096)
                return MOD_STAB  # 1.5x (6144/4096)
        elif move_type in original_types:
            # Original type moves still get 1.5x STAB when Terastallized
            # Note: Adaptability does NOT boost original type moves when Tera is active
            return MOD_STAB
    else:
        # Not Terastallized
        if move_type in original_types:
            if modifiers.has_adaptability:
                return MOD_STAB_BOOSTED  # 2x with Adaptability
            return MOD_STAB  # 1.5x normal STAB

    return MOD_NEUTRAL


def calculate_ko_threshold(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move: Move,
    modifiers: Optional[DamageModifiers] = None,
    target_ko_chance: float = 100.0
) -> Optional[dict]:
    """
    Find minimum EVs needed to achieve a certain KO probability.

    Args:
        attacker: Attacker base build (EVs will be varied)
        defender: Defender build
        move: Move being used
        modifiers: Battle conditions
        target_ko_chance: Target KO probability (100 = guaranteed)

    Returns:
        Dict with required EVs and resulting calc, or None if impossible
    """
    from ..models.pokemon import EVSpread, StatPointSpread
    from .stats_champions import SP_BREAKPOINTS_LV50

    is_physical = move.category == MoveCategory.PHYSICAL
    stat_name = "attack" if is_physical else "special_attack"

    # Champions (Reg MA) builds invest Stat Points (0-32 per stat / 66 total),
    # not EVs. calculate_all_stats ignores evs for champions, so sweeping EVs
    # would yield identical damage every iteration. Sweep SP breakpoints and
    # return the result in SP units instead.
    if attacker.format_system == "champions":
        for sp in SP_BREAKPOINTS_LV50:
            test_sps = StatPointSpread()
            if is_physical:
                test_sps.attack = sp
            else:
                test_sps.special_attack = sp

            test_attacker = attacker.model_copy()
            test_attacker.sps = test_sps

            result = calculate_damage(test_attacker, defender, move, modifiers)

            kos = sum(1 for r in result.rolls if r >= result.defender_hp)
            ko_pct = (kos / 16) * 100

            if ko_pct >= target_ko_chance:
                return {
                    "sps_needed": sp,
                    "stat_name": stat_name,
                    "ko_chance": ko_pct,
                    "damage_range": result.damage_range,
                    "result": result,
                }
        return None  # Cannot achieve target KO within the 32 SP cap

    # Use valid level 50 EV breakpoints (0, 4, 12, 20, 28...)
    for ev in EV_BREAKPOINTS_LV50:
        # Create modified attacker with test EVs
        test_evs = EVSpread()
        if is_physical:
            test_evs.attack = ev
        else:
            test_evs.special_attack = ev

        test_attacker = attacker.model_copy()
        test_attacker.evs = test_evs

        result = calculate_damage(test_attacker, defender, move, modifiers)

        # Calculate actual KO chance from rolls
        kos = sum(1 for r in result.rolls if r >= result.defender_hp)
        ko_pct = (kos / 16) * 100

        if ko_pct >= target_ko_chance:
            return {
                "evs_needed": ev,
                "stat_name": stat_name,
                "ko_chance": ko_pct,
                "damage_range": result.damage_range,
                "result": result
            }

    return None  # Cannot achieve target KO


def calculate_bulk_threshold(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move: Move,
    modifiers: Optional[DamageModifiers] = None,
    target_survival_chance: float = 100.0
) -> Optional[dict]:
    """
    Find minimum bulk EVs to survive an attack.

    Args:
        attacker: Attacker build
        defender: Defender base build (EVs will be varied)
        move: Move being used
        modifiers: Battle conditions
        target_survival_chance: Target survival % (100 = guaranteed survive)

    Returns:
        Dict with required HP/Def EVs and resulting calc (minimum total EVs)
    """
    from ..models.pokemon import EVSpread, StatPointSpread
    from .stats_champions import SP_BREAKPOINTS_LV50

    is_physical = move.category == MoveCategory.PHYSICAL
    def_stat_name = "defense" if is_physical else "special_defense"

    # Champions (Reg MA) defenders invest Stat Points (0-32 per stat / 66
    # total), not EVs. Sweep SP breakpoints and return the result in SP units.
    if defender.format_system == "champions":
        best_sp_result = None
        best_total_sps = float("inf")
        for hp_sp in SP_BREAKPOINTS_LV50:
            for def_sp in SP_BREAKPOINTS_LV50:
                total = hp_sp + def_sp
                if total > 66:
                    continue
                if total > best_total_sps:
                    continue

                test_sps = StatPointSpread(hp=hp_sp)
                if is_physical:
                    test_sps.defense = def_sp
                else:
                    test_sps.special_defense = def_sp

                test_defender = defender.model_copy()
                test_defender.sps = test_sps

                result = calculate_damage(attacker, test_defender, move, modifiers)

                survives = sum(1 for r in result.rolls if r < result.defender_hp)
                survival_pct = (survives / 16) * 100

                if survival_pct >= target_survival_chance:
                    # Prefer lower total SP, or higher HP when totals are equal.
                    if total < best_total_sps or (
                        total == best_total_sps and hp_sp > best_sp_result["hp_sps"]
                    ):
                        best_total_sps = total
                        best_sp_result = {
                            "hp_sps": hp_sp,
                            "def_sps": def_sp,
                            "def_stat_name": def_stat_name,
                            "survival_chance": survival_pct,
                            "damage_range": result.damage_range,
                            "result": result,
                        }
        return best_sp_result  # None if no SP combination achieves survival

    best_result = None
    best_total_evs = float('inf')

    # Test all valid EV combinations to find minimum total investment
    for hp_ev in EV_BREAKPOINTS_LV50:
        for def_ev in EV_BREAKPOINTS_LV50:
            total = hp_ev + def_ev
            if total > 508:
                continue

            # Skip if we can't improve on best found
            if total > best_total_evs:
                continue

            test_evs = EVSpread(hp=hp_ev)
            if is_physical:
                test_evs.defense = def_ev
            else:
                test_evs.special_defense = def_ev

            test_defender = defender.model_copy()
            test_defender.evs = test_evs

            result = calculate_damage(attacker, test_defender, move, modifiers)

            # Calculate survival chance
            survives = sum(1 for r in result.rolls if r < result.defender_hp)
            survival_pct = (survives / 16) * 100

            if survival_pct >= target_survival_chance:
                # Found a valid solution - check if it's better
                # Prefer lower total EVs, or higher HP when totals are equal
                if total < best_total_evs or (total == best_total_evs and hp_ev > best_result["hp_evs"]):
                    best_total_evs = total
                    best_result = {
                        "hp_evs": hp_ev,
                        "def_evs": def_ev,
                        "def_stat_name": def_stat_name,
                        "survival_chance": survival_pct,
                        "damage_range": result.damage_range,
                        "result": result
                    }

    return best_result  # None if no combination achieves survival
