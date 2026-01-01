"""Move data models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MoveCategory(str, Enum):
    """Move damage category."""
    PHYSICAL = "physical"
    SPECIAL = "special"
    STATUS = "status"


# Target types that indicate spread moves (hit multiple Pokemon)
SPREAD_TARGETS = [
    "all-opponents",
    "all-other-pokemon",
    "all-pokemon",
    "all-adjacent-foes",
    "all-adjacent",
]


class SecondaryEffect(str, Enum):
    """Possible secondary effects of moves."""
    BURN = "burn"
    FREEZE = "freeze"
    PARALYSIS = "paralysis"
    POISON = "poison"
    BADLY_POISON = "badly_poison"
    SLEEP = "sleep"
    CONFUSION = "confusion"
    FLINCH = "flinch"
    STAT_DROP = "stat_drop"
    STAT_BOOST = "stat_boost"


class Move(BaseModel):
    """Pokemon move data."""
    name: str
    type: str  # e.g., "fire", "water"
    category: MoveCategory
    power: Optional[int] = None  # None for status moves
    accuracy: Optional[int] = None  # None for moves that never miss
    pp: int = 5
    priority: int = 0
    target: str = "selected-pokemon"
    effect_chance: Optional[int] = None
    makes_contact: bool = False
    secondary_effect: Optional[str] = None  # e.g., "burn", "paralysis"
    effect_target: str = "defender"  # "defender", "attacker", "both"
    # Multi-hit move support
    min_hits: int = 1  # Minimum hits (e.g., 2 for Bullet Seed)
    max_hits: int = 1  # Maximum hits (e.g., 5 for Bullet Seed)
    always_crit: bool = False  # Surging Strikes always crits

    @property
    def is_spread(self) -> bool:
        """Check if move hits multiple targets in doubles."""
        return self.target in SPREAD_TARGETS

    @property
    def is_damaging(self) -> bool:
        """Check if move deals damage."""
        return self.category != MoveCategory.STATUS and self.power is not None and self.power > 0

    @property
    def has_secondary_effect(self) -> bool:
        """Check if move has a notable secondary effect."""
        return self.secondary_effect is not None and self.effect_chance is not None and self.effect_chance > 0

    @property
    def is_multi_hit(self) -> bool:
        """Check if move hits multiple times."""
        return self.max_hits > 1

    @property
    def expected_hits(self) -> float:
        """Get expected number of hits (for damage calculation)."""
        if self.min_hits == self.max_hits:
            return self.min_hits
        # For 2-5 hit moves, average is 3.167 (weighted by probability)
        if self.min_hits == 2 and self.max_hits == 5:
            return 3.167
        # For 1-10 hit moves (Population Bomb), average is 5.5
        if self.min_hits == 1 and self.max_hits == 10:
            return 5.5
        return (self.min_hits + self.max_hits) / 2


# Common priority moves for reference
PRIORITY_MOVES = {
    # +5
    "helping-hand": 5,
    # +4
    "protect": 4,
    "detect": 4,
    "endure": 4,
    "spiky-shield": 4,
    "baneful-bunker": 4,
    "silk-trap": 4,
    # +3
    "fake-out": 3,
    "quick-guard": 3,
    "wide-guard": 3,
    "crafty-shield": 3,
    # +2
    "extreme-speed": 2,
    "feint": 2,
    "first-impression": 2,
    "accelerock": 2,
    # +1
    "aqua-jet": 1,
    "bullet-punch": 1,
    "ice-shard": 1,
    "mach-punch": 1,
    "quick-attack": 1,
    "shadow-sneak": 1,
    "sucker-punch": 1,
    "vacuum-wave": 1,
    "water-shuriken": 1,
    "grassy-glide": 1,  # Only in grassy terrain
    "jet-punch": 1,
    # -1
    "vital-throw": -1,
    # -3
    "focus-punch": -3,
    # -5
    "counter": -5,
    "mirror-coat": -5,
    # -6
    "roar": -6,
    "whirlwind": -6,
    "dragon-tail": -6,
    "circle-throw": -6,
    # -7
    "trick-room": -7,
}


# Common spread moves in VGC
COMMON_SPREAD_MOVES = [
    "earthquake",
    "rock-slide",
    "heat-wave",
    "dazzling-gleam",
    "discharge",
    "surf",
    "muddy-water",
    "snarl",
    "icy-wind",
    "electroweb",
    "bulldoze",
    "breaking-swipe",
    "lava-plume",
    "hyper-voice",
    "blizzard",
]


# Secondary effects database for common VGC moves
# Format: {move_name: (effect_type, chance)}
MOVE_SECONDARY_EFFECTS: dict[str, tuple[str, int]] = {
    # High-chance burns (30%+)
    "sacred-fire": ("burn", 50),
    "scald": ("burn", 30),
    "lava-plume": ("burn", 30),
    "searing-shot": ("burn", 30),
    "inferno": ("burn", 100),  # Always burns if hits
    "will-o-wisp": ("burn", 100),  # Status move
    "blue-flare": ("burn", 20),
    "steam-eruption": ("burn", 30),

    # Lower-chance burns (10%)
    "flamethrower": ("burn", 10),
    "fire-blast": ("burn", 10),
    "heat-wave": ("burn", 10),
    "ember": ("burn", 10),
    "fire-punch": ("burn", 10),
    "blaze-kick": ("burn", 10),
    "mystical-fire": ("burn", 10),

    # Paralysis
    "thunder": ("paralysis", 30),
    "thunderbolt": ("paralysis", 10),
    "discharge": ("paralysis", 30),
    "nuzzle": ("paralysis", 100),
    "thunder-wave": ("paralysis", 100),
    "body-slam": ("paralysis", 30),
    "bounce": ("paralysis", 30),
    "force-palm": ("paralysis", 30),
    "spark": ("paralysis", 30),
    "thunder-punch": ("paralysis", 10),
    "thunder-fang": ("paralysis", 10),
    "lick": ("paralysis", 30),
    "stun-spore": ("paralysis", 100),
    "zap-cannon": ("paralysis", 100),
    "glare": ("paralysis", 100),
    "dragonbreath": ("paralysis", 30),

    # Freeze
    "ice-beam": ("freeze", 10),
    "blizzard": ("freeze", 10),
    "ice-punch": ("freeze", 10),
    "powder-snow": ("freeze", 10),
    "ice-fang": ("freeze", 10),
    "freeze-dry": ("freeze", 10),

    # Poison
    "sludge-bomb": ("poison", 30),
    "sludge-wave": ("poison", 10),
    "sludge": ("poison", 30),
    "gunk-shot": ("poison", 30),
    "poison-jab": ("poison", 30),
    "cross-poison": ("poison", 10),
    "poison-sting": ("poison", 30),
    "poison-powder": ("poison", 100),
    "toxic": ("badly_poison", 100),
    "poison-fang": ("badly_poison", 50),

    # Flinch
    "rock-slide": ("flinch", 30),
    "iron-head": ("flinch", 30),
    "zen-headbutt": ("flinch", 20),
    "air-slash": ("flinch", 30),
    "fake-out": ("flinch", 100),  # Always flinches turn 1
    "waterfall": ("flinch", 20),
    "bite": ("flinch", 30),
    "dark-pulse": ("flinch", 20),
    "headbutt": ("flinch", 30),
    "icicle-crash": ("flinch", 30),
    "stomp": ("flinch", 30),
    "astonish": ("flinch", 30),
    "extrasensory": ("flinch", 10),
    "dragon-rush": ("flinch", 20),
    "heart-stamp": ("flinch", 30),
    "twister": ("flinch", 20),
    "snore": ("flinch", 30),
    "zing-zap": ("flinch", 30),
    "floaty-fall": ("flinch", 30),

    # Confusion
    "hurricane": ("confusion", 30),
    "psybeam": ("confusion", 10),
    "confusion": ("confusion", 10),
    "signal-beam": ("confusion", 10),
    "dynamic-punch": ("confusion", 100),
    "dizzy-punch": ("confusion", 20),
    "confuse-ray": ("confusion", 100),
    "supersonic": ("confusion", 100),
    "sweet-kiss": ("confusion", 100),

    # Sleep
    "relic-song": ("sleep", 10),
    "sleep-powder": ("sleep", 100),
    "spore": ("sleep", 100),
    "hypnosis": ("sleep", 100),
    "sing": ("sleep", 100),
    "lovely-kiss": ("sleep", 100),
    "dark-void": ("sleep", 80),
    "grass-whistle": ("sleep", 100),
    "yawn": ("sleep", 100),  # Delayed

    # Stat drops on target
    "snarl": ("stat_drop", 100),  # -1 SpA
    "icy-wind": ("stat_drop", 100),  # -1 Speed
    "electroweb": ("stat_drop", 100),  # -1 Speed
    "breaking-swipe": ("stat_drop", 100),  # -1 Atk
    "parting-shot": ("stat_drop", 100),  # -1 Atk, -1 SpA
    "moonblast": ("stat_drop", 30),  # -1 SpA
    "shadow-ball": ("stat_drop", 20),  # -1 SpD
    "psychic": ("stat_drop", 10),  # -1 SpD
    "energy-ball": ("stat_drop", 10),  # -1 SpD
    "earth-power": ("stat_drop", 10),  # -1 SpD
    "flash-cannon": ("stat_drop", 10),  # -1 SpD
    "focus-blast": ("stat_drop", 10),  # -1 SpD
    "acid-spray": ("stat_drop", 100),  # -2 SpD
    "crunch": ("stat_drop", 20),  # -1 Def
    "rock-smash": ("stat_drop", 50),  # -1 Def
    "crush-claw": ("stat_drop", 50),  # -1 Def
    "razor-shell": ("stat_drop", 50),  # -1 Def
    "fire-lash": ("stat_drop", 100),  # -1 Def
    "liquidation": ("stat_drop", 20),  # -1 Def
    "seed-flare": ("stat_drop", 40),  # -2 SpD
}


def get_move_secondary_effect(move_name: str) -> tuple[str, int] | None:
    """
    Get the secondary effect info for a move.

    Args:
        move_name: Move name (case insensitive, hyphenated)

    Returns:
        Tuple of (effect_type, chance) or None if no effect
    """
    normalized = move_name.lower().replace(" ", "-")
    return MOVE_SECONDARY_EFFECTS.get(normalized)


def format_secondary_effect(effect: str, chance: int) -> str:
    """
    Format a secondary effect for display.

    Args:
        effect: Effect type (burn, paralysis, etc.)
        chance: Percentage chance (0-100)

    Returns:
        Human-readable effect description
    """
    effect_descriptions = {
        "burn": "Burns target",
        "freeze": "May freeze target",
        "paralysis": "Paralyzes target",
        "poison": "Poisons target",
        "badly_poison": "Badly poisons target",
        "sleep": "Puts target to sleep",
        "confusion": "Confuses target",
        "flinch": "May cause flinching",
        "stat_drop": "Lowers target's stats",
        "stat_boost": "Raises user's stats",
    }

    desc = effect_descriptions.get(effect, effect.replace("_", " ").title())

    if chance == 100:
        return f"{desc} (guaranteed)"
    else:
        return f"{desc} ({chance}% chance)"


# Always-crit moves (single hit but guaranteed critical)
ALWAYS_CRIT_MOVES: set[str] = {
    "wicked-blow",      # Urshifu-Single-Strike signature
    "frost-breath",     # Ice-type
    "storm-throw",      # Fighting-type
    "zippy-zap",        # Pikachu exclusive
    "flower-trick",     # Meowscarada signature
    # Note: Surging Strikes is in MULTI_HIT_MOVES with always_crit=True
}


# Multi-hit moves database
# Format: {move_name: (min_hits, max_hits, always_crit)}
MULTI_HIT_MOVES: dict[str, tuple[int, int, bool]] = {
    # Fixed hit count moves
    "surging-strikes": (3, 3, True),  # Always crits
    "dragon-darts": (2, 2, False),
    "triple-axel": (3, 3, False),  # Note: Power increases per hit (20/40/60)
    "triple-kick": (3, 3, False),  # Note: Power increases per hit
    "dual-wingbeat": (2, 2, False),
    "double-hit": (2, 2, False),
    "double-kick": (2, 2, False),
    "double-iron-bash": (2, 2, False),  # 30% flinch each hit
    "twineedle": (2, 2, False),
    "gear-grind": (2, 2, False),
    "bonemerang": (2, 2, False),
    "arm-thrust": (2, 5, False),

    # Variable hit count moves (2-5 hits)
    "bullet-seed": (2, 5, False),
    "rock-blast": (2, 5, False),
    "icicle-spear": (2, 5, False),
    "tail-slap": (2, 5, False),
    "scale-shot": (2, 5, False),
    "pin-missile": (2, 5, False),
    "fury-attack": (2, 5, False),
    "fury-swipes": (2, 5, False),
    "spike-cannon": (2, 5, False),
    "comet-punch": (2, 5, False),
    "barrage": (2, 5, False),
    "bone-rush": (2, 5, False),
    "water-shuriken": (2, 5, False),

    # Population Bomb (1-10 hits, affected by Skill Link and Wide Lens)
    "population-bomb": (1, 10, False),
}


def get_multi_hit_info(move_name: str) -> tuple[int, int, bool] | None:
    """
    Get multi-hit info for a move.

    Args:
        move_name: Move name (case insensitive, hyphenated)

    Returns:
        Tuple of (min_hits, max_hits, always_crit) or None if not multi-hit
    """
    normalized = move_name.lower().replace(" ", "-")
    return MULTI_HIT_MOVES.get(normalized)


def is_always_crit_move(move_name: str) -> bool:
    """
    Check if a move always results in a critical hit.

    Args:
        move_name: Move name (case insensitive, hyphenated)

    Returns:
        True if the move always crits (e.g., Wicked Blow, Frost Breath)
    """
    normalized = move_name.lower().replace(" ", "-")
    # Check both the always-crit set and multi-hit moves with always_crit=True
    if normalized in ALWAYS_CRIT_MOVES:
        return True
    multi_hit = MULTI_HIT_MOVES.get(normalized)
    return multi_hit is not None and multi_hit[2]


# Gen 9 signature moves with special mechanics
GEN9_SPECIAL_MOVES: dict[str, dict] = {
    "rage-fist": {
        "base_power": 50,
        "type": "ghost",
        "category": "physical",
        "scaling": "times_hit",  # +50 BP per time user was hit (max 350)
    },
    "last-respects": {
        "base_power": 50,
        "type": "ghost",
        "category": "physical",
        "scaling": "fainted_allies",  # +50 BP per fainted party member (max 300)
    },
    "collision-course": {
        "base_power": 100,
        "type": "fighting",
        "category": "physical",
        "se_bonus": 1.33,  # 1.33x on super effective hits
    },
    "electro-drift": {
        "base_power": 100,
        "type": "electric",
        "category": "special",
        "se_bonus": 1.33,  # 1.33x on super effective hits
    },
    "make-it-rain": {
        "base_power": 120,
        "type": "steel",
        "category": "special",
        "spread": True,
        "self_stat_drop": ("special_attack", -1),
    },
    "tera-blast": {
        "base_power": 80,
        "type": "normal",  # Changes to Tera type when Terastallized
        "category": "special",  # Becomes physical if Atk > SpA
        "tera_type_change": True,
    },
    "order-up": {
        "base_power": 80,
        "type": "dragon",
        "category": "physical",
        "tatsugiri_boost": True,  # Stat boost depends on Tatsugiri form
    },
}
