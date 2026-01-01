"""Common EV spread presets for VGC Pokemon.

These are proven, tournament-tested spreads with explanations
of what benchmarks they hit.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class SpreadPreset:
    """A preset EV spread with metadata."""
    name: str  # e.g., "Bulky Pivot", "Fast Attacker"
    pokemon: str  # Pokemon name (lowercase, hyphenated)
    nature: str
    evs: dict[str, int]  # hp, attack, defense, special_attack, special_defense, speed
    item: Optional[str] = None
    ability: Optional[str] = None
    tera_type: Optional[str] = None
    benchmarks: list[str] = None  # What this spread accomplishes
    usage_context: str = ""  # When to use this spread
    source: Optional[str] = None  # Tournament/player source

    def __post_init__(self):
        if self.benchmarks is None:
            self.benchmarks = []


# =============================================================================
# INCINEROAR SPREADS
# =============================================================================
INCINEROAR_SPREADS = [
    SpreadPreset(
        name="Standard Bulky Pivot",
        pokemon="incineroar",
        nature="careful",
        evs={"hp": 252, "attack": 4, "defense": 0, "special_attack": 0, "special_defense": 252, "speed": 0},
        item="safety-goggles",
        ability="intimidate",
        benchmarks=[
            "Survives Modest Flutter Mane Moonblast",
            "Maximum special bulk for Intimidate cycling",
        ],
        usage_context="Standard support set for most teams",
    ),
    SpreadPreset(
        name="Physically Defensive",
        pokemon="incineroar",
        nature="impish",
        evs={"hp": 252, "attack": 0, "defense": 252, "special_attack": 0, "special_defense": 4, "speed": 0},
        item="sitrus-berry",
        ability="intimidate",
        benchmarks=[
            "Survives +1 Dragonite Earthquake",
            "Tanks physical threats after Intimidate",
        ],
        usage_context="Teams weak to physical attackers",
    ),
    SpreadPreset(
        name="Fast Fake Out",
        pokemon="incineroar",
        nature="jolly",
        evs={"hp": 252, "attack": 4, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 252},
        item="safety-goggles",
        ability="intimidate",
        benchmarks=[
            "Outspeeds neutral base 70s",
            "Fast Fake Out for speed control",
        ],
        usage_context="Mirror matches, priority on Fake Out",
    ),
    SpreadPreset(
        name="Assault Vest Tank",
        pokemon="incineroar",
        nature="careful",
        evs={"hp": 244, "attack": 12, "defense": 4, "special_attack": 0, "special_defense": 244, "speed": 4},
        item="assault-vest",
        ability="intimidate",
        benchmarks=[
            "Lives 2x Fairy moves from Flutter Mane",
            "HP not divisible by 4 for less Stealth Rock damage",
        ],
        usage_context="Heavy special attack metagames",
    ),
]

# =============================================================================
# FLUTTER MANE SPREADS
# =============================================================================
FLUTTER_MANE_SPREADS = [
    SpreadPreset(
        name="Max Speed Attacker",
        pokemon="flutter-mane",
        nature="timid",
        evs={"hp": 4, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 0, "speed": 252},
        item="choice-specs",
        ability="protosynthesis",
        benchmarks=[
            "205 Speed - ties other max speed Flutter Mane",
            "OHKOs most non-resistant Pokemon with Moonblast",
        ],
        usage_context="Standard offensive set",
    ),
    SpreadPreset(
        name="Bulky Booster Energy",
        pokemon="flutter-mane",
        nature="modest",
        evs={"hp": 116, "attack": 0, "defense": 76, "special_attack": 116, "special_defense": 4, "speed": 196},
        item="booster-energy",
        ability="protosynthesis",
        benchmarks=[
            "Survives Adamant Urshifu Sucker Punch",
            "Still outspeeds most of the metagame after boost",
        ],
        usage_context="When you need Flutter Mane to take a hit",
    ),
    SpreadPreset(
        name="Focus Sash Lead",
        pokemon="flutter-mane",
        nature="timid",
        evs={"hp": 0, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 4, "speed": 252},
        item="focus-sash",
        ability="protosynthesis",
        benchmarks=[
            "Guarantees survival of any single hit",
            "Maximum offensive pressure turn 1",
        ],
        usage_context="Lead position, aggressive teams",
    ),
]

# =============================================================================
# URSHIFU SPREADS (Single Strike)
# =============================================================================
URSHIFU_SINGLE_SPREADS = [
    SpreadPreset(
        name="Max Attack Banded",
        pokemon="urshifu",
        nature="jolly",
        evs={"hp": 4, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 252},
        item="choice-band",
        ability="unseen-fist",
        benchmarks=[
            "163 Speed - outspeeds base 100s",
            "OHKOs most Pokemon with Wicked Blow",
        ],
        usage_context="Wallbreaker, late game cleaner",
    ),
    SpreadPreset(
        name="Bulky Attacker",
        pokemon="urshifu",
        nature="adamant",
        evs={"hp": 252, "attack": 156, "defense": 4, "special_attack": 0, "special_defense": 28, "speed": 68},
        item="assault-vest",
        ability="unseen-fist",
        benchmarks=[
            "Survives Modest Flutter Mane Moonblast",
            "Still OHKOs frail targets with Wicked Blow",
            "Outspeeds neutral base 70s",
        ],
        usage_context="Against special-heavy teams",
    ),
    SpreadPreset(
        name="Focus Sash Lead",
        pokemon="urshifu",
        nature="jolly",
        evs={"hp": 0, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 4, "speed": 252},
        item="focus-sash",
        ability="unseen-fist",
        benchmarks=[
            "Survives any single hit",
            "Maximum speed for Sucker Punch mind games",
        ],
        usage_context="Lead position, offensive teams",
    ),
]

# =============================================================================
# URSHIFU SPREADS (Rapid Strike)
# =============================================================================
URSHIFU_RAPID_SPREADS = [
    SpreadPreset(
        name="Standard Attacker",
        pokemon="urshifu-rapid-strike",
        nature="jolly",
        evs={"hp": 4, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 252},
        item="choice-band",
        ability="unseen-fist",
        benchmarks=[
            "163 Speed - outspeeds base 100s",
            "Surging Strikes breaks Substitutes and Sashes",
        ],
        usage_context="Rain teams, breaking through protection",
    ),
    SpreadPreset(
        name="Mystic Water Attacker",
        pokemon="urshifu-rapid-strike",
        nature="jolly",
        evs={"hp": 4, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 252},
        item="mystic-water",
        ability="unseen-fist",
        benchmarks=[
            "Flexible move choice unlike Choice Band",
            "Still hits hard with Rain support",
        ],
        usage_context="Needs flexibility, Rain teams",
    ),
]

# =============================================================================
# RILLABOOM SPREADS
# =============================================================================
RILLABOOM_SPREADS = [
    SpreadPreset(
        name="Assault Vest Pivot",
        pokemon="rillaboom",
        nature="adamant",
        evs={"hp": 252, "attack": 116, "defense": 4, "special_attack": 0, "special_defense": 132, "speed": 4},
        item="assault-vest",
        ability="grassy-surge",
        benchmarks=[
            "Survives Modest Flutter Mane Moonblast",
            "Grassy Glide priority in terrain",
        ],
        usage_context="Fake Out support with bulk",
    ),
    SpreadPreset(
        name="Choice Band Wallbreaker",
        pokemon="rillaboom",
        nature="adamant",
        evs={"hp": 252, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 4, "speed": 0},
        item="choice-band",
        ability="grassy-surge",
        benchmarks=[
            "OHKOs most Water/Ground types",
            "Wood Hammer decimates switch-ins",
        ],
        usage_context="Heavy damage output",
    ),
    SpreadPreset(
        name="Miracle Seed Attacker",
        pokemon="rillaboom",
        nature="adamant",
        evs={"hp": 252, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 4, "speed": 0},
        item="miracle-seed",
        ability="grassy-surge",
        benchmarks=[
            "Flexible move choice",
            "1.2x Grass moves without locking in",
        ],
        usage_context="Needs Fake Out + attacking flexibility",
    ),
]

# =============================================================================
# DRAGAPULT SPREADS
# =============================================================================
DRAGAPULT_SPREADS = [
    SpreadPreset(
        name="Max Speed Physical",
        pokemon="dragapult",
        nature="jolly",
        evs={"hp": 4, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 252},
        item="choice-band",
        ability="clear-body",
        benchmarks=[
            "213 Speed - outspeeds most unboosted Pokemon",
            "Dragon Darts hits both opponents",
        ],
        usage_context="Fast physical attacker",
    ),
    SpreadPreset(
        name="Max Speed Special",
        pokemon="dragapult",
        nature="timid",
        evs={"hp": 4, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 0, "speed": 252},
        item="choice-specs",
        ability="clear-body",
        benchmarks=[
            "213 Speed with special coverage",
            "Draco Meteor nukes Dragons",
        ],
        usage_context="Special attacker variant",
    ),
    SpreadPreset(
        name="Bulky Support",
        pokemon="dragapult",
        nature="jolly",
        evs={"hp": 252, "attack": 4, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 252},
        item="focus-sash",
        ability="clear-body",
        benchmarks=[
            "Will-O-Wisp support",
            "Thunder Wave speed control",
        ],
        usage_context="Utility/support set",
    ),
]

# =============================================================================
# TORNADUS SPREADS
# =============================================================================
TORNADUS_SPREADS = [
    SpreadPreset(
        name="Fast Tailwind Support",
        pokemon="tornadus",
        nature="timid",
        evs={"hp": 4, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 0, "speed": 252},
        item="focus-sash",
        ability="prankster",
        benchmarks=[
            "Prankster Tailwind always goes first",
            "Bleakwind Storm spreads damage",
        ],
        usage_context="Tailwind setter for offensive teams",
    ),
    SpreadPreset(
        name="Bulky Tailwind",
        pokemon="tornadus",
        nature="timid",
        evs={"hp": 252, "attack": 0, "defense": 100, "special_attack": 4, "special_defense": 4, "speed": 148},
        item="sitrus-berry",
        ability="prankster",
        benchmarks=[
            "Survives Rock Slide from most physical attackers",
            "Outspeeds base 100s for non-priority moves",
        ],
        usage_context="When you need Tailwind to survive",
    ),
]

# =============================================================================
# AMOONGUSS SPREADS
# =============================================================================
AMOONGUSS_SPREADS = [
    SpreadPreset(
        name="Standard Redirector",
        pokemon="amoonguss",
        nature="calm",
        evs={"hp": 252, "attack": 0, "defense": 4, "special_attack": 0, "special_defense": 252, "speed": 0},
        item="sitrus-berry",
        ability="regenerator",
        benchmarks=[
            "Maximum special bulk",
            "Rage Powder redirects attacks",
        ],
        usage_context="Protect frail partners",
    ),
    SpreadPreset(
        name="Physically Defensive",
        pokemon="amoonguss",
        nature="bold",
        evs={"hp": 252, "attack": 0, "defense": 252, "special_attack": 0, "special_defense": 4, "speed": 0},
        item="rocky-helmet",
        ability="regenerator",
        benchmarks=[
            "Punishes physical contact moves",
            "Tanks Earthquakes and Close Combats",
        ],
        usage_context="Against physical-heavy teams",
    ),
    SpreadPreset(
        name="Minimum Speed TR",
        pokemon="amoonguss",
        nature="sassy",
        evs={"hp": 252, "attack": 0, "defense": 4, "special_attack": 0, "special_defense": 252, "speed": 0},
        item="sitrus-berry",
        ability="regenerator",
        tera_type="water",
        benchmarks=[
            "Outspeeds in Trick Room",
            "Tera Water removes Fire weakness",
        ],
        usage_context="Trick Room teams",
    ),
]

# =============================================================================
# IRON HANDS SPREADS
# =============================================================================
IRON_HANDS_SPREADS = [
    SpreadPreset(
        name="Assault Vest Tank",
        pokemon="iron-hands",
        nature="adamant",
        evs={"hp": 252, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 4, "speed": 0},
        item="assault-vest",
        ability="quark-drive",
        benchmarks=[
            "Massive special bulk with AV",
            "Fake Out + Drain Punch sustain",
        ],
        usage_context="Bulky attacker for Trick Room",
    ),
    SpreadPreset(
        name="Choice Band Nuke",
        pokemon="iron-hands",
        nature="adamant",
        evs={"hp": 252, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 4, "speed": 0},
        item="choice-band",
        ability="quark-drive",
        benchmarks=[
            "Close Combat OHKOs almost everything",
            "Best used in Trick Room",
        ],
        usage_context="Maximum damage output",
    ),
    SpreadPreset(
        name="Booster Energy Speed",
        pokemon="iron-hands",
        nature="adamant",
        evs={"hp": 4, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 252},
        item="booster-energy",
        ability="quark-drive",
        benchmarks=[
            "Boosts Speed with Booster Energy",
            "Outspeeds most of the meta after boost",
        ],
        usage_context="Outside of Trick Room",
    ),
]

# =============================================================================
# CALYREX-ICE SPREADS
# =============================================================================
CALYREX_ICE_SPREADS = [
    SpreadPreset(
        name="Standard TR Attacker",
        pokemon="calyrex-ice",
        nature="brave",
        evs={"hp": 252, "attack": 252, "defense": 4, "special_attack": 0, "special_defense": 0, "speed": 0},
        item="clear-amulet",
        ability="as-one-glastrier",
        benchmarks=[
            "0 Speed IVs for Trick Room",
            "Glacial Lance decimates teams",
            "Clear Amulet prevents Intimidate",
        ],
        usage_context="Trick Room sweeper",
    ),
    SpreadPreset(
        name="Assault Vest Bulk",
        pokemon="calyrex-ice",
        nature="brave",
        evs={"hp": 252, "attack": 116, "defense": 4, "special_attack": 0, "special_defense": 132, "speed": 0},
        item="assault-vest",
        ability="as-one-glastrier",
        benchmarks=[
            "Survives special attacks better",
            "Still hits hard with Glacial Lance",
        ],
        usage_context="Against special attackers",
    ),
]

# =============================================================================
# CALYREX-SHADOW SPREADS
# =============================================================================
CALYREX_SHADOW_SPREADS = [
    SpreadPreset(
        name="Max Speed Attacker",
        pokemon="calyrex-shadow",
        nature="timid",
        evs={"hp": 4, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 0, "speed": 252},
        item="focus-sash",
        ability="as-one-spectrier",
        benchmarks=[
            "222 Speed - fastest restricted",
            "Astral Barrage spreads massive damage",
        ],
        usage_context="Fast offensive team",
    ),
    SpreadPreset(
        name="Choice Specs Nuke",
        pokemon="calyrex-shadow",
        nature="modest",
        evs={"hp": 4, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 0, "speed": 252},
        item="choice-specs",
        ability="as-one-spectrier",
        benchmarks=[
            "OHKOs almost anything neutral",
            "Modest for more power, still fast",
        ],
        usage_context="Wallbreaker",
    ),
]

# =============================================================================
# KYOGRE SPREADS
# =============================================================================
KYOGRE_SPREADS = [
    SpreadPreset(
        name="Choice Specs Rain",
        pokemon="kyogre",
        nature="modest",
        evs={"hp": 4, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 0, "speed": 252},
        item="choice-specs",
        ability="drizzle",
        benchmarks=[
            "Water Spout in Rain OHKOs most Pokemon",
            "Origin Pulse spread damage",
        ],
        usage_context="Rain teams, offensive",
    ),
    SpreadPreset(
        name="Assault Vest Bulk",
        pokemon="kyogre",
        nature="modest",
        evs={"hp": 252, "attack": 0, "defense": 4, "special_attack": 156, "special_defense": 92, "speed": 4},
        item="assault-vest",
        ability="drizzle",
        benchmarks=[
            "Survives Grass attacks from Rillaboom",
            "Still hits hard with Rain-boosted moves",
        ],
        usage_context="Bulkier Rain teams",
    ),
]

# =============================================================================
# GROUDON SPREADS
# =============================================================================
GROUDON_SPREADS = [
    SpreadPreset(
        name="Physical Attacker",
        pokemon="groudon",
        nature="adamant",
        evs={"hp": 252, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 4, "speed": 0},
        item="assault-vest",
        ability="drought",
        benchmarks=[
            "Precipice Blades spread damage",
            "Sun boosts Fire moves",
        ],
        usage_context="Sun teams, Trick Room",
    ),
    SpreadPreset(
        name="Fast Attacker",
        pokemon="groudon",
        nature="jolly",
        evs={"hp": 4, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 252},
        item="choice-band",
        ability="drought",
        benchmarks=[
            "Outspeeds neutral base 90s",
            "Band Precipice Blades destroys teams",
        ],
        usage_context="Offensive Sun teams",
    ),
]

# =============================================================================
# MIRAIDON SPREADS
# =============================================================================
MIRAIDON_SPREADS = [
    SpreadPreset(
        name="Max Speed Specs",
        pokemon="miraidon",
        nature="timid",
        evs={"hp": 4, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 0, "speed": 252},
        item="choice-specs",
        ability="hadron-engine",
        benchmarks=[
            "205 Speed - ties Flutter Mane",
            "Electro Drift OHKOs most things",
        ],
        usage_context="Hyper offensive teams",
    ),
    SpreadPreset(
        name="Life Orb Attacker",
        pokemon="miraidon",
        nature="timid",
        evs={"hp": 4, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 0, "speed": 252},
        item="life-orb",
        ability="hadron-engine",
        benchmarks=[
            "Flexible move choice",
            "Can use support moves like Electroweb",
        ],
        usage_context="Needs coverage flexibility",
    ),
]

# =============================================================================
# KORAIDON SPREADS
# =============================================================================
KORAIDON_SPREADS = [
    SpreadPreset(
        name="Physical Sweeper",
        pokemon="koraidon",
        nature="adamant",
        evs={"hp": 4, "attack": 252, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 252},
        item="choice-band",
        ability="orichalcum-pulse",
        benchmarks=[
            "Collision Course hits insanely hard in Sun",
            "Outspeeds neutral base 100s",
        ],
        usage_context="Sun teams, offensive",
    ),
    SpreadPreset(
        name="Bulky Attacker",
        pokemon="koraidon",
        nature="adamant",
        evs={"hp": 252, "attack": 156, "defense": 4, "special_attack": 0, "special_defense": 92, "speed": 4},
        item="assault-vest",
        ability="orichalcum-pulse",
        benchmarks=[
            "Lives special hits from Kyogre",
            "Still hits hard with Sun boost",
        ],
        usage_context="Against Rain/Water teams",
    ),
]


# =============================================================================
# PRESET LOOKUP
# =============================================================================
ALL_PRESETS: dict[str, list[SpreadPreset]] = {
    "incineroar": INCINEROAR_SPREADS,
    "flutter-mane": FLUTTER_MANE_SPREADS,
    "urshifu": URSHIFU_SINGLE_SPREADS,
    "urshifu-single-strike": URSHIFU_SINGLE_SPREADS,
    "urshifu-rapid-strike": URSHIFU_RAPID_SPREADS,
    "rillaboom": RILLABOOM_SPREADS,
    "dragapult": DRAGAPULT_SPREADS,
    "tornadus": TORNADUS_SPREADS,
    "amoonguss": AMOONGUSS_SPREADS,
    "iron-hands": IRON_HANDS_SPREADS,
    "calyrex-ice": CALYREX_ICE_SPREADS,
    "calyrex-ice-rider": CALYREX_ICE_SPREADS,
    "calyrex-shadow": CALYREX_SHADOW_SPREADS,
    "calyrex-shadow-rider": CALYREX_SHADOW_SPREADS,
    "kyogre": KYOGRE_SPREADS,
    "groudon": GROUDON_SPREADS,
    "miraidon": MIRAIDON_SPREADS,
    "koraidon": KORAIDON_SPREADS,
}


def get_presets_for_pokemon(pokemon_name: str) -> list[SpreadPreset]:
    """Get all spread presets for a Pokemon."""
    normalized = pokemon_name.lower().replace(" ", "-")
    return ALL_PRESETS.get(normalized, [])


def get_preset_by_name(pokemon_name: str, preset_name: str) -> Optional[SpreadPreset]:
    """Get a specific preset by Pokemon and preset name."""
    presets = get_presets_for_pokemon(pokemon_name)
    for preset in presets:
        if preset.name.lower() == preset_name.lower():
            return preset
    return None


def get_all_pokemon_with_presets() -> list[str]:
    """Get list of all Pokemon that have preset spreads."""
    return list(ALL_PRESETS.keys())
