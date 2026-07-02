"""Pokemon data models with nature modifiers and stat spreads."""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Format systems determine how a Pokemon's stat allocation is interpreted.
# - "mainline": classic VGC EV system (0-252/stat, 508 total) — Reg F/G/H/I.
# - "champions": Pokemon Champions stat-point system (0-32/stat, 66 total) — Reg MA.
FormatSystem = Literal["mainline", "champions"]

# Champions SP <-> mainline stat name mapping. NCP setdex JSON uses
# the abbreviated keys; we keep canonical full names internally.
SP_KEY_TO_STAT: dict[str, str] = {
    "hp": "hp",
    "at": "attack",
    "df": "defense",
    "sa": "special_attack",
    "sd": "special_defense",
    "sp": "speed",
}
STAT_TO_SP_KEY: dict[str, str] = {v: k for k, v in SP_KEY_TO_STAT.items()}


class Nature(str, Enum):
    """All 25 Pokemon natures with their stat effects."""
    # Neutral natures
    HARDY = "hardy"
    DOCILE = "docile"
    SERIOUS = "serious"
    BASHFUL = "bashful"
    QUIRKY = "quirky"
    # +Attack
    LONELY = "lonely"    # +Atk, -Def
    BRAVE = "brave"      # +Atk, -Spe
    ADAMANT = "adamant"  # +Atk, -SpA
    NAUGHTY = "naughty"  # +Atk, -SpD
    # +Defense
    BOLD = "bold"        # +Def, -Atk
    RELAXED = "relaxed"  # +Def, -Spe
    IMPISH = "impish"    # +Def, -SpA
    LAX = "lax"          # +Def, -SpD
    # +Special Attack
    MODEST = "modest"    # +SpA, -Atk
    MILD = "mild"        # +SpA, -Def
    QUIET = "quiet"      # +SpA, -Spe
    RASH = "rash"        # +SpA, -SpD
    # +Special Defense
    CALM = "calm"        # +SpD, -Atk
    GENTLE = "gentle"    # +SpD, -Def
    SASSY = "sassy"      # +SpD, -Spe
    CAREFUL = "careful"  # +SpD, -SpA
    # +Speed
    TIMID = "timid"      # +Spe, -Atk
    HASTY = "hasty"      # +Spe, -Def
    JOLLY = "jolly"      # +Spe, -SpA
    NAIVE = "naive"      # +Spe, -SpD


# Nature modifiers: stat_name -> modifier (1.1 = +10%, 0.9 = -10%)
NATURE_MODIFIERS: dict[Nature, dict[str, float]] = {
    # Neutral
    Nature.HARDY: {},
    Nature.DOCILE: {},
    Nature.SERIOUS: {},
    Nature.BASHFUL: {},
    Nature.QUIRKY: {},
    # +Attack
    Nature.LONELY: {"attack": 1.1, "defense": 0.9},
    Nature.BRAVE: {"attack": 1.1, "speed": 0.9},
    Nature.ADAMANT: {"attack": 1.1, "special_attack": 0.9},
    Nature.NAUGHTY: {"attack": 1.1, "special_defense": 0.9},
    # +Defense
    Nature.BOLD: {"defense": 1.1, "attack": 0.9},
    Nature.RELAXED: {"defense": 1.1, "speed": 0.9},
    Nature.IMPISH: {"defense": 1.1, "special_attack": 0.9},
    Nature.LAX: {"defense": 1.1, "special_defense": 0.9},
    # +Special Attack
    Nature.MODEST: {"special_attack": 1.1, "attack": 0.9},
    Nature.MILD: {"special_attack": 1.1, "defense": 0.9},
    Nature.QUIET: {"special_attack": 1.1, "speed": 0.9},
    Nature.RASH: {"special_attack": 1.1, "special_defense": 0.9},
    # +Special Defense
    Nature.CALM: {"special_defense": 1.1, "attack": 0.9},
    Nature.GENTLE: {"special_defense": 1.1, "defense": 0.9},
    Nature.SASSY: {"special_defense": 1.1, "speed": 0.9},
    Nature.CAREFUL: {"special_defense": 1.1, "special_attack": 0.9},
    # +Speed
    Nature.TIMID: {"speed": 1.1, "attack": 0.9},
    Nature.HASTY: {"speed": 1.1, "defense": 0.9},
    Nature.JOLLY: {"speed": 1.1, "special_attack": 0.9},
    Nature.NAIVE: {"speed": 1.1, "special_defense": 0.9},
}


def get_nature_modifier(nature: Nature, stat_name: str) -> float:
    """Get the nature modifier for a specific stat."""
    if nature not in NATURE_MODIFIERS:
        return 1.0
    return NATURE_MODIFIERS[nature].get(stat_name, 1.0)


class BaseStats(BaseModel):
    """Pokemon base stats (species-specific)."""
    hp: int = Field(ge=1, le=255)
    attack: int = Field(ge=1, le=255)
    defense: int = Field(ge=1, le=255)
    special_attack: int = Field(ge=1, le=255)
    special_defense: int = Field(ge=1, le=255)
    speed: int = Field(ge=1, le=255)

    model_config = ConfigDict(populate_by_name=True)


class EVSpread(BaseModel):
    """EV (Effort Value) spread - max 252 per stat, 508 total."""
    hp: int = Field(default=0, ge=0, le=252)
    attack: int = Field(default=0, ge=0, le=252)
    defense: int = Field(default=0, ge=0, le=252)
    special_attack: int = Field(default=0, ge=0, le=252)
    special_defense: int = Field(default=0, ge=0, le=252)
    speed: int = Field(default=0, ge=0, le=252)

    @property
    def total(self) -> int:
        """Total EVs used."""
        return (
            self.hp + self.attack + self.defense +
            self.special_attack + self.special_defense + self.speed
        )

    def is_valid(self) -> bool:
        """Check if EV spread is valid (max 508 total)."""
        return self.total <= 508

    def remaining(self) -> int:
        """EVs remaining to allocate."""
        return max(0, 508 - self.total)


class StatPointSpread(BaseModel):
    """Stat Point spread for Pokemon Champions VGC (Reg MA).

    Per-stat cap is 32, total budget is 66 across all six stats. Field names
    match the canonical full-stat names (not the NCP `at/df/sa/sd/sp` abbrevs).
    Use `from_sps_dict` to load from NCP setdex JSON shape.
    """
    hp: int = Field(default=0, ge=0, le=32)
    attack: int = Field(default=0, ge=0, le=32)
    defense: int = Field(default=0, ge=0, le=32)
    special_attack: int = Field(default=0, ge=0, le=32)
    special_defense: int = Field(default=0, ge=0, le=32)
    speed: int = Field(default=0, ge=0, le=32)

    MAX_TOTAL: int = 66

    @property
    def total(self) -> int:
        """Total stat points used."""
        return (
            self.hp + self.attack + self.defense +
            self.special_attack + self.special_defense + self.speed
        )

    def is_valid(self) -> bool:
        """Check if SP spread is within the 66-point budget."""
        return self.total <= 66

    def remaining(self) -> int:
        """Stat points remaining to allocate."""
        return max(0, 66 - self.total)

    @classmethod
    def from_sps_dict(cls, sps: dict) -> "StatPointSpread":
        """Build from an NCP-style dict using `hp/at/df/sa/sd/sp` keys.

        Falls back to full canonical names if abbreviations aren't present so
        the same loader works for both shapes.
        """
        kwargs: dict[str, int] = {}
        for short_key, full_key in SP_KEY_TO_STAT.items():
            if short_key in sps:
                kwargs[full_key] = int(sps[short_key])
            elif full_key in sps:
                kwargs[full_key] = int(sps[full_key])
        return cls(**kwargs)

    def to_sps_dict(self) -> dict[str, int]:
        """Emit NCP-style dict with abbreviated keys."""
        return {
            "hp": self.hp,
            "at": self.attack,
            "df": self.defense,
            "sa": self.special_attack,
            "sd": self.special_defense,
            "sp": self.speed,
        }


class IVSpread(BaseModel):
    """IV (Individual Value) spread - 0-31 per stat, default 31."""
    hp: int = Field(default=31, ge=0, le=31)
    attack: int = Field(default=31, ge=0, le=31)
    defense: int = Field(default=31, ge=0, le=31)
    special_attack: int = Field(default=31, ge=0, le=31)
    special_defense: int = Field(default=31, ge=0, le=31)
    speed: int = Field(default=31, ge=0, le=31)


class Pokemon(BaseModel):
    """Pokemon species data from API."""
    name: str
    base_stats: BaseStats
    types: list[str] = Field(default_factory=list, max_length=2)
    abilities: list[str] = Field(default_factory=list)
    species: str = ""  # For species clause (base form name)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.species:
            # Extract base species from form name (e.g., "urshifu-rapid-strike" -> "urshifu")
            self.species = self.name.split("-")[0]


class PokemonBuild(BaseModel):
    """A specific Pokemon build with EVs/SPs, IVs, nature, item, moves, etc.

    The `format_system` field controls how stats are interpreted:
    - "mainline" (default): classic VGC, uses `evs` (EVSpread, 252/508).
    - "champions": Pokemon Champions Reg MA, uses `sps` (StatPointSpread, 32/66).

    `evs` is always present (defaults to all-zero) so existing code that touches
    `pokemon.evs` keeps working. Champions builds simply ignore it and read `sps`.
    """
    name: str
    species: str = ""
    base_stats: BaseStats
    types: list[str] = Field(default_factory=list, max_length=2)
    nature: Nature = Nature.SERIOUS
    evs: EVSpread = Field(default_factory=EVSpread)
    sps: Optional[StatPointSpread] = None
    ivs: IVSpread = Field(default_factory=IVSpread)
    level: int = Field(default=50, ge=1, le=100)
    format_system: FormatSystem = "mainline"
    ability: Optional[str] = None
    item: Optional[str] = None
    tera_type: Optional[str] = None
    moves: list[str] = Field(default_factory=list, max_length=4)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.species:
            self.species = self.name.split("-")[0]

    @field_validator("evs")
    @classmethod
    def validate_evs(cls, v: EVSpread) -> EVSpread:
        if not v.is_valid():
            raise ValueError(f"EV total ({v.total}) exceeds maximum of 508")
        return v

    @field_validator("sps")
    @classmethod
    def validate_sps(cls, v: Optional[StatPointSpread]) -> Optional[StatPointSpread]:
        if v is not None and not v.is_valid():
            raise ValueError(f"SP total ({v.total}) exceeds maximum of 66")
        return v

    def get_nature_modifier(self, stat_name: str) -> float:
        """Get nature modifier for a stat."""
        return get_nature_modifier(self.nature, stat_name)

    def is_champions(self) -> bool:
        """True if this build uses the Pokemon Champions stat-point system."""
        return self.format_system == "champions"

    def get_stat_allocation(self, stat_name: str) -> int:
        """Return the EV (mainline) or SP (champions) allocation for `stat_name`.

        Always returns an int in the units appropriate for `format_system`. Use
        this when a caller needs to read raw allocation without branching.
        """
        if self.is_champions():
            sps = self.sps or StatPointSpread()
            return getattr(sps, stat_name, 0)
        return getattr(self.evs, stat_name, 0)
