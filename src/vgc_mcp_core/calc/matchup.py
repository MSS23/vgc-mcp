"""Matchup analysis for team threat assessment."""

from dataclasses import dataclass
from typing import Optional

from ..models.pokemon import PokemonBuild, BaseStats, Nature, EVSpread, IVSpread
from ..models.move import Move, MoveCategory
from ..models.team import Team
from .damage import calculate_damage, DamageResult
from .stats import calculate_all_stats
from .speed import SPEED_BENCHMARKS
from .modifiers import DamageModifiers, get_type_effectiveness


@dataclass
class MatchupResult:
    """Result of analyzing how one Pokemon matches up against another."""
    attacker_name: str
    defender_name: str
    can_ohko: bool
    can_2hko: bool
    best_move: Optional[str]
    damage_range: str
    ko_chance: str
    outspeeds: bool
    is_check: bool  # Outspeeds AND can OHKO
    is_counter: bool  # Survives best attack AND can OHKO


@dataclass
class ThreatAnalysis:
    """Analysis of how a team handles a specific threat."""
    threat_name: str
    threat_speed: int
    ohko_by: list[str]  # Team members that OHKO the threat
    twohko_by: list[str]  # Team members that 2HKO
    checks: list[str]  # Can revenge kill (outspeeds + KOs)
    counters: list[str]  # Survives + KOs
    threatened: list[str]  # Team members threatened by this Pokemon
    survives: list[str]  # Team members that survive the threat's attacks
    notes: list[str]


@dataclass
class TeamThreatSummary:
    """Summary of threats to a team."""
    major_threats: list[str]  # Threats that OHKO 3+ team members
    moderate_threats: list[str]  # Threats that OHKO 2 team members
    checks_available: dict[str, list[str]]  # Threat -> list of checks
    counters_available: dict[str, list[str]]  # Threat -> list of counters
    coverage_gaps: list[str]  # Types the team struggles against


# Common threat Pokemon with typical sets
COMMON_THREATS = {
    "flutter-mane": {
        "base_stats": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
        "types": ["Ghost", "Fairy"],
        "nature": Nature.TIMID,
        "evs": EVSpread(hp=4, special_attack=252, speed=252),
        "ability": "protosynthesis",
        "item": "choice-specs",
        "moves": ["moonblast", "shadow-ball", "dazzling-gleam", "mystical-fire"],
        "move_data": {
            "moonblast": {"power": 95, "type": "Fairy", "category": "special"},
            "shadow-ball": {"power": 80, "type": "Ghost", "category": "special"},
            "dazzling-gleam": {"power": 80, "type": "Fairy", "category": "special", "spread": True},
            "mystical-fire": {"power": 75, "type": "Fire", "category": "special"},
        }
    },
    "dragapult": {
        "base_stats": BaseStats(hp=88, attack=120, defense=75, special_attack=100, special_defense=75, speed=142),
        "types": ["Dragon", "Ghost"],
        "nature": Nature.JOLLY,
        "evs": EVSpread(attack=252, speed=252, hp=4),
        "ability": "clear-body",
        "item": "choice-band",
        "moves": ["dragon-darts", "phantom-force", "u-turn", "draco-meteor"],
        "move_data": {
            "dragon-darts": {"power": 50, "type": "Dragon", "category": "physical"},
            "phantom-force": {"power": 90, "type": "Ghost", "category": "physical"},
            "u-turn": {"power": 70, "type": "Bug", "category": "physical"},
            "draco-meteor": {"power": 130, "type": "Dragon", "category": "special"},
        }
    },
    "urshifu-rapid-strike": {
        "base_stats": BaseStats(hp=100, attack=130, defense=100, special_attack=63, special_defense=60, speed=97),
        "types": ["Fighting", "Water"],
        "nature": Nature.JOLLY,
        "evs": EVSpread(attack=252, speed=252, hp=4),
        "ability": "unseen-fist",
        "item": "choice-scarf",
        "moves": ["surging-strikes", "close-combat", "u-turn", "aqua-jet"],
        "move_data": {
            "surging-strikes": {"power": 25, "type": "Water", "category": "physical"},  # Hits 3x, always crits
            "close-combat": {"power": 120, "type": "Fighting", "category": "physical"},
            "u-turn": {"power": 70, "type": "Bug", "category": "physical"},
            "aqua-jet": {"power": 40, "type": "Water", "category": "physical"},
        }
    },
    "chi-yu": {
        "base_stats": BaseStats(hp=55, attack=80, defense=80, special_attack=135, special_defense=120, speed=100),
        "types": ["Dark", "Fire"],
        "nature": Nature.TIMID,
        "evs": EVSpread(special_attack=252, speed=252, hp=4),
        "ability": "beads-of-ruin",
        "item": "choice-specs",
        "moves": ["heat-wave", "dark-pulse", "overheat", "snarl"],
        "move_data": {
            "heat-wave": {"power": 95, "type": "Fire", "category": "special", "spread": True},
            "dark-pulse": {"power": 80, "type": "Dark", "category": "special"},
            "overheat": {"power": 130, "type": "Fire", "category": "special"},
            "snarl": {"power": 55, "type": "Dark", "category": "special", "spread": True},
        }
    },
    "chien-pao": {
        "base_stats": BaseStats(hp=80, attack=120, defense=80, special_attack=90, special_defense=65, speed=135),
        "types": ["Dark", "Ice"],
        "nature": Nature.JOLLY,
        "evs": EVSpread(attack=252, speed=252, hp=4),
        "ability": "sword-of-ruin",
        "item": "focus-sash",
        "moves": ["icicle-crash", "sucker-punch", "sacred-sword", "ice-shard"],
        "move_data": {
            "icicle-crash": {"power": 85, "type": "Ice", "category": "physical"},
            "sucker-punch": {"power": 70, "type": "Dark", "category": "physical"},
            "sacred-sword": {"power": 90, "type": "Fighting", "category": "physical"},
            "ice-shard": {"power": 40, "type": "Ice", "category": "physical"},
        }
    },
    "ting-lu": {
        "base_stats": BaseStats(hp=155, attack=110, defense=125, special_attack=55, special_defense=80, speed=45),
        "types": ["Dark", "Ground"],
        "nature": Nature.CAREFUL,
        "evs": EVSpread(hp=252, special_defense=252, defense=4),
        "ability": "vessel-of-ruin",
        "item": "sitrus-berry",
        "moves": ["earthquake", "stomping-tantrum", "rock-slide", "protect"],
        "move_data": {
            "earthquake": {"power": 100, "type": "Ground", "category": "physical", "spread": True},
            "stomping-tantrum": {"power": 75, "type": "Ground", "category": "physical"},
            "rock-slide": {"power": 75, "type": "Rock", "category": "physical", "spread": True},
            "protect": {"power": 0, "type": "Normal", "category": "status"},
        }
    },
    "wo-chien": {
        "base_stats": BaseStats(hp=85, attack=85, defense=100, special_attack=95, special_defense=135, speed=70),
        "types": ["Dark", "Grass"],
        "nature": Nature.CALM,
        "evs": EVSpread(hp=252, special_defense=252, defense=4),
        "ability": "tablets-of-ruin",
        "item": "leftovers",
        "moves": ["giga-drain", "leech-seed", "pollen-puff", "protect"],
        "move_data": {
            "giga-drain": {"power": 75, "type": "Grass", "category": "special"},
            "leech-seed": {"power": 0, "type": "Grass", "category": "status"},
            "pollen-puff": {"power": 90, "type": "Bug", "category": "special"},
            "protect": {"power": 0, "type": "Normal", "category": "status"},
        }
    },
    "iron-hands": {
        "base_stats": BaseStats(hp=154, attack=140, defense=108, special_attack=50, special_defense=68, speed=50),
        "types": ["Fighting", "Electric"],
        "nature": Nature.ADAMANT,
        "evs": EVSpread(hp=252, attack=252, defense=4),
        "ability": "quark-drive",
        "item": "assault-vest",
        "moves": ["drain-punch", "wild-charge", "fake-out", "ice-punch"],
        "move_data": {
            "drain-punch": {"power": 75, "type": "Fighting", "category": "physical"},
            "wild-charge": {"power": 90, "type": "Electric", "category": "physical"},
            "fake-out": {"power": 40, "type": "Normal", "category": "physical"},
            "ice-punch": {"power": 75, "type": "Ice", "category": "physical"},
        }
    },
    "rillaboom": {
        "base_stats": BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85),
        "types": ["Grass"],
        "nature": Nature.ADAMANT,
        "evs": EVSpread(hp=252, attack=252, speed=4),
        "ability": "grassy-surge",
        "item": "assault-vest",
        "moves": ["grassy-glide", "wood-hammer", "fake-out", "u-turn"],
        "move_data": {
            "grassy-glide": {"power": 55, "type": "Grass", "category": "physical"},  # +1 priority in terrain
            "wood-hammer": {"power": 120, "type": "Grass", "category": "physical"},
            "fake-out": {"power": 40, "type": "Normal", "category": "physical"},
            "u-turn": {"power": 70, "type": "Bug", "category": "physical"},
        }
    },
    "incineroar": {
        "base_stats": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
        "types": ["Fire", "Dark"],
        "nature": Nature.CAREFUL,
        "evs": EVSpread(hp=252, special_defense=252, defense=4),
        "ability": "intimidate",
        "item": "safety-goggles",
        "moves": ["flare-blitz", "knock-off", "fake-out", "parting-shot"],
        "move_data": {
            "flare-blitz": {"power": 120, "type": "Fire", "category": "physical"},
            "knock-off": {"power": 65, "type": "Dark", "category": "physical"},
            "fake-out": {"power": 40, "type": "Normal", "category": "physical"},
            "parting-shot": {"power": 0, "type": "Dark", "category": "status"},
        }
    },
    "kingambit": {
        "base_stats": BaseStats(hp=100, attack=135, defense=120, special_attack=60, special_defense=85, speed=50),
        "types": ["Dark", "Steel"],
        "nature": Nature.ADAMANT,
        "evs": EVSpread(hp=252, attack=252, defense=4),
        "ability": "supreme-overlord",
        "item": "assault-vest",
        "moves": ["kowtow-cleave", "iron-head", "sucker-punch", "low-kick"],
        "move_data": {
            "kowtow-cleave": {"power": 85, "type": "Dark", "category": "physical"},
            "iron-head": {"power": 80, "type": "Steel", "category": "physical"},
            "sucker-punch": {"power": 70, "type": "Dark", "category": "physical"},
            "low-kick": {"power": 1, "type": "Fighting", "category": "physical"},  # Weight-based
        }
    },
    "gholdengo": {
        "base_stats": BaseStats(hp=87, attack=60, defense=95, special_attack=133, special_defense=91, speed=84),
        "types": ["Steel", "Ghost"],
        "nature": Nature.MODEST,
        "evs": EVSpread(hp=252, special_attack=252, speed=4),
        "ability": "good-as-gold",
        "item": "choice-specs",
        "moves": ["make-it-rain", "shadow-ball", "dazzling-gleam", "trick"],
        "move_data": {
            "make-it-rain": {"power": 120, "type": "Steel", "category": "special", "spread": True},
            "shadow-ball": {"power": 80, "type": "Ghost", "category": "special"},
            "dazzling-gleam": {"power": 80, "type": "Fairy", "category": "special", "spread": True},
            "trick": {"power": 0, "type": "Psychic", "category": "status"},
        }
    },
    "tornadus": {
        "base_stats": BaseStats(hp=79, attack=115, defense=70, special_attack=125, special_defense=80, speed=111),
        "types": ["Flying"],
        "nature": Nature.TIMID,
        "evs": EVSpread(special_attack=252, speed=252, hp=4),
        "ability": "prankster",
        "item": "focus-sash",
        "moves": ["bleakwind-storm", "hurricane", "tailwind", "rain-dance"],
        "move_data": {
            "bleakwind-storm": {"power": 100, "type": "Flying", "category": "special", "spread": True},
            "hurricane": {"power": 110, "type": "Flying", "category": "special"},
            "tailwind": {"power": 0, "type": "Flying", "category": "status"},
            "rain-dance": {"power": 0, "type": "Water", "category": "status"},
        }
    },
    "landorus": {
        "base_stats": BaseStats(hp=89, attack=125, defense=90, special_attack=115, special_defense=80, speed=101),
        "types": ["Ground", "Flying"],
        "nature": Nature.ADAMANT,
        "evs": EVSpread(attack=252, speed=252, hp=4),
        "ability": "sheer-force",
        "item": "life-orb",
        "moves": ["sandsear-storm", "earth-power", "sludge-bomb", "protect"],
        "move_data": {
            "sandsear-storm": {"power": 100, "type": "Ground", "category": "special", "spread": True},
            "earth-power": {"power": 90, "type": "Ground", "category": "special"},
            "sludge-bomb": {"power": 90, "type": "Poison", "category": "special"},
            "protect": {"power": 0, "type": "Normal", "category": "status"},
        }
    },
    "raging-bolt": {
        "base_stats": BaseStats(hp=125, attack=73, defense=91, special_attack=137, special_defense=89, speed=91),
        "types": ["Electric", "Dragon"],
        "nature": Nature.MODEST,
        "evs": EVSpread(hp=252, special_attack=252, speed=4),
        "ability": "protosynthesis",
        "item": "booster-energy",
        "moves": ["thunderclap", "draco-meteor", "thunderbolt", "protect"],
        "move_data": {
            "thunderclap": {"power": 70, "type": "Electric", "category": "special"},
            "draco-meteor": {"power": 130, "type": "Dragon", "category": "special"},
            "thunderbolt": {"power": 90, "type": "Electric", "category": "special"},
            "protect": {"power": 0, "type": "Normal", "category": "status"},
        }
    },
}


def create_threat_pokemon(threat_name: str) -> Optional[PokemonBuild]:
    """Create a PokemonBuild from threat data."""
    if threat_name not in COMMON_THREATS:
        return None

    data = COMMON_THREATS[threat_name]
    return PokemonBuild(
        name=threat_name,
        base_stats=data["base_stats"],
        types=data["types"],
        nature=data["nature"],
        evs=data["evs"],
        ivs=IVSpread(),
        level=50,
        ability=data["ability"],
        item=data["item"],
        moves=data["moves"]
    )


def create_threat_move(threat_name: str, move_name: str) -> Optional[Move]:
    """Create a Move object from threat move data."""
    if threat_name not in COMMON_THREATS:
        return None

    threat_data = COMMON_THREATS[threat_name]
    if move_name not in threat_data["move_data"]:
        return None

    move_data = threat_data["move_data"][move_name]

    return Move(
        name=move_name,
        type=move_data["type"],
        category=MoveCategory.PHYSICAL if move_data["category"] == "physical" else (
            MoveCategory.SPECIAL if move_data["category"] == "special" else MoveCategory.STATUS
        ),
        power=move_data["power"],
        accuracy=100,
        is_spread=move_data.get("spread", False)
    )


def analyze_single_matchup(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    attacker_moves: list[Move],
    defender_moves: list[Move] = None,
    modifiers: DamageModifiers = None
) -> MatchupResult:
    """
    Analyze how well an attacker matches up against a defender.

    Args:
        attacker: The attacking Pokemon
        defender: The defending Pokemon
        attacker_moves: Attacker's available moves
        defender_moves: Defender's moves (to check if attacker survives)
        modifiers: Battle modifiers

    Returns:
        MatchupResult with OHKO/2HKO info and check/counter status
    """
    if modifiers is None:
        modifiers = DamageModifiers(is_doubles=True)

    # Apply Ruinous abilities from both Pokemon
    from .abilities import apply_ruin_abilities
    apply_ruin_abilities(
        attacker_ability=attacker.ability,
        defender_ability=defender.ability,
        modifiers=modifiers
    )

    attacker_stats = calculate_all_stats(attacker)
    defender_stats = calculate_all_stats(defender)

    attacker_speed = attacker_stats["speed"]
    defender_speed = defender_stats["speed"]
    outspeeds = attacker_speed > defender_speed

    # Find best move and damage
    best_result = None
    best_move_name = None
    best_damage_pct = 0

    for move in attacker_moves:
        if not move.is_damaging:
            continue

        result = calculate_damage(attacker, defender, move, modifiers)

        if result.max_percent > best_damage_pct:
            best_damage_pct = result.max_percent
            best_result = result
            best_move_name = move.name

    if best_result is None:
        return MatchupResult(
            attacker_name=attacker.name,
            defender_name=defender.name,
            can_ohko=False,
            can_2hko=False,
            best_move=None,
            damage_range="0-0 (0%-0%)",
            ko_chance="No damaging moves",
            outspeeds=outspeeds,
            is_check=False,
            is_counter=False
        )

    can_ohko = best_result.is_possible_ohko
    # Guaranteed 2HKO requires min damage >= 50% (two min rolls = 100%+)
    # Possible 2HKO requires max damage >= 50% (two max rolls = 100%+)
    guaranteed_2hko = best_result.min_percent >= 50
    can_2hko = best_result.max_percent >= 50  # Possible but not guaranteed

    # Check if attacker survives defender's best attack
    survives_attack = True
    if defender_moves:
        for move in defender_moves:
            if not move.is_damaging:
                continue

            result = calculate_damage(defender, attacker, move, modifiers)
            if result.is_possible_ohko:
                survives_attack = False
                break

    is_check = outspeeds and can_ohko
    is_counter = survives_attack and can_ohko

    return MatchupResult(
        attacker_name=attacker.name,
        defender_name=defender.name,
        can_ohko=can_ohko,
        can_2hko=can_2hko,
        best_move=best_move_name,
        damage_range=best_result.damage_range,
        ko_chance=best_result.ko_chance,
        outspeeds=outspeeds,
        is_check=is_check,
        is_counter=is_counter
    )


def analyze_threat_matchup(
    team: Team,
    threat_name: str,
    team_moves: dict[str, list[Move]] = None
) -> ThreatAnalysis:
    """
    Analyze how a team handles a specific threat Pokemon.

    Args:
        team: The team to analyze
        threat_name: Name of the threat Pokemon
        team_moves: Dict mapping Pokemon names to their moves

    Returns:
        ThreatAnalysis with detailed breakdown
    """
    threat = create_threat_pokemon(threat_name)
    if not threat:
        return ThreatAnalysis(
            threat_name=threat_name,
            threat_speed=0,
            ohko_by=[],
            twohko_by=[],
            checks=[],
            counters=[],
            threatened=[],
            survives=[],
            notes=[f"Unknown threat: {threat_name}"]
        )

    threat_stats = calculate_all_stats(threat)
    threat_speed = threat_stats["speed"]

    # Get threat's moves
    threat_data = COMMON_THREATS[threat_name]
    threat_moves = [
        create_threat_move(threat_name, move)
        for move in threat_data["moves"]
    ]
    threat_moves = [m for m in threat_moves if m is not None]

    ohko_by = []
    twohko_by = []
    checks = []
    counters = []
    threatened = []
    survives = []
    notes = []

    modifiers = DamageModifiers(is_doubles=True)

    for slot in team.slots:
        pokemon = slot.pokemon
        pokemon_stats = calculate_all_stats(pokemon)
        pokemon_speed = pokemon_stats["speed"]

        # Create moves for this Pokemon if not provided
        if team_moves and pokemon.name in team_moves:
            pokemon_moves = team_moves[pokemon.name]
        else:
            # Create generic moves based on Pokemon's types
            pokemon_moves = _create_generic_moves(pokemon)

        # Check if team member can KO threat
        matchup = analyze_single_matchup(pokemon, threat, pokemon_moves, threat_moves, modifiers)

        if matchup.can_ohko:
            ohko_by.append(pokemon.name)
            if matchup.outspeeds:
                checks.append(pokemon.name)
        elif matchup.can_2hko:
            twohko_by.append(pokemon.name)

        # Check if team member survives threat's attacks
        member_survives = True
        for move in threat_moves:
            if not move.is_damaging:
                continue

            # Create fresh modifiers for threat attacking team member
            threat_modifiers = DamageModifiers(is_doubles=True)
            from .abilities import apply_ruin_abilities
            apply_ruin_abilities(
                attacker_ability=threat.ability,
                defender_ability=pokemon.ability,
                modifiers=threat_modifiers
            )

            result = calculate_damage(threat, pokemon, move, threat_modifiers)
            if result.is_possible_ohko:
                member_survives = False
                threatened.append(pokemon.name)
                break

        if member_survives:
            survives.append(pokemon.name)
            if matchup.can_ohko:
                counters.append(pokemon.name)

    # Generate notes
    if len(ohko_by) == 0:
        notes.append(f"WARNING: No Pokemon can OHKO {threat_name}")
    if len(checks) == 0:
        notes.append(f"WARNING: No reliable check to {threat_name}")
    if len(counters) == 0:
        notes.append(f"WARNING: No counter to {threat_name}")
    if len(threatened) >= 4:
        notes.append(f"DANGER: {threat_name} threatens {len(threatened)}/6 team members")

    return ThreatAnalysis(
        threat_name=threat_name,
        threat_speed=threat_speed,
        ohko_by=ohko_by,
        twohko_by=twohko_by,
        checks=checks,
        counters=counters,
        threatened=threatened,
        survives=survives,
        notes=notes
    )


def find_team_threats(team: Team) -> TeamThreatSummary:
    """
    Identify what common threats are problematic for a team.

    Args:
        team: The team to analyze

    Returns:
        TeamThreatSummary with major/moderate threats and available answers
    """
    major_threats = []
    moderate_threats = []
    checks_available = {}
    counters_available = {}

    for threat_name in COMMON_THREATS:
        analysis = analyze_threat_matchup(team, threat_name)

        # Categorize threat severity
        threat_count = len(analysis.threatened)
        if threat_count >= 4:
            major_threats.append(threat_name)
        elif threat_count >= 2:
            moderate_threats.append(threat_name)

        if analysis.checks:
            checks_available[threat_name] = analysis.checks
        if analysis.counters:
            counters_available[threat_name] = analysis.counters

    # Analyze type coverage gaps
    coverage_gaps = _find_coverage_gaps(team)

    return TeamThreatSummary(
        major_threats=major_threats,
        moderate_threats=moderate_threats,
        checks_available=checks_available,
        counters_available=counters_available,
        coverage_gaps=coverage_gaps
    )


def check_type_coverage(team: Team, target_type: str) -> dict:
    """
    Check how well a team can hit a specific type.

    Args:
        team: The team to analyze
        target_type: The type to check coverage against

    Returns:
        Dict with Pokemon that can hit super effectively
    """
    super_effective = []
    neutral = []
    resisted = []

    for slot in team.slots:
        pokemon = slot.pokemon

        # Check Pokemon's STAB types against target
        best_effectiveness = 1.0
        best_type = None

        for poke_type in pokemon.types:
            eff = get_type_effectiveness(poke_type, [target_type])
            if eff > best_effectiveness:
                best_effectiveness = eff
                best_type = poke_type

        if best_effectiveness >= 2.0:
            super_effective.append({
                "pokemon": pokemon.name,
                "type": best_type,
                "effectiveness": best_effectiveness
            })
        elif best_effectiveness >= 1.0:
            neutral.append(pokemon.name)
        else:
            resisted.append(pokemon.name)

    return {
        "target_type": target_type,
        "super_effective": super_effective,
        "neutral": neutral,
        "resisted": resisted,
        "has_coverage": len(super_effective) > 0
    }


def analyze_defensive_matchup(team: Team, attacking_type: str) -> dict:
    """
    Check how well a team resists a specific attacking type.

    Args:
        team: The team to analyze
        attacking_type: The type of attack to check

    Returns:
        Dict with resistances, immunities, and weaknesses
    """
    immune = []
    resists = []
    neutral = []
    weak = []

    for slot in team.slots:
        pokemon = slot.pokemon
        eff = get_type_effectiveness(attacking_type, pokemon.types)

        if eff == 0:
            immune.append(pokemon.name)
        elif eff <= 0.5:
            resists.append(pokemon.name)
        elif eff >= 2.0:
            weak.append(pokemon.name)
        else:
            neutral.append(pokemon.name)

    return {
        "attacking_type": attacking_type,
        "immune": immune,
        "resists": resists,
        "neutral": neutral,
        "weak": weak,
        "safe_switch_ins": len(immune) + len(resists)
    }


def _create_generic_moves(pokemon: PokemonBuild) -> list[Move]:
    """Create generic STAB moves for a Pokemon based on its types."""
    moves = []

    for poke_type in pokemon.types:
        # Add a physical and special move for each type
        moves.append(Move(
            name=f"{poke_type.lower()}-move-physical",
            type=poke_type,
            category=MoveCategory.PHYSICAL,
            power=80,
            accuracy=100
        ))
        moves.append(Move(
            name=f"{poke_type.lower()}-move-special",
            type=poke_type,
            category=MoveCategory.SPECIAL,
            power=80,
            accuracy=100
        ))

    return moves


def _find_coverage_gaps(team: Team) -> list[str]:
    """Find types the team lacks super effective coverage against."""
    all_types = [
        "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
        "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
        "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
    ]

    gaps = []

    for target_type in all_types:
        coverage = check_type_coverage(team, target_type)
        if not coverage["has_coverage"]:
            gaps.append(target_type)

    return gaps
