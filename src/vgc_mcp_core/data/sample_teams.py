"""Sample tournament-proven teams database.

These are archetypal teams from various regulations that showcase
different team structures and strategies.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SampleTeam:
    """A sample team with metadata."""
    name: str
    archetype: str  # rain, sun, trick_room, hyper_offense, balance, goodstuffs
    pokemon: list[str]
    paste: str  # Showdown paste format
    description: str
    strengths: list[str]
    weaknesses: list[str]
    regulation: str
    source: Optional[str] = None  # Tournament/player source
    difficulty: str = "intermediate"  # beginner, intermediate, advanced


# =============================================================================
# RAIN TEAMS
# =============================================================================
RAIN_TEAM_1 = SampleTeam(
    name="Classic Rain Offense",
    archetype="rain",
    pokemon=["Kyogre", "Tornadus", "Urshifu-Rapid-Strike", "Rillaboom", "Incineroar", "Flutter Mane"],
    paste="""Kyogre @ Choice Specs
Ability: Drizzle
Level: 50
Tera Type: Water
EVs: 4 HP / 252 SpA / 252 Spe
Modest Nature
- Water Spout
- Origin Pulse
- Ice Beam
- Thunder

Tornadus @ Focus Sash
Ability: Prankster
Level: 50
Tera Type: Ghost
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Bleakwind Storm
- Tailwind
- Taunt
- Protect

Urshifu-Rapid-Strike @ Choice Band
Ability: Unseen Fist
Level: 50
Tera Type: Water
EVs: 4 HP / 252 Atk / 252 Spe
Jolly Nature
- Surging Strikes
- Close Combat
- Aqua Jet
- U-turn

Rillaboom @ Assault Vest
Ability: Grassy Surge
Level: 50
Tera Type: Fire
EVs: 252 HP / 116 Atk / 4 Def / 132 SpD / 4 Spe
Adamant Nature
- Grassy Glide
- Wood Hammer
- Fake Out
- U-turn

Incineroar @ Safety Goggles
Ability: Intimidate
Level: 50
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
- Flare Blitz
- Knock Off
- Fake Out
- Parting Shot

Flutter Mane @ Booster Energy
Ability: Protosynthesis
Level: 50
Tera Type: Fairy
EVs: 116 HP / 76 Def / 116 SpA / 4 SpD / 196 Spe
Modest Nature
- Moonblast
- Shadow Ball
- Thunderbolt
- Protect
""",
    description="Standard rain team with Tailwind support. Kyogre + Tornadus lead pressures immediately with Water Spout under Tailwind.",
    strengths=["Fast setup with Tailwind", "Massive spread damage", "Good defensive pivots"],
    weaknesses=["Struggles vs opposing weather", "Weak to Grass", "Speed control reliant"],
    regulation="G",
    source="Tournament archetype",
    difficulty="intermediate"
)

# =============================================================================
# SUN TEAMS
# =============================================================================
SUN_TEAM_1 = SampleTeam(
    name="Koraidon Sun Offense",
    archetype="sun",
    pokemon=["Koraidon", "Flutter Mane", "Incineroar", "Rillaboom", "Landorus", "Farigiraf"],
    paste="""Koraidon @ Choice Band
Ability: Orichalcum Pulse
Level: 50
Tera Type: Fire
EVs: 4 HP / 252 Atk / 252 Spe
Adamant Nature
- Collision Course
- Flare Blitz
- Outrage
- Close Combat

Flutter Mane @ Choice Specs
Ability: Protosynthesis
Level: 50
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Mystical Fire
- Dazzling Gleam

Incineroar @ Sitrus Berry
Ability: Intimidate
Level: 50
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
- Flare Blitz
- Knock Off
- Fake Out
- Parting Shot

Rillaboom @ Miracle Seed
Ability: Grassy Surge
Level: 50
Tera Type: Fire
EVs: 252 HP / 252 Atk / 4 SpD
Adamant Nature
- Grassy Glide
- Wood Hammer
- Fake Out
- Protect

Landorus @ Life Orb
Ability: Sheer Force
Level: 50
Tera Type: Flying
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Earth Power
- Sludge Bomb
- Psychic
- Protect

Farigiraf @ Covert Cloak
Ability: Armor Tail
Level: 50
Tera Type: Water
EVs: 252 HP / 4 Def / 252 SpD
Calm Nature
- Psychic
- Hyper Voice
- Trick Room
- Protect
""",
    description="Sun-boosted Koraidon tears through teams. Flutter Mane's Protosynthesis activates in Sun for extra speed.",
    strengths=["Insane damage output", "Speed control options", "Flexible mode selection"],
    weaknesses=["Weak to Ground", "Rain matchup is tough", "Item reliant"],
    regulation="H",
    source="Tournament archetype",
    difficulty="intermediate"
)

# =============================================================================
# TRICK ROOM TEAMS
# =============================================================================
TRICK_ROOM_TEAM_1 = SampleTeam(
    name="Calyrex-Ice Trick Room",
    archetype="trick_room",
    pokemon=["Calyrex-Ice", "Farigiraf", "Iron Hands", "Amoonguss", "Incineroar", "Flutter Mane"],
    paste="""Calyrex-Ice @ Clear Amulet
Ability: As One (Glastrier)
Level: 50
Tera Type: Ghost
EVs: 252 HP / 252 Atk / 4 SpD
Brave Nature
IVs: 0 Spe
- Glacial Lance
- High Horsepower
- Trick Room
- Protect

Farigiraf @ Sitrus Berry
Ability: Armor Tail
Level: 50
Tera Type: Water
EVs: 252 HP / 4 Def / 252 SpD
Sassy Nature
IVs: 0 Spe
- Psychic
- Hyper Voice
- Trick Room
- Helping Hand

Iron Hands @ Assault Vest
Ability: Quark Drive
Level: 50
Tera Type: Grass
EVs: 252 HP / 252 Atk / 4 SpD
Brave Nature
IVs: 0 Spe
- Drain Punch
- Wild Charge
- Fake Out
- Heavy Slam

Amoonguss @ Rocky Helmet
Ability: Regenerator
Level: 50
Tera Type: Water
EVs: 252 HP / 252 Def / 4 SpD
Relaxed Nature
IVs: 0 Spe
- Pollen Puff
- Spore
- Rage Powder
- Protect

Incineroar @ Safety Goggles
Ability: Intimidate
Level: 50
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 252 SpD
Sassy Nature
IVs: 0 Spe
- Flare Blitz
- Knock Off
- Fake Out
- Parting Shot

Flutter Mane @ Choice Specs
Ability: Protosynthesis
Level: 50
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Mystical Fire
- Dazzling Gleam
""",
    description="Dedicated Trick Room team. Calyrex-Ice devastates under TR while Farigiraf blocks priority.",
    strengths=["Dominates under Trick Room", "Armor Tail blocks Fake Out", "Multiple TR setters"],
    weaknesses=["Struggles without TR", "Taunt shuts down setup", "Fire weakness"],
    regulation="G",
    source="Tournament archetype",
    difficulty="intermediate"
)

# =============================================================================
# GOODSTUFFS / BALANCE TEAMS
# =============================================================================
GOODSTUFFS_TEAM_1 = SampleTeam(
    name="Regulation G Goodstuffs",
    archetype="goodstuffs",
    pokemon=["Miraidon", "Flutter Mane", "Incineroar", "Rillaboom", "Landorus", "Urshifu"],
    paste="""Miraidon @ Life Orb
Ability: Hadron Engine
Level: 50
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Electro Drift
- Draco Meteor
- Volt Switch
- Protect

Flutter Mane @ Booster Energy
Ability: Protosynthesis
Level: 50
Tera Type: Stellar
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Tera Blast
- Protect

Incineroar @ Safety Goggles
Ability: Intimidate
Level: 50
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
- Flare Blitz
- Knock Off
- Fake Out
- Parting Shot

Rillaboom @ Assault Vest
Ability: Grassy Surge
Level: 50
Tera Type: Fire
EVs: 252 HP / 116 Atk / 4 Def / 132 SpD / 4 Spe
Adamant Nature
- Grassy Glide
- Wood Hammer
- Fake Out
- U-turn

Landorus @ Choice Scarf
Ability: Sheer Force
Level: 50
Tera Type: Flying
EVs: 4 HP / 252 SpA / 252 Spe
Modest Nature
- Earth Power
- Sludge Bomb
- Psychic
- U-turn

Urshifu @ Focus Sash
Ability: Unseen Fist
Level: 50
Tera Type: Poison
EVs: 4 HP / 252 Atk / 252 Spe
Jolly Nature
- Wicked Blow
- Close Combat
- Sucker Punch
- Protect
""",
    description="Standard goodstuffs with excellent Pokemon. Flexible game plan with both offensive and defensive options.",
    strengths=["Flexible leads", "Good type coverage", "Strong individual Pokemon"],
    weaknesses=["No dedicated mode", "Can be out-sped", "Somewhat predictable"],
    regulation="G",
    source="Tournament archetype",
    difficulty="beginner"
)

# =============================================================================
# HYPER OFFENSE
# =============================================================================
HYPER_OFFENSE_TEAM_1 = SampleTeam(
    name="Tailwind Hyper Offense",
    archetype="hyper_offense",
    pokemon=["Tornadus", "Flutter Mane", "Chien-Pao", "Urshifu", "Chi-Yu", "Landorus"],
    paste="""Tornadus @ Focus Sash
Ability: Prankster
Level: 50
Tera Type: Ghost
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Bleakwind Storm
- Tailwind
- Taunt
- Protect

Flutter Mane @ Choice Specs
Ability: Protosynthesis
Level: 50
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Mystical Fire
- Dazzling Gleam

Chien-Pao @ Focus Sash
Ability: Sword of Ruin
Level: 50
Tera Type: Ghost
EVs: 4 HP / 252 Atk / 252 Spe
Jolly Nature
- Ice Spinner
- Crunch
- Sacred Sword
- Protect

Urshifu @ Choice Band
Ability: Unseen Fist
Level: 50
Tera Type: Dark
EVs: 4 HP / 252 Atk / 252 Spe
Jolly Nature
- Wicked Blow
- Close Combat
- Sucker Punch
- U-turn

Chi-Yu @ Choice Specs
Ability: Beads of Ruin
Level: 50
Tera Type: Ghost
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Heat Wave
- Dark Pulse
- Overheat
- Psychic

Landorus @ Life Orb
Ability: Sheer Force
Level: 50
Tera Type: Flying
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Earth Power
- Sludge Bomb
- Psychic
- Protect
""",
    description="Pure offense. Set Tailwind turn 1 and overwhelm with firepower. No defensive Pokemon.",
    strengths=["Massive damage output", "Fast pace", "Punishes passive play"],
    weaknesses=["No defensive backbone", "Trick Room destroys it", "No recovery"],
    regulation="G",
    source="Tournament archetype",
    difficulty="advanced"
)


# =============================================================================
# TEAM LOOKUP
# =============================================================================
ALL_SAMPLE_TEAMS = [
    RAIN_TEAM_1,
    SUN_TEAM_1,
    TRICK_ROOM_TEAM_1,
    GOODSTUFFS_TEAM_1,
    HYPER_OFFENSE_TEAM_1,
]


def get_teams_by_archetype(archetype: str) -> list[SampleTeam]:
    """Get all teams of a specific archetype."""
    archetype_lower = archetype.lower()
    return [t for t in ALL_SAMPLE_TEAMS if t.archetype.lower() == archetype_lower]


def get_teams_with_pokemon(pokemon_name: str) -> list[SampleTeam]:
    """Get all teams containing a specific Pokemon."""
    pokemon_lower = pokemon_name.lower().replace(" ", "-")
    return [
        t for t in ALL_SAMPLE_TEAMS
        if any(pokemon_lower in p.lower().replace(" ", "-") for p in t.pokemon)
    ]


def get_teams_by_regulation(regulation: str) -> list[SampleTeam]:
    """Get all teams for a specific regulation."""
    return [t for t in ALL_SAMPLE_TEAMS if t.regulation.upper() == regulation.upper()]


def get_teams_by_difficulty(difficulty: str) -> list[SampleTeam]:
    """Get teams by difficulty level."""
    return [t for t in ALL_SAMPLE_TEAMS if t.difficulty.lower() == difficulty.lower()]


def get_all_archetypes() -> list[str]:
    """Get list of all available archetypes."""
    return list(set(t.archetype for t in ALL_SAMPLE_TEAMS))
