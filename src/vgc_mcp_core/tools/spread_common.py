"""Shared helpers for EV/SP spread tools: stat inversion, threat caches, constants."""

from dataclasses import dataclass
from typing import Optional

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.damage import DamageResult, calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.stats import calculate_hp, calculate_stat
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import (
    BaseStats,
    EVSpread,
    Nature,
    PokemonBuild,
    StatPointSpread,
)
from vgc_mcp_core.tools.build_helpers import build_pokemon
from vgc_mcp_core.tools.smogon_helpers import (
    get_common_spread as _shared_get_common_spread,
)


def _champions_offensive_stat(base_stats: BaseStats) -> str:
    """Pick the offensive stat ('attack' or 'special_attack') for an SP build."""
    return "attack" if base_stats.attack >= base_stats.special_attack else "special_attack"


def _build_champions_pokemon(
    name: str,
    base_stats: BaseStats,
    types: list[str],
    nature: Nature,
    sps: StatPointSpread,
    item: Optional[str] = None,
    tera_type: Optional[str] = None,
    ability: Optional[str] = None,
) -> PokemonBuild:
    """Construct a format-aware Champions PokemonBuild (emits 'SPs:' pastes)."""
    return build_pokemon(
        name=name,
        base_stats=base_stats,
        types=types,
        nature=nature,
        champions=True,
        spread=sps,
        item=item,
        ability=ability,
        tera_type=tera_type,
    )


META_SYNERGIES = {
    "landorus": ("Life Orb", "Sheer Force"),
    "landorus-incarnate": ("Life Orb", "Sheer Force"),
    "nidoking": ("Life Orb", "Sheer Force"),
    "nidoqueen": ("Life Orb", "Sheer Force"),
    "toucannon": ("Life Orb", "Sheer Force"),
    "conkeldurr": ("Flame Orb", "Guts"),
    "ursaluna": ("Flame Orb", "Guts"),
    "ursaluna-bloodmoon": ("Life Orb", "Mind's Eye"),
    "urshifu": ("Choice Band", "Unseen Fist"),
    "urshifu-single-strike": ("Choice Band", "Unseen Fist"),
    "urshifu-rapid-strike": ("Choice Band", "Unseen Fist"),
    # Ogerpon forms with their signature masks
    "ogerpon": ("Teal Mask", "Defiant"),
    "ogerpon-teal-mask": ("Teal Mask", "Defiant"),
    "ogerpon-hearthflame": ("Hearthflame Mask", "Mold Breaker"),
    "ogerpon-wellspring": ("Wellspring Mask", "Water Absorb"),
    "ogerpon-cornerstone": ("Cornerstone Mask", "Sturdy"),
    # Treasures of Ruin - auto-detect Ruinous abilities
    "chien-pao": ("Focus Sash", "Sword of Ruin"),
    "chi-yu": ("Choice Specs", "Beads of Ruin"),
    "ting-lu": ("Leftovers", "Vessel of Ruin"),
    "wo-chien": ("Rocky Helmet", "Tablets of Ruin"),
}


def _find_min_evs_for_stat(base: int, iv: int, target_stat: int, nature_mod: float, level: int = 50) -> int:
    """
    Find minimum EVs needed to reach target_stat with given nature modifier.

    IMPORTANT: This function now returns the OPTIMIZED EV value, removing any
    wasted EVs that don't contribute to the final stat.

    Formula: target_stat = floor((floor((2*base + IV + EV/4) * level/100) + 5) * nature_mod)
    We need to reverse-engineer EV from target_stat.

    Args:
        base: Base stat value
        iv: IV value (typically 31)
        target_stat: Target final stat value
        nature_mod: Nature modifier (0.9, 1.0, or 1.1)
        level: Pokemon level (default 50)

    Returns:
        Minimum OPTIMIZED EVs needed (0-252), with waste removed
    """
    from vgc_mcp_core.calc.stats import optimize_ev_efficiency

    # Find the first EV breakpoint that reaches the target
    for ev in EV_BREAKPOINTS_LV50:
        calculated_stat = calculate_stat(base, iv, ev, level, nature_mod)
        if calculated_stat >= target_stat:
            # Found the target - now optimize for efficiency
            # This removes any wasted EVs (e.g., 152 → 148 if they give same stat)
            return optimize_ev_efficiency(base, iv, ev, level, nature_mod, "normal")

    # If we can't reach it even with 252 EVs, optimize 252
    return optimize_ev_efficiency(base, iv, 252, level, nature_mod, "normal")


def _find_min_evs_for_hp(base: int, iv: int, target_hp: int, level: int = 50) -> int:
    """
    Find minimum EVs needed to reach target HP.

    IMPORTANT: This function now returns the OPTIMIZED EV value, removing any
    wasted EVs that don't contribute to the final HP stat.
    """
    from vgc_mcp_core.calc.stats import optimize_ev_efficiency

    for ev in EV_BREAKPOINTS_LV50:
        calculated_hp = calculate_hp(base, iv, ev, level)
        if calculated_hp >= target_hp:
            # Found the target - now optimize for efficiency
            return optimize_ev_efficiency(base, iv, ev, level, 1.0, "hp")

    # If we can't reach it even with 252 EVs, optimize 252
    return optimize_ev_efficiency(base, iv, 252, level, 1.0, "hp")


async def _get_common_spread(smogon: Optional[SmogonStatsClient], pokemon_name: str) -> Optional[dict]:
    """Most common Smogon spread for a Pokemon (None without a client or data).

    Handlers call this through the module (``spread_common._get_common_spread``)
    so tests can patch one place.
    """
    return await _shared_get_common_spread(smogon, pokemon_name)


def _get_nature_boost_stat(nature_name: str) -> str:
    """Get the stat that a nature boosts (returns '+Atk', '+Def', etc.)."""
    nature_boosts = {
        "adamant": "+Atk",
        "brave": "+Atk",
        "lonely": "+Atk",
        "naughty": "+Atk",
        "bold": "+Def",
        "impish": "+Def",
        "lax": "+Def",
        "relaxed": "+Def",
        "modest": "+SpA",
        "mild": "+SpA",
        "quiet": "+SpA",
        "rash": "+SpA",
        "calm": "+SpD",
        "careful": "+SpD",
        "gentle": "+SpD",
        "sassy": "+SpD",
        "jolly": "+Spe",
        "hasty": "+Spe",
        "naive": "+Spe",
        "timid": "+Spe",
        "serious": "neutral",
        "bashful": "neutral",
        "docile": "neutral",
        "hardy": "neutral",
        "quirky": "neutral"
    }
    return nature_boosts.get(nature_name.lower(), "neutral")


def _generate_nature_explanation(optimal: dict, alternative: dict) -> str:
    """Generate explanation comparing alternative nature to optimal."""
    opt_nature = optimal["nature"]
    alt_nature = alternative["nature"]

    opt_boost = _get_nature_boost_stat(opt_nature)
    alt_boost = _get_nature_boost_stat(alt_nature)

    ev_diff = alternative["total_evs"] - optimal["total_evs"]
    speed_diff = alternative["speed_evs"] - optimal["speed_evs"]

    # Build explanation based on stat differences
    if speed_diff > 0:
        return f"{alt_nature.title()}'s {alt_boost} nature requires {speed_diff} more Speed EVs to hit the same speed tier. Uses {ev_diff} more EVs total than {opt_nature.title()} ({opt_boost})."
    elif speed_diff < 0:
        # Less speed EVs needed, but more total EVs (must be compensating with bulk)
        bulk_diff = ev_diff - speed_diff  # Additional EVs beyond the speed savings
        return f"{alt_nature.title()}'s {alt_boost} nature saves {abs(speed_diff)} Speed EVs but requires {bulk_diff} more EVs in bulk stats. Uses {ev_diff} more EVs total than {opt_nature.title()} ({opt_boost})."
    else:
        # Same speed EVs, different bulk distribution
        return f"{alt_nature.title()}'s {alt_boost} nature hits the same speed tier but distributes bulk EVs differently. Uses {ev_diff} more EVs total than {opt_nature.title()} ({opt_boost})."


@dataclass
class ThreatSpec:
    """Specification for a single threat in multi-survival optimization."""
    attacker_name: str
    attacker_build: PokemonBuild
    move: Move
    is_physical: bool
    modifiers: DamageModifiers
    # Original user inputs for display
    nature: str
    evs: int
    item: Optional[str]
    ability: Optional[str]
    tera_type: Optional[str]


class DamageCache:
    """Cache damage calculations to avoid redundant computations."""

    def __init__(
        self,
        threats: list[ThreatSpec],
        defender_name: str,
        defender_base: BaseStats,
        defender_types: list[str],
        defender_ability: Optional[str] = None,
        defender_item: Optional[str] = None,
    ):
        self.threats = threats
        self.defender_name = defender_name
        self.defender_base = defender_base
        self.defender_types = defender_types
        self.defender_ability = defender_ability
        self.defender_item = defender_item
        self.cache: dict = {}  # Key: (threat_idx, hp_ev, def_ev, spd_ev, nature_name, tera_type)

    def get_damage(
        self,
        threat_idx: int,
        hp_ev: int,
        def_ev: int,
        spd_ev: int,
        nature: Nature,
        defender_tera_type: Optional[str] = None
    ) -> DamageResult:
        """Get cached damage result or calculate and cache it."""
        tera_key = defender_tera_type or "none"
        key = (threat_idx, hp_ev, def_ev, spd_ev, nature.value, tera_key)

        if key not in self.cache:
            # Build defender with these EVs — stamp the defender's ability so the
            # damage engine auto-applies every defensive ability interaction
            # (Multiscale, Ice Scales, Thick Fat, Fluffy, Filter, Levitate, type
            # absorption, Heatproof, etc.).
            defender = build_pokemon(
                name=self.defender_name,
                base_stats=self.defender_base,
                types=self.defender_types,
                nature=nature,
                spread=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                ability=self.defender_ability,
                item=self.defender_item,
                tera_type=defender_tera_type,
            )

            threat = self.threats[threat_idx]

            # Compute Intimidate stage event from defender's ability vs this
            # threat's ability/move (only triggers for physical moves).
            from vgc_mcp_core.tools.ability_helpers import compute_intimidate_attack_stage
            intim_stage, _ = compute_intimidate_attack_stage(
                defender_ability=self.defender_ability,
                attacker_ability=threat.modifiers.attacker_ability,
                is_physical=threat.is_physical,
            )

            # Update modifiers with defender Tera if specified
            modifiers = DamageModifiers.from_scenario(
                is_doubles=threat.modifiers.is_doubles,
                attacker_item=threat.modifiers.attacker_item,
                attacker_ability=threat.modifiers.attacker_ability,
                defender_ability=self.defender_ability,
                tera_type=threat.modifiers.tera_type,
                tera_active=threat.modifiers.tera_active,
                defender_tera_type=defender_tera_type,
                is_critical=threat.modifiers.is_critical,
                sword_of_ruin=threat.modifiers.sword_of_ruin,
                beads_of_ruin=threat.modifiers.beads_of_ruin,
                vessel_of_ruin=threat.modifiers.vessel_of_ruin,
                tablets_of_ruin=threat.modifiers.tablets_of_ruin,
                intimidate_stage=intim_stage,
                is_physical=threat.is_physical,
            )

            # Calculate damage
            result = calculate_damage(threat.attacker_build, defender, threat.move, modifiers)
            self.cache[key] = result

        return self.cache[key]

    def test_spread_all_threats(
        self,
        hp_ev: int,
        def_ev: int,
        spd_ev: int,
        nature: Nature,
        target_survival: float,
        defender_tera_type: Optional[str] = None
    ) -> tuple[bool, list[tuple[bool, DamageResult]]]:
        """Test if spread survives ALL threats at the target survival rate.

        Returns:
            (all_survive: bool, results: list[(survives, DamageResult)])
        """
        results = []

        for i in range(len(self.threats)):
            result = self.get_damage(i, hp_ev, def_ev, spd_ev, nature, defender_tera_type)

            # Calculate survival percentage (count rolls that don't KO)
            survival_pct = result.survival_percent

            survives = survival_pct >= target_survival
            results.append((survives, result))

        all_survive = all(r[0] for r in results)
        return all_survive, results

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "total_cached": len(self.cache),
            "cache_hits": sum(1 for _ in self.cache.values())  # Placeholder - would need tracking
        }


async def _prepare_threats(
    threats: list[dict],
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient] = None,
) -> list[ThreatSpec]:
    """Prepare and validate threat specifications.

    Args:
        threats: List of threat dicts with attacker, move, and optional nature/evs/item/ability/tera
        pokeapi: PokeAPI client for fetching data

    Returns:
        List of prepared ThreatSpec objects with auto-fetched data
    """
    prepared = []

    for threat_dict in threats:
        attacker_name = threat_dict["attacker"]
        move_name = threat_dict["move"]

        # Fetch attacker data
        atk_base = await pokeapi.get_base_stats(attacker_name)
        atk_types = await pokeapi.get_pokemon_types(attacker_name)
        move = await pokeapi.get_move(move_name, user_name=attacker_name)

        is_physical = move.category == MoveCategory.PHYSICAL

        # Auto-fetch Smogon spread if not specified
        smogon_data = await _get_common_spread(smogon, attacker_name)

        nature_str = threat_dict.get("nature")
        if nature_str is None and smogon_data:
            nature_str = smogon_data.get("nature", "adamant" if is_physical else "modest")
        elif nature_str is None:
            nature_str = "adamant" if is_physical else "modest"

        nature = Nature(nature_str.lower())

        evs = threat_dict.get("evs")
        if evs is None and smogon_data:
            evs_dict = smogon_data.get("evs", {})
            evs = evs_dict.get("attack" if is_physical else "special_attack", 252)
        elif evs is None:
            evs = 252

        item = threat_dict.get("item")
        if item is None and smogon_data:
            item = smogon_data.get("item")
        if item is None:
            # Fallback to meta synergies
            atk_key = attacker_name.lower().replace(" ", "-")
            if atk_key in META_SYNERGIES:
                item, _ = META_SYNERGIES[atk_key]

        ability = threat_dict.get("ability")
        if ability is None and smogon_data:
            ability = smogon_data.get("ability")
        if ability is None:
            # Fallback to meta synergies
            atk_key = attacker_name.lower().replace(" ", "-")
            if atk_key in META_SYNERGIES:
                _, ability = META_SYNERGIES[atk_key]

        # Auto-detect Ruinous abilities
        atk_key = attacker_name.lower().replace(" ", "-")
        sword_of_ruin = False
        beads_of_ruin = False
        vessel_of_ruin = False
        tablets_of_ruin = False

        if atk_key == "chien-pao":
            sword_of_ruin = True
            if not ability:
                ability = "sword-of-ruin"
        elif atk_key == "chi-yu":
            beads_of_ruin = True
            if not ability:
                ability = "beads-of-ruin"
        elif atk_key == "ting-lu":
            vessel_of_ruin = True
            if not ability:
                ability = "vessel-of-ruin"
        elif atk_key == "wo-chien":
            tablets_of_ruin = True
            if not ability:
                ability = "tablets-of-ruin"
        elif ability:
            ability_lower = ability.lower().replace(" ", "-").replace("_", "-")
            if ability_lower == "sword-of-ruin":
                sword_of_ruin = True
            elif ability_lower == "beads-of-ruin":
                beads_of_ruin = True
            elif ability_lower == "vessel-of-ruin":
                vessel_of_ruin = True
            elif ability_lower == "tablets-of-ruin":
                tablets_of_ruin = True

        # Auto-detect Unseen Fist for Urshifu
        if atk_key in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
            if not ability:
                ability = "unseen-fist"

        tera_type = threat_dict.get("tera_type")

        # Auto-assign fixed Tera types (Ogerpon forms, Terapagos)
        from vgc_mcp_core.calc.items import get_fixed_tera_type
        if tera_type is not None:
            fixed_tera = get_fixed_tera_type(attacker_name)
            if fixed_tera and tera_type.lower() != fixed_tera.lower():
                tera_type = fixed_tera

        # Create attacker build
        attacker_build = build_pokemon(
            name=attacker_name,
            base_stats=atk_base,
            types=atk_types,
            nature=nature,
            spread=EVSpread(
                attack=evs if is_physical else 0,
                special_attack=0 if is_physical else evs
            ),
            item=item,
            ability=ability,
            tera_type=tera_type,
        )

        # Create damage modifiers
        modifiers = DamageModifiers.from_scenario(
            attacker_item=item,
            attacker_ability=ability,
            tera_type=tera_type,
            is_critical=move.always_crit,
            sword_of_ruin=sword_of_ruin,
            beads_of_ruin=beads_of_ruin,
            vessel_of_ruin=vessel_of_ruin,
            tablets_of_ruin=tablets_of_ruin,
        )

        prepared.append(ThreatSpec(
            attacker_name=attacker_name,
            attacker_build=attacker_build,
            move=move,
            is_physical=is_physical,
            modifiers=modifiers,
            nature=nature_str,
            evs=evs,
            item=item,
            ability=ability,
            tera_type=tera_type
        ))

    return prepared


def _find_min_bulk_for_threat(
    cache: DamageCache,
    threat_idx: int,
    hp_ev: int,
    nature: Nature,
    target_survival: float,
    stat_type: str,  # "defense" or "special_defense"
    defender_tera_type: Optional[str] = None
) -> int:
    """Binary search for minimum Def or SpD EVs to survive a threat at given HP.

    Args:
        cache: Damage cache
        threat_idx: Index of threat in cache.threats
        hp_ev: HP EVs to test at
        nature: Nature being tested
        target_survival: Minimum survival percentage required
        stat_type: "defense" or "special_defense"
        defender_tera_type: Defender's Tera type if active

    Returns:
        Minimum EVs needed, or -1 if impossible even at 252
    """
    for test_ev in EV_BREAKPOINTS_LV50:
        def_ev = test_ev if stat_type == "defense" else 0
        spd_ev = test_ev if stat_type == "special_defense" else 0

        result = cache.get_damage(threat_idx, hp_ev, def_ev, spd_ev, nature, defender_tera_type)

        # Calculate survival percentage
        survival_pct = result.survival_percent

        if survival_pct >= target_survival:
            return test_ev

    return -1  # Impossible even at 252 EVs


def _quick_feasibility_check(
    cache: DamageCache,
    remaining_evs: int,
    nature: Nature,
    target_survival: float,
    defender_tera_type: Optional[str] = None
) -> Optional[dict]:
    """Quick feasibility check by sampling 5 HP values.

    Args:
        cache: Damage cache with all threats
        remaining_evs: EVs available for bulk (after speed)
        nature: Nature to test
        target_survival: Minimum survival percentage
        defender_tera_type: Defender's Tera type if active

    Returns:
        Feasible spread dict if found, else None
    """
    hp_samples = [0, 60, 120, 180, 252]

    # Categorize threats
    physical_threats = [i for i, t in enumerate(cache.threats) if t.is_physical]
    special_threats = [i for i, t in enumerate(cache.threats) if not t.is_physical]

    for hp_ev in hp_samples:
        if hp_ev > remaining_evs:
            continue

        # Find maximum Defense needed across all physical threats
        max_def_needed = 0
        if physical_threats:
            for threat_idx in physical_threats:
                min_def = _find_min_bulk_for_threat(
                    cache, threat_idx, hp_ev, nature, target_survival, "defense", defender_tera_type
                )
                if min_def < 0:
                    max_def_needed = 999  # Impossible
                    break
                max_def_needed = max(max_def_needed, min_def)

        # Find maximum SpD needed across all special threats
        max_spd_needed = 0
        if special_threats:
            for threat_idx in special_threats:
                min_spd = _find_min_bulk_for_threat(
                    cache, threat_idx, hp_ev, nature, target_survival, "special_defense", defender_tera_type
                )
                if min_spd < 0:
                    max_spd_needed = 999  # Impossible
                    break
                max_spd_needed = max(max_spd_needed, min_spd)

        # Check if this HP value works
        if hp_ev + max_def_needed + max_spd_needed <= remaining_evs:
            return {
                "hp": hp_ev,
                "def": max_def_needed,
                "spd": max_spd_needed
            }

    return None  # No feasible spread found


SPEED_STAGE_MULTIPLIERS = {
    -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
    0: 1,
    1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2
}


NATURE_CANDIDATES_PHYSICAL = [
    # Bulk-boosting natures FIRST (prefer -SpA over -Atk for physical attackers)
    ("impish", {"speed": 1.0, "attack": 1.0, "defense": 1.1, "special_attack": 0.9, "special_defense": 1.0}),
    ("careful", {"speed": 1.0, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.1}),
    ("bold", {"speed": 1.0, "attack": 0.9, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
    ("calm", {"speed": 1.0, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
    # Offensive natures (can save EVs for speed benchmarks)
    ("adamant", {"speed": 1.0, "attack": 1.1, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.0}),
    # +Speed natures - Jolly first (doesn't hurt Atk)
    ("jolly", {"speed": 1.1, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.0}),
    ("timid", {"speed": 1.1, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.0}),
    # -Speed natures
    ("brave", {"speed": 0.9, "attack": 1.1, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.0}),
    ("relaxed", {"speed": 0.9, "attack": 1.0, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
    ("sassy", {"speed": 0.9, "attack": 1.0, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
]


NATURE_CANDIDATES_SPECIAL = [
    # Bulk-boosting natures FIRST (prefer -Atk over -SpA for special attackers)
    ("bold", {"speed": 1.0, "attack": 0.9, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
    ("calm", {"speed": 1.0, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
    ("impish", {"speed": 1.0, "attack": 1.0, "defense": 1.1, "special_attack": 0.9, "special_defense": 1.0}),
    ("careful", {"speed": 1.0, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.1}),
    # Offensive natures (can save EVs for speed benchmarks)
    ("modest", {"speed": 1.0, "attack": 0.9, "defense": 1.0, "special_attack": 1.1, "special_defense": 1.0}),
    # +Speed natures - Timid first (doesn't hurt SpA)
    ("timid", {"speed": 1.1, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.0}),
    ("jolly", {"speed": 1.1, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.0}),
    # -Speed natures
    ("quiet", {"speed": 0.9, "attack": 1.0, "defense": 1.0, "special_attack": 1.1, "special_defense": 1.0}),
    ("relaxed", {"speed": 0.9, "attack": 1.0, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
    ("sassy", {"speed": 0.9, "attack": 1.0, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
]
