"""Speed control analysis for Trick Room, Tailwind, and stat drops."""

import math
from dataclasses import dataclass
from typing import Optional

from ..models.team import Team
from ..models.pokemon import PokemonBuild
from .stats import calculate_all_stats
from .speed import SPEED_BENCHMARKS


# Speed modifiers from various sources
SPEED_STAGE_MULTIPLIERS = {
    -6: 2/8,   # 0.25x
    -5: 2/7,   # ~0.286x
    -4: 2/6,   # ~0.333x
    -3: 2/5,   # 0.4x
    -2: 2/4,   # 0.5x
    -1: 2/3,   # ~0.667x
    0: 1.0,
    1: 3/2,    # 1.5x
    2: 4/2,    # 2.0x
    3: 5/2,    # 2.5x
    4: 6/2,    # 3.0x
    5: 7/2,    # 3.5x
    6: 8/2,    # 4.0x
}

# Common speed control moves and their effects
SPEED_CONTROL_MOVES = {
    # Speed drops
    "icy-wind": {"stage": -1, "targets": "opponents"},
    "electroweb": {"stage": -1, "targets": "opponents"},
    "bulldoze": {"stage": -1, "targets": "adjacent"},
    "rock-tomb": {"stage": -1, "targets": "single"},
    "bubble-beam": {"stage": -1, "targets": "single", "chance": 10},
    "mud-shot": {"stage": -1, "targets": "single"},
    "scary-face": {"stage": -2, "targets": "single"},
    "cotton-spore": {"stage": -2, "targets": "single"},
    "string-shot": {"stage": -2, "targets": "opponents"},
    "sticky-web": {"stage": -1, "targets": "grounded_entry"},

    # Speed boosts
    "tailwind": {"effect": "tailwind", "duration": 4},
    "dragon-dance": {"stage": +1, "targets": "self"},
    "quiver-dance": {"stage": +1, "targets": "self"},
    "shift-gear": {"stage": +2, "targets": "self"},
    "autotomize": {"stage": +2, "targets": "self"},
    "agility": {"stage": +2, "targets": "self"},
    "rock-polish": {"stage": +2, "targets": "self"},
    "flame-charge": {"stage": +1, "targets": "self"},

    # Speed control
    "trick-room": {"effect": "trick_room", "duration": 5},
    "quash": {"effect": "quash"},
    "after-you": {"effect": "after_you"},
}


@dataclass
class SpeedTier:
    """A Pokemon's speed tier info."""
    name: str
    base_speed: int
    final_speed: int
    nature: str
    evs: int
    modified_speed: Optional[int] = None
    notes: list[str] = None


@dataclass
class SpeedControlAnalysis:
    """Analysis of team under speed control conditions."""
    condition: str  # "trick_room", "tailwind", "-1_stage", etc.
    team_speeds: list[SpeedTier]
    move_order: list[str]  # Pokemon names in move order
    outspeeds: dict[str, list[str]]  # What each Pokemon outspeeds
    notes: list[str]


def apply_speed_modifier(speed: int, modifier: float) -> int:
    """Apply a speed modifier (tailwind, paralysis, etc.)."""
    return int(speed * modifier)


def apply_stage_modifier(speed: int, stages: int) -> int:
    """Apply stat stage modifier to speed."""
    stages = max(-6, min(6, stages))
    return int(speed * SPEED_STAGE_MULTIPLIERS[stages])


def get_team_speeds(team: Team) -> list[SpeedTier]:
    """Get speed tiers for all Pokemon on a team."""
    speeds = []

    for slot in team.slots:
        pokemon = slot.pokemon
        stats = calculate_all_stats(pokemon)

        speeds.append(SpeedTier(
            name=pokemon.name,
            base_speed=pokemon.base_stats.speed,
            final_speed=stats["speed"],
            nature=pokemon.nature.value,
            evs=pokemon.evs.speed,
            notes=[]
        ))

    return sorted(speeds, key=lambda x: x.final_speed, reverse=True)


def analyze_trick_room(team: Team) -> SpeedControlAnalysis:
    """
    Analyze team performance under Trick Room.

    In Trick Room, slower Pokemon move first (with some exceptions).
    """
    speeds = get_team_speeds(team)

    # In Trick Room, reverse order (slowest first)
    tr_order = sorted(speeds, key=lambda x: x.final_speed)

    # Add modified speed (conceptually inverted)
    for tier in tr_order:
        tier.modified_speed = -tier.final_speed  # Conceptual - lower is better
        tier.notes = []

        if tier.final_speed <= 50:
            tier.notes.append("Excellent TR Pokemon")
        elif tier.final_speed <= 70:
            tier.notes.append("Good TR Pokemon")
        elif tier.final_speed >= 100:
            tier.notes.append("Too fast for TR - consider not bringing")

    # Compare against common benchmarks
    outspeeds = {}
    for tier in tr_order:
        outspeeds[tier.name] = []
        for mon, data in SPEED_BENCHMARKS.items():
            # In TR, we "outspeed" if we're slower
            if "min_negative" in data:
                if tier.final_speed < data["min_negative"]:
                    outspeeds[tier.name].append(f"Min Speed {mon}")
            elif "neutral_0ev" in data:
                if tier.final_speed < data["neutral_0ev"]:
                    outspeeds[tier.name].append(f"Uninvested {mon}")

    notes = []
    slow_count = sum(1 for t in tr_order if t.final_speed <= 70)
    fast_count = sum(1 for t in tr_order if t.final_speed >= 100)

    if slow_count >= 4:
        notes.append("Team is well-suited for Trick Room")
    elif slow_count >= 2:
        notes.append("Team has some Trick Room options")
    else:
        notes.append("Team lacks good Trick Room Pokemon")

    if fast_count >= 3:
        notes.append(f"{fast_count} Pokemon are too fast for TR - consider mix mode")

    # Check for TR setters
    tr_setters = ["hatterene", "porygon2", "dusclops", "indeedee-female", "cresselia",
                  "bronzong", "gothitelle", "armarouge", "farigiraf"]
    team_names = [t.name.lower() for t in tr_order]
    has_setter = any(setter in name for name in team_names for setter in tr_setters)

    if not has_setter:
        notes.append("No obvious Trick Room setter on team")

    return SpeedControlAnalysis(
        condition="Trick Room",
        team_speeds=tr_order,
        move_order=[t.name for t in tr_order],
        outspeeds=outspeeds,
        notes=notes
    )


def analyze_tailwind(team: Team) -> SpeedControlAnalysis:
    """
    Analyze team performance with Tailwind active.

    Tailwind doubles Speed for 4 turns.
    """
    speeds = get_team_speeds(team)

    # Apply Tailwind (2x speed)
    for tier in speeds:
        tier.modified_speed = apply_speed_modifier(tier.final_speed, 2.0)
        tier.notes = []

    # Re-sort by modified speed
    tw_order = sorted(speeds, key=lambda x: x.modified_speed, reverse=True)

    # Compare against common benchmarks (max speed variants)
    outspeeds = {}
    for tier in tw_order:
        outspeeds[tier.name] = []
        for mon, data in SPEED_BENCHMARKS.items():
            if "max_positive" in data:
                if tier.modified_speed > data["max_positive"]:
                    outspeeds[tier.name].append(f"Max Speed {mon}")
            if "max_neutral" in data:
                if tier.modified_speed > data["max_neutral"]:
                    if f"Max Speed {mon}" not in outspeeds[tier.name]:
                        outspeeds[tier.name].append(f"Neutral {mon}")

    notes = []

    # Check what the team can outspeed with Tailwind
    fastest_tw = tw_order[0].modified_speed if tw_order else 0

    if fastest_tw >= 400:
        notes.append("Can outspeed max speed Regieleki with Tailwind")
    elif fastest_tw >= 280:
        notes.append("Can outspeed most max speed Pokemon with Tailwind")

    # Check for Tailwind setters
    tw_setters = ["tornadus", "whimsicott", "talonflame", "murkrow", "suicune",
                  "pelipper", "mandibuzz", "kilowattrel", "flamigo"]
    team_names = [t.name.lower() for t in tw_order]
    has_setter = any(setter in name for name in team_names for setter in tw_setters)

    if not has_setter:
        notes.append("No obvious Tailwind setter on team")

    return SpeedControlAnalysis(
        condition="Tailwind (2x Speed)",
        team_speeds=tw_order,
        move_order=[t.name for t in tw_order],
        outspeeds=outspeeds,
        notes=notes
    )


def analyze_speed_drop(team: Team, stages: int = -1) -> SpeedControlAnalysis:
    """
    Analyze opponent speeds after Icy Wind/Electroweb.

    Args:
        team: Your team
        stages: Speed drop stages (negative)
    """
    # For this analysis, we show what benchmark speeds become after the drop
    speeds = get_team_speeds(team)

    # Calculate what common threats' speeds become after the drop
    threat_speeds_after = {}
    for mon, data in SPEED_BENCHMARKS.items():
        if "max_positive" in data:
            after_drop = apply_stage_modifier(data["max_positive"], stages)
            threat_speeds_after[f"Max {mon}"] = after_drop

    notes = []
    move_name = "Icy Wind/Electroweb" if stages == -1 else f"{abs(stages)} Speed drops"
    notes.append(f"After {move_name} on opponents:")

    # For each team member, what can they now outspeed?
    outspeeds = {}
    for tier in speeds:
        outspeeds[tier.name] = []

        for threat, dropped_speed in threat_speeds_after.items():
            if tier.final_speed > dropped_speed:
                outspeeds[tier.name].append(f"{threat} ({dropped_speed})")

    # Add info about key speed tiers after drop
    key_threats = ["flutter-mane", "dragapult", "iron-bundle", "chi-yu"]
    for threat in key_threats:
        if threat in SPEED_BENCHMARKS and "max_positive" in SPEED_BENCHMARKS[threat]:
            orig = SPEED_BENCHMARKS[threat]["max_positive"]
            after = apply_stage_modifier(orig, stages)
            notes.append(f"Max Speed {threat.title()}: {orig} → {after}")

    return SpeedControlAnalysis(
        condition=f"After {abs(stages)} Speed drop(s)",
        team_speeds=speeds,
        move_order=[t.name for t in speeds],
        outspeeds=outspeeds,
        notes=notes
    )


def analyze_paralysis(team: Team) -> SpeedControlAnalysis:
    """Analyze opponent speeds while paralyzed (0.5x Speed)."""
    speeds = get_team_speeds(team)

    # Calculate paralyzed speeds for common threats
    threat_speeds_para = {}
    for mon, data in SPEED_BENCHMARKS.items():
        if "max_positive" in data:
            para_speed = apply_speed_modifier(data["max_positive"], 0.5)
            threat_speeds_para[f"Max {mon}"] = para_speed

    notes = ["Paralysis halves Speed"]

    outspeeds = {}
    for tier in speeds:
        outspeeds[tier.name] = []

        for threat, para_speed in threat_speeds_para.items():
            if tier.final_speed > para_speed:
                outspeeds[tier.name].append(f"{threat} paralyzed ({para_speed})")

    # Key examples
    notes.append("Key paralyzed speeds:")
    if "flutter-mane" in SPEED_BENCHMARKS:
        para = apply_speed_modifier(SPEED_BENCHMARKS["flutter-mane"]["max_positive"], 0.5)
        notes.append(f"Max Flutter Mane paralyzed: {para}")

    if "dragapult" in SPEED_BENCHMARKS:
        para = apply_speed_modifier(SPEED_BENCHMARKS["dragapult"]["max_positive"], 0.5)
        notes.append(f"Max Dragapult paralyzed: {para}")

    return SpeedControlAnalysis(
        condition="Opponent Paralyzed (0.5x)",
        team_speeds=speeds,
        move_order=[t.name for t in speeds],
        outspeeds=outspeeds,
        notes=notes
    )


def get_speed_control_summary(team: Team) -> dict:
    """Get comprehensive speed control analysis for a team."""
    base_speeds = get_team_speeds(team)
    tr_analysis = analyze_trick_room(team)
    tw_analysis = analyze_tailwind(team)
    drop_analysis = analyze_speed_drop(team, -1)

    return {
        "base_speeds": [
            {
                "name": t.name,
                "speed": t.final_speed,
                "base": t.base_speed,
                "nature": t.nature,
                "evs": t.evs
            }
            for t in base_speeds
        ],
        "trick_room": {
            "move_order": tr_analysis.move_order,
            "notes": tr_analysis.notes,
            "speeds": [
                {"name": t.name, "speed": t.final_speed}
                for t in tr_analysis.team_speeds
            ]
        },
        "tailwind": {
            "move_order": tw_analysis.move_order,
            "notes": tw_analysis.notes,
            "speeds": [
                {"name": t.name, "base": t.final_speed, "with_tailwind": t.modified_speed}
                for t in tw_analysis.team_speeds
            ]
        },
        "after_icy_wind": {
            "notes": drop_analysis.notes,
            "outspeeds": drop_analysis.outspeeds
        }
    }
