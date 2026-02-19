"""Bulk offensive damage calculation engine.

Runs N moves × M defenders × K scenarios in a single call,
returning structured results grouped by defender → move → scenario.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..models.move import Move
from ..models.pokemon import PokemonBuild
from .damage import DamageResult, calculate_damage, format_percent
from .modifiers import DamageModifiers

# =============================================================================
# Scenario system
# =============================================================================

@dataclass
class ScenarioConfig:
    """Named modifier preset for bulk calculations."""
    name: str
    display_name: str
    weather: Optional[str] = None
    tera_active: bool = False
    attack_stage: int = 0
    defense_stage: int = 0
    special_attack_stage: int = 0
    special_defense_stage: int = 0
    helping_hand: bool = False
    is_critical: bool = False
    reflect_up: bool = False
    light_screen_up: bool = False


# Pre-built scenarios matching common VGC analysis patterns
DEFAULT_SCENARIOS: dict[str, ScenarioConfig] = {
    "normal": ScenarioConfig(
        name="normal",
        display_name="Normal",
    ),
    "tera": ScenarioConfig(
        name="tera",
        display_name="Tera",
        tera_active=True,
    ),
    "rain": ScenarioConfig(
        name="rain",
        display_name="Rain",
        weather="rain",
    ),
    "sun": ScenarioConfig(
        name="sun",
        display_name="Sun",
        weather="sun",
    ),
    "rain_tera": ScenarioConfig(
        name="rain_tera",
        display_name="Rain + Tera",
        weather="rain",
        tera_active=True,
    ),
    "sun_tera": ScenarioConfig(
        name="sun_tera",
        display_name="Sun + Tera",
        weather="sun",
        tera_active=True,
    ),
    "intimidate": ScenarioConfig(
        name="intimidate",
        display_name="Intimidate (-1 Atk)",
        attack_stage=-1,
    ),
    "helping_hand": ScenarioConfig(
        name="helping_hand",
        display_name="Helping Hand",
        helping_hand=True,
    ),
}


def build_scenario_modifiers(
    scenario: ScenarioConfig,
    attacker: PokemonBuild,
    move: Move,
) -> DamageModifiers:
    """Convert a ScenarioConfig into a DamageModifiers object.

    Special case: if the move always crits (e.g. Surging Strikes),
    Intimidate's -1 Atk stage is ignored because critical hits
    bypass negative attack stages.
    """
    attack_stage = scenario.attack_stage

    # Critical hits ignore negative attack stat stages
    if move.always_crit and attack_stage < 0:
        attack_stage = 0

    return DamageModifiers(
        is_doubles=True,
        multiple_targets=move.is_spread,
        weather=scenario.weather,
        tera_type=attacker.tera_type if scenario.tera_active else None,
        tera_active=scenario.tera_active,
        attack_stage=attack_stage,
        defense_stage=scenario.defense_stage,
        special_attack_stage=scenario.special_attack_stage,
        special_defense_stage=scenario.special_defense_stage,
        helping_hand=scenario.helping_hand,
        is_critical=scenario.is_critical or move.always_crit,
        reflect_up=scenario.reflect_up,
        light_screen_up=scenario.light_screen_up,
        attacker_item=attacker.item,
        attacker_ability=attacker.ability,
    )


# =============================================================================
# Result structures
# =============================================================================

@dataclass
class BulkCalcResult:
    """Single damage calculation result within a bulk run."""
    defender_name: str
    move_name: str
    scenario_name: str
    scenario_display: str
    min_pct: float
    max_pct: float
    min_damage: int
    max_damage: int
    defender_hp: int
    ko_chance: str
    calc_string: str


@dataclass
class BulkCalcSummary:
    """Aggregated results from a bulk damage calculation run."""
    attacker_name: str
    attacker_spread_str: str
    move_names: list[str]
    scenario_names: list[str]
    total_calcs: int
    results: list[BulkCalcResult]
    # Keyed by scenario name
    ohko_counts: dict[str, int] = field(default_factory=dict)
    twohko_counts: dict[str, int] = field(default_factory=dict)
    defender_spreads: dict[str, str] = field(default_factory=dict)
    defender_items: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Calc string builder
# =============================================================================

def _format_ev_label(pokemon: PokemonBuild, stat: str) -> str:
    """Format a single EV stat for the calc string, e.g. '252 Atk' or '252+ Atk'."""
    evs = getattr(pokemon.evs, stat, 0)
    if evs == 0:
        return ""

    stat_abbrevs = {
        "hp": "HP",
        "attack": "Atk",
        "defense": "Def",
        "special_attack": "SpA",
        "special_defense": "SpD",
        "speed": "Spe",
    }
    abbrev = stat_abbrevs.get(stat, stat)

    # Check nature boost
    nature_mod = pokemon.get_nature_modifier(stat)
    if nature_mod > 1.0:
        return f"{evs}+ {abbrev}"
    elif nature_mod < 1.0:
        return f"{evs}- {abbrev}"
    return f"{evs} {abbrev}"


def _build_attacker_label(attacker: PokemonBuild) -> str:
    """Build attacker portion: '252+ Atk Choice Scarf Urshifu-Rapid-Strike'."""
    parts = []

    # Find main offensive stat
    if attacker.evs.attack >= attacker.evs.special_attack:
        atk_label = _format_ev_label(attacker, "attack")
    else:
        atk_label = _format_ev_label(attacker, "special_attack")

    if atk_label:
        parts.append(atk_label)

    if attacker.item:
        item_display = attacker.item.replace("-", " ").title()
        parts.append(item_display)

    name_display = attacker.name.replace("-", " ").title()
    # Preserve common suffixes
    suffixes = [
        "Rapid Strike", "Single Strike", "Therian",
        "Incarnate", "Hearthflame", "Wellspring", "Cornerstone",
    ]
    for suffix in suffixes:
        hyphenated = suffix.replace(" ", "-")
        if hyphenated.lower() in attacker.name.lower():
            name_display = attacker.name.replace("-", " ").title()
            # Replace with hyphenated form for readability
            name_display = name_display.replace(suffix, suffix.replace(" ", "-"))

    parts.append(name_display)
    return " ".join(parts)


def _build_defender_label(defender: PokemonBuild) -> str:
    """Build defender portion: '0 HP / 4 Def Chien-Pao'."""
    ev_parts = []
    for stat in ["hp", "defense", "special_defense"]:
        label = _format_ev_label(defender, stat)
        if label:
            ev_parts.append(label)

    name_display = defender.name.replace("-", " ").title()

    if ev_parts:
        return " / ".join(ev_parts) + " " + name_display
    return name_display


def build_calc_string(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move: Move,
    result: DamageResult,
    scenario: ScenarioConfig,
) -> str:
    """Build a Showdown-style calc string.

    Example output:
    "252+ Atk Choice Scarf Urshifu-Rapid-Strike Surging Strikes vs.
     0 HP / 4 Def Chien-Pao: 123-147 (79.4-94.8%) -- guaranteed 2HKO"
    """
    atk_label = _build_attacker_label(attacker)
    move_display = move.name.replace("-", " ").title()
    def_label = _build_defender_label(defender)

    min_pct = format_percent(result.min_percent)
    max_pct = format_percent(result.max_percent)

    verdict = result.ko_chance

    dmg = f"{result.min_damage}-{result.max_damage}"
    pct = f"{min_pct}-{max_pct}%"
    calc = (
        f"{atk_label} {move_display} vs. {def_label}: "
        f"{dmg} ({pct}) -- {verdict}"
    )

    # Add scenario tag if not normal
    if scenario.name != "normal":
        calc = f"[{scenario.display_name}] {calc}"

    return calc


# =============================================================================
# Bulk calc engine
# =============================================================================

def run_bulk_calcs(
    attacker: PokemonBuild,
    moves: list[Move],
    defenders: list[PokemonBuild],
    scenarios: list[ScenarioConfig],
    defender_tera_types: Optional[dict[str, str]] = None,
) -> BulkCalcSummary:
    """Run damage calculations for all combinations of moves × defenders × scenarios.

    Args:
        attacker: The attacking Pokemon build
        moves: List of moves to test (1-4)
        defenders: List of defending Pokemon builds
        scenarios: List of scenario configs to test

    Returns:
        BulkCalcSummary with all results grouped and counted
    """
    results: list[BulkCalcResult] = []
    ohko_counts: dict[str, int] = {s.name: 0 for s in scenarios}
    twohko_counts: dict[str, int] = {s.name: 0 for s in scenarios}
    defender_spreads: dict[str, str] = {}
    defender_items: dict[str, str] = {}

    # Build attacker spread string
    nature_name = attacker.nature.value.title()
    evs = attacker.evs
    attacker_spread_str = (
        f"{nature_name} {evs.hp}/{evs.attack}/{evs.defense}/"
        f"{evs.special_attack}/{evs.special_defense}/{evs.speed}"
    )

    for defender in defenders:
        # Cache defender spread info
        def_evs = defender.evs
        def_nature = defender.nature.value.title()
        defender_spreads[defender.name] = (
            f"{def_nature} {def_evs.hp}/{def_evs.attack}/{def_evs.defense}/"
            f"{def_evs.special_attack}/{def_evs.special_defense}/{def_evs.speed}"
        )
        defender_items[defender.name] = defender.item or "None"

        for move in moves:
            for scenario in scenarios:
                modifiers = build_scenario_modifiers(scenario, attacker, move)

                # Set defender item/ability on modifiers
                modifiers.defender_item = defender.item
                modifiers.defender_ability = defender.ability

                # Set defender Tera type if specified
                if defender_tera_types and defender.name in defender_tera_types:
                    modifiers.defender_tera_type = defender_tera_types[defender.name]
                    modifiers.defender_tera_active = True

                result = calculate_damage(attacker, defender, move, modifiers)

                calc_string = build_calc_string(attacker, defender, move, result, scenario)

                bulk_result = BulkCalcResult(
                    defender_name=defender.name,
                    move_name=move.name,
                    scenario_name=scenario.name,
                    scenario_display=scenario.display_name,
                    min_pct=result.min_percent,
                    max_pct=result.max_percent,
                    min_damage=result.min_damage,
                    max_damage=result.max_damage,
                    defender_hp=result.defender_hp,
                    ko_chance=result.ko_chance,
                    calc_string=calc_string,
                )
                results.append(bulk_result)

                # Count KOs per scenario (best move per defender)
                if result.is_guaranteed_ohko:
                    ohko_counts[scenario.name] += 1
                elif result.ko_chance in ("2HKO", "possible 2HKO"):
                    twohko_counts[scenario.name] += 1

    return BulkCalcSummary(
        attacker_name=attacker.name,
        attacker_spread_str=attacker_spread_str,
        move_names=[m.name for m in moves],
        scenario_names=[s.name for s in scenarios],
        total_calcs=len(results),
        results=results,
        ohko_counts=ohko_counts,
        twohko_counts=twohko_counts,
        defender_spreads=defender_spreads,
        defender_items=defender_items,
    )


def get_results_for_defender(
    summary: BulkCalcSummary,
    defender_name: str,
) -> list[BulkCalcResult]:
    """Filter results for a specific defender."""
    return [r for r in summary.results if r.defender_name == defender_name]


def get_results_for_scenario(
    summary: BulkCalcSummary,
    scenario_name: str,
) -> list[BulkCalcResult]:
    """Filter results for a specific scenario."""
    return [r for r in summary.results if r.scenario_name == scenario_name]


def get_best_move_per_defender(
    summary: BulkCalcSummary,
    scenario_name: str = "normal",
) -> dict[str, BulkCalcResult]:
    """For each defender, find the move with the highest max damage % in a scenario."""
    best: dict[str, BulkCalcResult] = {}
    for r in summary.results:
        if r.scenario_name != scenario_name:
            continue
        if r.defender_name not in best or r.max_pct > best[r.defender_name].max_pct:
            best[r.defender_name] = r
    return best
