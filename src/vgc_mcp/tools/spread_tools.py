"""MCP tools for EV spread optimization."""

from typing import Optional
from mcp.server.fastmcp import FastMCP
from dataclasses import dataclass
import itertools
import time

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.stats import calculate_speed, calculate_stat, calculate_hp, find_speed_evs
from vgc_mcp_core.calc.damage import calculate_damage, DamageResult, format_percent
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.bulk_optimization import (
    calculate_optimal_bulk_distribution,
    analyze_diminishing_returns
)
from vgc_mcp_core.models.pokemon import Nature, get_nature_modifier, PokemonBuild, BaseStats, EVSpread
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50, normalize_evs
from vgc_mcp_core.utils.synergies import get_synergy_ability
import math


# Module-level Smogon client reference (set during registration)
_smogon_client: Optional[SmogonStatsClient] = None


# Known meta synergies: Pokemon -> (item, ability) defaults
# Used as fallback when Smogon data is unavailable
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


async def _get_common_spread(pokemon_name: str) -> Optional[dict]:
    """Fetch the most common spread for a Pokemon from Smogon usage stats.

    Returns:
        dict with 'nature', 'evs', 'item', 'ability' keys, or None if not found
    """
    if _smogon_client is None:
        return None
    try:
        usage = await _smogon_client.get_pokemon_usage(pokemon_name)
        if usage and usage.get("spreads"):
            top_spread = usage["spreads"][0]
            items = usage.get("items", {})
            abilities = usage.get("abilities", {})
            top_item = list(items.keys())[0] if items else None

            # Get ability based on item synergy (e.g., Life Orb -> Sheer Force)
            top_ability, _ = get_synergy_ability(top_item, abilities)

            return {
                "nature": top_spread.get("nature", "Serious"),
                "evs": top_spread.get("evs", {}),
                "usage": top_spread.get("usage", 0),
                "item": top_item,
                "ability": top_ability,
            }
    except Exception as e:
        logger.warning(f"Failed to fetch Smogon spread for {pokemon_name}: {e}")
    return None


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


# Multi-threat optimization helper classes

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

    def __init__(self, threats: list[ThreatSpec], defender_name: str, defender_base: BaseStats, defender_types: list[str]):
        self.threats = threats
        self.defender_name = defender_name
        self.defender_base = defender_base
        self.defender_types = defender_types
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
            # Build defender with these EVs
            defender = PokemonBuild(
                name=self.defender_name,
                base_stats=self.defender_base,
                types=self.defender_types,
                nature=nature,
                evs=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                tera_type=defender_tera_type
            )

            threat = self.threats[threat_idx]

            # Update modifiers with defender Tera if specified
            modifiers = DamageModifiers(
                is_doubles=threat.modifiers.is_doubles,
                attacker_item=threat.modifiers.attacker_item,
                attacker_ability=threat.modifiers.attacker_ability,
                tera_type=threat.modifiers.tera_type,
                tera_active=threat.modifiers.tera_active,
                defender_tera_type=defender_tera_type,
                defender_tera_active=defender_tera_type is not None,
                is_critical=threat.modifiers.is_critical,
                sword_of_ruin=threat.modifiers.sword_of_ruin,
                beads_of_ruin=threat.modifiers.beads_of_ruin,
                vessel_of_ruin=threat.modifiers.vessel_of_ruin,
                tablets_of_ruin=threat.modifiers.tablets_of_ruin
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
            survive_rolls = sum(1 for roll in result.rolls if roll < result.defender_hp)
            survival_pct = (survive_rolls / 16) * 100

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
    pokeapi: PokeAPIClient
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
        smogon_data = await _get_common_spread(attacker_name)

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
        attacker_build = PokemonBuild(
            name=attacker_name,
            base_stats=atk_base,
            types=atk_types,
            nature=nature,
            evs=EVSpread(
                attack=evs if is_physical else 0,
                special_attack=0 if is_physical else evs
            ),
            item=item,
            ability=ability,
            tera_type=tera_type
        )

        # Create damage modifiers
        modifiers = DamageModifiers(
            is_doubles=True,
            attacker_item=item,
            attacker_ability=ability,
            tera_type=tera_type,
            tera_active=tera_type is not None,
            is_critical=move.always_crit,
            sword_of_ruin=sword_of_ruin,
            beads_of_ruin=beads_of_ruin,
            vessel_of_ruin=vessel_of_ruin,
            tablets_of_ruin=tablets_of_ruin
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
        survive_rolls = sum(1 for roll in result.rolls if roll < result.defender_hp)
        survival_pct = (survive_rolls / 16) * 100

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


def register_spread_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register EV spread optimization tools with the MCP server."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool()
    async def check_spread_efficiency(
        pokemon_name: str,
        nature: str,
        hp_evs: int = 0,
        atk_evs: int = 0,
        def_evs: int = 0,
        spa_evs: int = 0,
        spd_evs: int = 0,
        spe_evs: int = 0
    ) -> dict:
        """
        Check an EV spread for efficiency (wasted EVs, optimal distribution).

        Args:
            pokemon_name: Pokemon name
            nature: Pokemon's nature
            hp_evs through spe_evs: Current EV spread

        Returns:
            Analysis of spread efficiency with suggestions
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            total = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs
            issues = []
            suggestions = []

            # Check total EVs
            if total > 508:
                issues.append(f"Total EVs ({total}) exceed maximum of 508")
            elif total < 508:
                suggestions.append(f"You have {508 - total} EVs remaining to allocate")

            # Check for non-multiples of 4 (wasted EVs)
            evs = {
                "HP": hp_evs, "Attack": atk_evs, "Defense": def_evs,
                "Sp.Atk": spa_evs, "Sp.Def": spd_evs, "Speed": spe_evs
            }

            for stat_name, ev in evs.items():
                if ev % 4 != 0 and ev != 0:
                    wasted = ev % 4
                    issues.append(f"{stat_name}: {wasted} wasted EVs (not multiple of 4)")

            # Check for conflicting nature/EV investment
            nature_mods = {
                "attack": get_nature_modifier(parsed_nature, "attack"),
                "special_attack": get_nature_modifier(parsed_nature, "special_attack"),
                "speed": get_nature_modifier(parsed_nature, "speed"),
            }

            if nature_mods["attack"] < 1.0 and atk_evs > 0:
                suggestions.append(f"Investing in Attack with -{nature} nature. Consider a neutral or +Atk nature.")

            if nature_mods["special_attack"] < 1.0 and spa_evs > 0:
                suggestions.append(f"Investing in Sp.Atk with -{nature} nature. Consider a neutral or +SpA nature.")

            # Calculate final stats
            final_stats = {
                "hp": calculate_hp(base_stats.hp, 31, hp_evs, 50),
                "attack": calculate_stat(base_stats.attack, 31, atk_evs, 50, nature_mods.get("attack", 1.0)),
                "defense": calculate_stat(base_stats.defense, 31, def_evs, 50, get_nature_modifier(parsed_nature, "defense")),
                "special_attack": calculate_stat(base_stats.special_attack, 31, spa_evs, 50, nature_mods.get("special_attack", 1.0)),
                "special_defense": calculate_stat(base_stats.special_defense, 31, spd_evs, 50, get_nature_modifier(parsed_nature, "special_defense")),
                "speed": calculate_stat(base_stats.speed, 31, spe_evs, 50, nature_mods.get("speed", 1.0)),
            }

            # Build summary table
            efficiency = "Valid" if total <= 508 and not any("wasted" in i for i in issues) else "Issues found"
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Pokemon          | {pokemon_name}                             |",
                f"| Nature           | {nature}                                   |",
                f"| Total EVs        | {total}/508                                |",
                f"| EVs Remaining    | {max(0, 508 - total)}                      |",
                f"| Efficiency       | {efficiency}                               |",
            ]
            if issues and issues != ["No issues found"]:
                table_lines.append(f"| Issues           | {len(issues)} found                        |")

            # Build analysis prose
            issue_count = len([i for i in issues if "wasted" in i.lower() or "exceed" in i.lower()])
            if issue_count > 0:
                analysis_str = f"{pokemon_name}'s spread uses {total}/508 EVs — {issue_count} issue(s) found"
            else:
                analysis_str = f"{pokemon_name}'s spread uses {total}/508 EVs — {max(0, 508 - total)} remaining"

            # Generate Showdown paste for the analyzed spread
            types = await pokeapi.get_pokemon_types(pokemon_name)
            analyzed_pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=base_stats,
                types=types,
                nature=parsed_nature,
                evs=EVSpread(
                    hp=hp_evs,
                    attack=atk_evs,
                    defense=def_evs,
                    special_attack=spa_evs,
                    special_defense=spd_evs,
                    speed=spe_evs
                )
            )
            showdown_paste = pokemon_build_to_showdown(analyzed_pokemon)

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "total_evs": total,
                "remaining_evs": max(0, 508 - total),
                "final_stats": final_stats,
                "issues": issues if issues else ["No issues found"],
                "suggestions": suggestions if suggestions else ["Spread looks efficient!"],
                "is_valid": total <= 508 and not any("wasted" in i for i in issues),
                "showdown_paste": showdown_paste,
                "summary_table": "\n".join(table_lines),
                "analysis": analysis_str
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def suggest_nature_optimization(
        pokemon_name: str,
        current_nature: str,
        hp_evs: int,
        atk_evs: int,
        def_evs: int,
        spa_evs: int,
        spd_evs: int,
        spe_evs: int,
        moves: Optional[list[str]] = None
    ) -> dict:
        """
        Suggest a nature change that achieves same stats with fewer EVs.
        Like Showdown's "Use a different nature to save X EVs" feature.
        
        Args:
            pokemon_name: Pokemon name
            current_nature: Current nature (e.g., "serious", "timid")
            hp_evs through spe_evs: Current EV spread
            moves: Optional list of moves to determine physical/special preference
            
        Returns:
            Nature optimization suggestion with EV savings
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            
            # Parse current nature
            try:
                current_nature_enum = Nature(current_nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {current_nature}"}
            
            # Calculate current final stats
            current_stats = {
                "hp": calculate_hp(base_stats.hp, 31, hp_evs, 50),
                "attack": calculate_stat(base_stats.attack, 31, atk_evs, 50, get_nature_modifier(current_nature_enum, "attack")),
                "defense": calculate_stat(base_stats.defense, 31, def_evs, 50, get_nature_modifier(current_nature_enum, "defense")),
                "special_attack": calculate_stat(base_stats.special_attack, 31, spa_evs, 50, get_nature_modifier(current_nature_enum, "special_attack")),
                "special_defense": calculate_stat(base_stats.special_defense, 31, spd_evs, 50, get_nature_modifier(current_nature_enum, "special_defense")),
                "speed": calculate_stat(base_stats.speed, 31, spe_evs, 50, get_nature_modifier(current_nature_enum, "speed"))
            }
            
            current_total_evs = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs
            
            # Determine if Pokemon is physical or special attacker
            is_physical = False
            is_special = False
            if moves:
                for move_name in moves:
                    try:
                        move = await pokeapi.get_move(move_name)
                        if move.category == MoveCategory.PHYSICAL:
                            is_physical = True
                        elif move.category == MoveCategory.SPECIAL:
                            is_special = True
                    except Exception:
                        continue
            
            # Try all natures and find the one that uses fewest EVs
            best_nature = None
            best_evs = None
            best_total_evs = current_total_evs
            best_stats = None
            
            for nature in Nature:
                # Skip current nature
                if nature == current_nature_enum:
                    continue
                
                # Don't suggest -Atk for physical attackers
                if is_physical and get_nature_modifier(nature, "attack") < 1.0:
                    continue
                
                # Don't suggest -SpA for special attackers
                if is_special and get_nature_modifier(nature, "special_attack") < 1.0:
                    continue
                
                # Calculate minimum EVs needed to reach same stats
                new_hp_evs = _find_min_evs_for_hp(base_stats.hp, 31, current_stats["hp"], 50)
                new_atk_evs = _find_min_evs_for_stat(base_stats.attack, 31, current_stats["attack"], get_nature_modifier(nature, "attack"), 50)
                new_def_evs = _find_min_evs_for_stat(base_stats.defense, 31, current_stats["defense"], get_nature_modifier(nature, "defense"), 50)
                new_spa_evs = _find_min_evs_for_stat(base_stats.special_attack, 31, current_stats["special_attack"], get_nature_modifier(nature, "special_attack"), 50)
                new_spd_evs = _find_min_evs_for_stat(base_stats.special_defense, 31, current_stats["special_defense"], get_nature_modifier(nature, "special_defense"), 50)
                new_spe_evs = _find_min_evs_for_stat(base_stats.speed, 31, current_stats["speed"], get_nature_modifier(nature, "speed"), 50)
                
                new_total_evs = new_hp_evs + new_atk_evs + new_def_evs + new_spa_evs + new_spd_evs + new_spe_evs
                
                # Verify stats match (should be same or better)
                new_stats = {
                    "hp": calculate_hp(base_stats.hp, 31, new_hp_evs, 50),
                    "attack": calculate_stat(base_stats.attack, 31, new_atk_evs, 50, get_nature_modifier(nature, "attack")),
                    "defense": calculate_stat(base_stats.defense, 31, new_def_evs, 50, get_nature_modifier(nature, "defense")),
                    "special_attack": calculate_stat(base_stats.special_attack, 31, new_spa_evs, 50, get_nature_modifier(nature, "special_attack")),
                    "special_defense": calculate_stat(base_stats.special_defense, 31, new_spd_evs, 50, get_nature_modifier(nature, "special_defense")),
                    "speed": calculate_stat(base_stats.speed, 31, new_spe_evs, 50, get_nature_modifier(nature, "speed"))
                }
                
                # Check if stats are same or better in important stats
                # For physical attackers, Attack and Speed must be same or better
                # For special attackers, SpA and Speed must be same or better
                # HP and defenses should generally be same or better
                stats_match = True
                
                # HP should be same or better
                if new_stats["hp"] < current_stats["hp"]:
                    stats_match = False
                
                # Attack must be same or better for physical attackers
                if is_physical and new_stats["attack"] < current_stats["attack"]:
                    stats_match = False
                
                # Special Attack must be same or better for special attackers
                if is_special and new_stats["special_attack"] < current_stats["special_attack"]:
                    stats_match = False
                
                # Speed should generally be same or better (unless Trick Room)
                if new_stats["speed"] < current_stats["speed"]:
                    stats_match = False
                
                # Defenses can be slightly worse if it saves significant EVs
                # But only if the loss is minimal (1-2 points)
                if new_stats["defense"] < current_stats["defense"] - 2:
                    stats_match = False
                if new_stats["special_defense"] < current_stats["special_defense"] - 2:
                    stats_match = False
                
                if stats_match and new_total_evs < best_total_evs:
                    best_nature = nature
                    best_evs = {
                        "hp": new_hp_evs,
                        "attack": new_atk_evs,
                        "defense": new_def_evs,
                        "special_attack": new_spa_evs,
                        "special_defense": new_spd_evs,
                        "speed": new_spe_evs
                    }
                    best_total_evs = new_total_evs
                    best_stats = new_stats
            
            # If no better nature found
            if best_nature is None:
                return {
                    "pokemon": pokemon_name,
                    "current_nature": current_nature,
                    "optimization_found": False,
                    "message": "Your nature is already optimal! No EV savings possible.",
                    "markdown_summary": f"## Nature Optimization: {pokemon_name.title()}\n\n### Result\nYour current nature ({current_nature.title()}) is already optimal. No EV savings possible with a different nature."
                }
            
            ev_savings = current_total_evs - best_total_evs
            
            # Build markdown output
            markdown_lines = [
                f"## Nature Optimization: {pokemon_name.title()}",
                "",
                "### Current Build",
                "| Nature | HP | Atk | Def | SpA | SpD | Spe | Total EVs |",
                "|--------|-----|-----|-----|-----|-----|-----|-----------|",
                f"| {current_nature.title()} | {hp_evs} | {atk_evs} | {def_evs} | {spa_evs} | {spd_evs} | {spe_evs} | **{current_total_evs}** |",
                "",
                "### Final Stats (Current)",
                "| HP | Atk | Def | SpA | SpD | Spe |",
                "|----|-----|-----|-----|-----|-----|",
                f"| {current_stats['hp']} | {current_stats['attack']} | {current_stats['defense']} | "
                f"{current_stats['special_attack']} | {current_stats['special_defense']} | {current_stats['speed']} |",
                "",
                "---",
                "",
                "### Suggested Optimization",
                "",
                f"**Use {best_nature.value.title().replace('_', ' ')} ({best_nature.value.split('_')[0].title() if '_' in best_nature.value else best_nature.value.title()}, "
                f"-{best_nature.value.split('_')[1].title() if '_' in best_nature.value else 'Atk'}) to save {ev_savings} EVs!**",
                "",
                "| Nature | HP | Atk | Def | SpA | SpD | Spe | Total EVs |",
                "|--------|-----|-----|-----|-----|-----|-----|-----------|",
                f"| {best_nature.value.title().replace('_', ' ')} | {best_evs['hp']} | **{best_evs['attack']}** | {best_evs['defense']} | "
                f"{best_evs['special_attack']} | {best_evs['special_defense']} | **{best_evs['speed']}** | **{best_total_evs}** |",
                "",
                "### Final Stats (Optimized) - SAME OR BETTER",
                "| HP | Atk | Def | SpA | SpD | Spe |",
                "|----|-----|-----|-----|-----|-----|",
                f"| {best_stats['hp']} | **{best_stats['attack']}** | {best_stats['defense']} | "
                f"{best_stats['special_attack']} | {best_stats['special_defense']} | {best_stats['speed']} |",
                "",
                "### What Changed"
            ]
            
            # Show what changed
            if best_stats['attack'] != current_stats['attack']:
                diff = best_stats['attack'] - current_stats['attack']
                markdown_lines.append(f"- Attack: {current_stats['attack']} → {best_stats['attack']} ({'+' if diff > 0 else ''}{diff}) - Nature boost compensates for fewer EVs")
            
            if best_stats['special_attack'] != current_stats['special_attack']:
                diff = best_stats['special_attack'] - current_stats['special_attack']
                spa_reason = "Not used for special moves" if is_physical else "Nature adjustment"
                markdown_lines.append(f"- Sp.Atk: {current_stats['special_attack']} → {best_stats['special_attack']} ({'+' if diff > 0 else ''}{diff}) - {spa_reason}")
            
            if best_stats['speed'] != current_stats['speed']:
                diff = best_stats['speed'] - current_stats['speed']
                markdown_lines.append(f"- Speed: {current_stats['speed']} → {best_stats['speed']} ({'+' if diff > 0 else ''}{diff}) - Nature adjustment")
            
            markdown_lines.extend([
                f"- **{ev_savings} EVs freed up** for other stats!",
                "",
                "### Where to Invest Saved EVs",
                f"With {ev_savings} extra EVs, you could:"
            ])
            
            # Suggest where to invest saved EVs
            if best_stats['hp'] < 400:  # Reasonable HP cap
                hp_gain = calculate_hp(base_stats.hp, 31, best_evs['hp'] + ev_savings, 50) - best_stats['hp']
                markdown_lines.append(f"- Add {ev_savings} to HP ({best_stats['hp']} → {best_stats['hp'] + hp_gain}) for more bulk")
            
            if best_stats['defense'] < 300:
                def_gain = calculate_stat(base_stats.defense, 31, best_evs['defense'] + ev_savings, 50, get_nature_modifier(best_nature, "defense")) - best_stats['defense']
                markdown_lines.append(f"- Add {ev_savings} to Def ({best_stats['defense']} → {best_stats['defense'] + def_gain}) to survive physical hits")
            
            if best_stats['special_defense'] < 300:
                spd_gain = calculate_stat(base_stats.special_defense, 31, best_evs['special_defense'] + ev_savings, 50, get_nature_modifier(best_nature, "special_defense")) - best_stats['special_defense']
                markdown_lines.append(f"- Add {ev_savings} to SpD ({best_stats['special_defense']} → {best_stats['special_defense'] + spd_gain}) to survive special hits")
            
            # Generate Showdown pastes for both current and optimized spreads
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Build current Pokemon
            current_pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=base_stats,
                types=types,
                nature=current_nature_enum,
                evs=EVSpread(
                    hp=hp_evs,
                    attack=atk_evs,
                    defense=def_evs,
                    special_attack=spa_evs,
                    special_defense=spd_evs,
                    speed=spe_evs
                )
            )
            current_showdown = pokemon_build_to_showdown(current_pokemon)

            # Build optimized Pokemon
            optimized_pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=base_stats,
                types=types,
                nature=best_nature,
                evs=EVSpread(
                    hp=best_evs["hp"],
                    attack=best_evs["attack"],
                    defense=best_evs["defense"],
                    special_attack=best_evs["special_attack"],
                    special_defense=best_evs["special_defense"],
                    speed=best_evs["speed"]
                )
            )
            optimized_showdown = pokemon_build_to_showdown(optimized_pokemon)

            response = {
                "pokemon": pokemon_name,
                "current_nature": current_nature,
                "current_evs": {
                    "hp": hp_evs,
                    "attack": atk_evs,
                    "defense": def_evs,
                    "special_attack": spa_evs,
                    "special_defense": spd_evs,
                    "speed": spe_evs
                },
                "current_total_evs": current_total_evs,
                "current_stats": current_stats,
                "current_showdown_paste": current_showdown,
                "suggested_nature": best_nature.value,
                "suggested_evs": best_evs,
                "suggested_total_evs": best_total_evs,
                "suggested_stats": best_stats,
                "optimized_showdown_paste": optimized_showdown,
                "ev_savings": ev_savings,
                "optimization_found": True,
                "markdown_summary": "\n".join(markdown_lines)
            }

            return response
            
        except Exception as e:
            logger.error(f"Error in suggest_nature_optimization: {e}", exc_info=True)
            return {"error": str(e)}

    @mcp.tool()
    async def optimize_bulk(
        pokemon_name: str,
        nature: str,
        total_bulk_evs: int = 252,
        defense_bias: float = 0.5
    ) -> dict:
        """
        Optimize HP/Def/SpD EVs for maximum bulk.

        Args:
            pokemon_name: Pokemon name
            nature: Pokemon's nature
            total_bulk_evs: Total EVs to allocate to bulk (default 252)
            defense_bias: 0.5 = balanced, 1.0 = physical, 0.0 = special

        Returns:
            Optimal HP/Def/SpD distribution
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            # Simple optimization: balance HP with defenses based on bias
            # General rule: invest in HP until it's ~2x each defense stat

            best_spread = None
            best_bulk = 0

            # Try different distributions (level 50 breakpoints: 0, 4, 12, 20, 28...)
            for hp_ev in EV_BREAKPOINTS_LV50:
                if hp_ev > min(252, total_bulk_evs):
                    break
                remaining = total_bulk_evs - hp_ev
                for def_ev in EV_BREAKPOINTS_LV50:
                    if def_ev > min(252, remaining):
                        break
                    spd_ev = normalize_evs(remaining - def_ev)
                    if spd_ev < 0:
                        continue

                    hp = calculate_hp(base_stats.hp, 31, hp_ev, 50)
                    def_stat = calculate_stat(
                        base_stats.defense, 31, def_ev, 50,
                        get_nature_modifier(parsed_nature, "defense")
                    )
                    spd_stat = calculate_stat(
                        base_stats.special_defense, 31, spd_ev, 50,
                        get_nature_modifier(parsed_nature, "special_defense")
                    )

                    # Calculate effective bulk (HP * Def for physical, HP * SpD for special)
                    phys_bulk = hp * def_stat
                    spec_bulk = hp * spd_stat
                    total_bulk = phys_bulk * defense_bias + spec_bulk * (1 - defense_bias)

                    if total_bulk > best_bulk:
                        best_bulk = total_bulk
                        best_spread = {
                            "hp_evs": hp_ev,
                            "def_evs": def_ev,
                            "spd_evs": spd_ev,
                            "final_hp": hp,
                            "final_def": def_stat,
                            "final_spd": spd_stat,
                            "physical_bulk": phys_bulk,
                            "special_bulk": spec_bulk
                        }

            # Build summary table
            if best_spread:
                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Pokemon          | {pokemon_name}                             |",
                    f"| Nature           | {nature}                                   |",
                    f"| HP EVs           | {best_spread['hp_evs']}                    |",
                    f"| Defense EVs      | {best_spread['def_evs']}                   |",
                    f"| SpDef EVs        | {best_spread['spd_evs']}                   |",
                    f"| Final HP         | {best_spread['final_hp']}                  |",
                    f"| Final Def        | {best_spread['final_def']}                 |",
                    f"| Final SpD        | {best_spread['final_spd']}                 |",
                    f"| Physical Bulk    | {best_spread['physical_bulk']}             |",
                    f"| Special Bulk     | {best_spread['special_bulk']}              |",
                ]
            else:
                table_lines = ["| No optimal spread found |"]

            # Build analysis prose
            if best_spread:
                analysis_str = f"Optimal bulk: {best_spread['hp_evs']} HP / {best_spread['def_evs']} Def / {best_spread['spd_evs']} SpD for {pokemon_name}"
            else:
                analysis_str = f"No optimal spread found for {pokemon_name}"

            # Generate Showdown paste if spread found
            showdown_paste = None
            if best_spread:
                types = await pokeapi.get_pokemon_types(pokemon_name)
                optimized_pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=base_stats,
                    types=types,
                    nature=parsed_nature,
                    evs=EVSpread(
                        hp=best_spread["hp_evs"],
                        attack=0,
                        defense=best_spread["def_evs"],
                        special_attack=0,
                        special_defense=best_spread["spd_evs"],
                        speed=0
                    )
                )
                showdown_paste = pokemon_build_to_showdown(optimized_pokemon)

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "total_bulk_evs": total_bulk_evs,
                "defense_bias": defense_bias,
                "optimal_spread": best_spread,
                "showdown_paste": showdown_paste,
                "summary_table": "\n".join(table_lines),
                "analysis": analysis_str
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def suggest_spread(
        pokemon_name: str,
        role: str = "offensive",
        speed_target: Optional[int] = None
    ) -> dict:
        """
        Suggest an EV spread based on role.

        Args:
            pokemon_name: Pokemon name
            role: "offensive" (max offensive stat + speed), "bulky" (HP + defenses),
                  "bulky_offense" (some bulk + offense), "support" (bulk focused)
            speed_target: Optional specific speed stat to hit

        Returns:
            Suggested spread with reasoning
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            # Determine if physical or special attacker
            is_physical = base_stats.attack > base_stats.special_attack
            is_special = base_stats.special_attack > base_stats.attack
            offensive_stat = "Attack" if is_physical else "Sp. Atk"

            # Use intelligent nature selection for offensive role
            nature_name = "Jolly" if is_physical else "Timid"  # Default fallback
            nature_reasoning = None
            
            if role == "offensive":
                from vgc_mcp_core.calc.nature_optimization import find_optimal_nature_for_benchmarks
                
                benchmarks = {
                    "speed_target": speed_target,
                    "prioritize": "offense",
                    "offensive_evs": 252,
                    "speed_evs": 252
                }
                
                nature_result = find_optimal_nature_for_benchmarks(
                    base_stats=base_stats,
                    benchmarks=benchmarks,
                    is_physical=is_physical,
                    is_special=is_special,
                    role="offensive"
                )
                
                if nature_result:
                    nature_name = nature_result.best_nature.value.title()
                    nature_reasoning = nature_result.reasoning

            spreads = {
                "offensive": {
                    "description": f"Max {offensive_stat} and Speed for maximum damage output",
                    "nature": nature_name,
                    "evs": {
                        "hp": 0,
                        "attack": 252 if is_physical else 0,
                        "defense": 0,
                        "special_attack": 0 if is_physical else 252,
                        "special_defense": 4,
                        "speed": 252
                    }
                },
                "bulky": {
                    "description": "Maximum HP with balanced defenses",
                    "nature": "Calm" if base_stats.special_defense > base_stats.defense else "Bold",
                    "evs": {
                        "hp": 252,
                        "attack": 0,
                        "defense": 128,
                        "special_attack": 0,
                        "special_defense": 128,
                        "speed": 0
                    }
                },
                "bulky_offense": {
                    "description": f"Some bulk while maintaining {offensive_stat}",
                    "nature": "Adamant" if is_physical else "Modest",
                    "evs": {
                        "hp": 252,
                        "attack": 252 if is_physical else 0,
                        "defense": 0,
                        "special_attack": 0 if is_physical else 252,
                        "special_defense": 4,
                        "speed": 0
                    }
                },
                "support": {
                    "description": "Maximum bulk for supporting the team",
                    "nature": "Bold",
                    "evs": {
                        "hp": 252,
                        "attack": 0,
                        "defense": 252,
                        "special_attack": 0,
                        "special_defense": 4,
                        "speed": 0
                    }
                }
            }

            if role not in spreads:
                return {"error": f"Unknown role: {role}. Use: offensive, bulky, bulky_offense, support"}

            spread = spreads[role]

            # If speed target specified, adjust
            if speed_target and role == "offensive":
                # Calculate EVs needed
                nature = Nature(spread["nature"].lower())
                needed = find_speed_evs(base_stats.speed, speed_target, nature)

                if needed is not None and needed < 252:
                    leftover = normalize_evs(252 - needed)
                    spread["evs"]["speed"] = normalize_evs(needed)
                    spread["evs"]["hp"] = leftover
                    spread["description"] += f" (Speed creep to {speed_target})"

            # Generate Showdown paste for suggested spread
            types = await pokeapi.get_pokemon_types(pokemon_name)
            nature_enum = Nature(spread["nature"].lower())

            suggested_pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=base_stats,
                types=types,
                nature=nature_enum,
                evs=EVSpread(
                    hp=spread["evs"]["hp"],
                    attack=spread["evs"]["attack"],
                    defense=spread["evs"]["defense"],
                    special_attack=spread["evs"]["special_attack"],
                    special_defense=spread["evs"]["special_defense"],
                    speed=spread["evs"]["speed"]
                )
            )
            showdown_paste = pokemon_build_to_showdown(suggested_pokemon)

            result = {
                "pokemon": pokemon_name,
                "role": role,
                "suggestion": spread,
                "base_stats": {
                    "hp": base_stats.hp,
                    "attack": base_stats.attack,
                    "defense": base_stats.defense,
                    "special_attack": base_stats.special_attack,
                    "special_defense": base_stats.special_defense,
                    "speed": base_stats.speed
                },
                "showdown_paste": showdown_paste
            }
            
            if nature_reasoning:
                result["nature_selection_reasoning"] = nature_reasoning
            
            return result

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def optimize_bulk_math(
        pokemon_name: str,
        nature: str,
        total_bulk_evs: int = 252,
        defense_weight: float = 0.5
    ) -> dict:
        """
        Find mathematically optimal HP/Def/SpD using diminishing returns analysis.

        This uses the principle that Effective Bulk = HP * Defense, and optimal
        distribution is when marginal gains are equal across stats.

        Key insights:
        - High base HP Pokemon should invest more in defenses
        - High base Def/SpD Pokemon should invest more in HP
        - Nature boosts reduce EV investment needed in that stat

        Args:
            pokemon_name: Pokemon name
            nature: Pokemon's nature (e.g., "Bold", "Calm", "Careful")
            total_bulk_evs: Total EVs to distribute (default 252)
            defense_weight: 0.0 = all SpD, 0.5 = balanced, 1.0 = all Def

        Returns:
            Optimal distribution with efficiency comparison vs naive allocation
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            # Use the mathematical optimizer
            result = calculate_optimal_bulk_distribution(
                base_hp=base_stats.hp,
                base_def=base_stats.defense,
                base_spd=base_stats.special_defense,
                nature=nature,
                total_bulk_evs=total_bulk_evs,
                defense_weight=defense_weight
            )

            # Generate Showdown paste
            types = await pokeapi.get_pokemon_types(pokemon_name)
            optimized_pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=base_stats,
                types=types,
                nature=parsed_nature,
                evs=EVSpread(
                    hp=result.hp_evs,
                    attack=0,
                    defense=result.def_evs,
                    special_attack=0,
                    special_defense=result.spd_evs,
                    speed=0
                )
            )
            showdown_paste = pokemon_build_to_showdown(optimized_pokemon)

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "base_stats": {
                    "hp": base_stats.hp,
                    "defense": base_stats.defense,
                    "special_defense": base_stats.special_defense
                },
                "total_bulk_evs": total_bulk_evs,
                "defense_weight": defense_weight,
                "optimal_spread": {
                    "hp_evs": result.hp_evs,
                    "def_evs": result.def_evs,
                    "spd_evs": result.spd_evs
                },
                "final_stats": {
                    "hp": result.final_hp,
                    "defense": result.final_def,
                    "special_defense": result.final_spd
                },
                "bulk_scores": {
                    "physical_bulk": result.physical_bulk,
                    "special_bulk": result.special_bulk,
                    "total_bulk": result.total_bulk
                },
                "efficiency_score": result.efficiency_score,
                "explanation": result.explanation,
                "comparison_vs_naive": result.comparison,
                "showdown_paste": showdown_paste
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_bulk_diminishing_returns(
        pokemon_name: str,
        nature: str
    ) -> dict:
        """
        Analyze diminishing returns for HP, Def, and SpD investment.

        Shows how the value of each additional EV investment decreases
        as you invest more in a stat, helping you understand optimal breakpoints.

        Args:
            pokemon_name: Pokemon name
            nature: Pokemon's nature

        Returns:
            Marginal gain analysis for each stat at different EV thresholds
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            analysis = analyze_diminishing_returns(
                base_hp=base_stats.hp,
                base_def=base_stats.defense,
                base_spd=base_stats.special_defense,
                nature=nature
            )

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "base_stats": {
                    "hp": base_stats.hp,
                    "defense": base_stats.defense,
                    "special_defense": base_stats.special_defense
                },
                "marginal_gains": {
                    "hp": analysis["hp_gains"],
                    "defense": analysis["def_gains"],
                    "special_defense": analysis["spd_gains"]
                },
                "recommendations": analysis["recommendations"],
                "interpretation": (
                    "Higher marginal gain means better EV efficiency at that threshold. "
                    "Invest where marginal gains are highest, then balance."
                )
            }

        except Exception as e:
            return {"error": str(e)}

    # Speed stage multipliers (Gen 9)
    SPEED_STAGE_MULTIPLIERS = {
        -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
        0: 1,
        1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2
    }

    @mcp.tool()
    async def design_spread_with_benchmarks(
        pokemon_name: str,
        nature: Optional[str] = None,
        outspeed_pokemon: Optional[str] = None,
        outspeed_pokemon_nature: str = "jolly",
        outspeed_pokemon_evs: int = 252,
        outspeed_at_speed_stage: int = 0,
        outspeed_target_has_booster: bool = False,
        outspeed_target_has_tailwind: bool = False,
        my_pokemon_has_booster: bool = False,
        my_pokemon_has_tailwind: bool = False,
        survive_pokemon: Optional[str] = None,
        survive_move: Optional[str] = None,
        survive_pokemon_nature: str = "adamant",
        survive_pokemon_evs: int = 252,
        survive_pokemon_ability: Optional[str] = None,
        survive_pokemon_item: Optional[str] = None,
        survive_pokemon_tera_type: Optional[str] = None,
        defender_tera_type: Optional[str] = None,
        prioritize: str = "bulk",
        offensive_evs: int = 0
    ) -> dict:
        """
        Design an EV spread that meets specific speed and SINGLE survival benchmarks.

        Use this when asked questions like:
        - "I need Entei to survive Surging Strikes and outspeed Chien-Pao"
        - "Make my Flutter Mane live Sacred Sword while being faster than Rillaboom"
        - "Build a max Attack Entei that outspeeds Chien-Pao after Icy Wind"

        For surviving TWO DIFFERENT attacks, use optimize_dual_survival_spread instead.

        IMPORTANT - ASK ABOUT TERA BEFORE CALLING:
        Before using this tool for survival calculations, ASK the user:
        1. "Is the attacking Pokemon Terastallized? If so, what type?"
        2. "Is your Pokemon Terastallizing? If so, what type?"

        Tera significantly changes damage calculations:
        - Same-type Tera boosts STAB moves by 33% (1.5x -> 2.0x)
        - Tera changes defensive typing (e.g., Tera Normal removes all weaknesses)

        Do NOT assume no Tera - always clarify with the user first.

        Args:
            pokemon_name: Your Pokemon
            nature: Your Pokemon's nature (optional - auto-selects optimal if not provided)
            outspeed_pokemon: Pokemon to outspeed
            outspeed_pokemon_nature: Target's nature (default: jolly)
            outspeed_pokemon_evs: Target's speed EVs (default: 252)
            outspeed_at_speed_stage: Target's speed stage (-1 = after Icy Wind, -2 = after 2x Icy Wind, etc.)
            outspeed_target_has_booster: True if target has Protosynthesis/Quark Drive speed boost active (1.5x)
            outspeed_target_has_tailwind: True if target has Tailwind active (2x speed)
            my_pokemon_has_booster: True if YOUR Pokemon has Protosynthesis/Quark Drive speed boost (1.5x)
            my_pokemon_has_tailwind: True if YOUR Pokemon has Tailwind active (2x speed)
            survive_pokemon: Attacker to survive
            survive_move: Move to survive
            survive_pokemon_nature: Attacker's nature (default: adamant)
            survive_pokemon_evs: Attacker's offensive EVs (default: 252)
            survive_pokemon_ability: Attacker's ability if relevant
            survive_pokemon_item: Attacker's item (e.g., "choice-band")
            survive_pokemon_tera_type: Attacker's Tera type if Terastallized - ASK USER FIRST!
            defender_tera_type: Your Pokemon's Tera type if Terastallizing - ASK USER FIRST!
            prioritize: "bulk" (max bulk after speed) or "offense" (specified offensive EVs)
            offensive_evs: Attack/SpA EVs if prioritize="offense"

        Returns:
            Complete EV spread with final stats and survival calc
        """
        try:
            # Auto-assign fixed Tera types (Ogerpon forms, Terapagos)
            from vgc_mcp_core.calc.items import get_fixed_tera_type
            if survive_pokemon_tera_type is not None:
                fixed_tera = get_fixed_tera_type(survive_pokemon)
                if fixed_tera and survive_pokemon_tera_type.lower() != fixed_tera.lower():
                    survive_pokemon_tera_type = fixed_tera
            if defender_tera_type is not None:
                fixed_tera = get_fixed_tera_type(pokemon_name)
                if fixed_tera and defender_tera_type.lower() != fixed_tera.lower():
                    defender_tera_type = fixed_tera

            # Fetch our Pokemon's data
            my_base = await pokeapi.get_base_stats(pokemon_name)
            my_types = await pokeapi.get_pokemon_types(pokemon_name)
            
            # Auto-select nature if not provided
            nature_reasoning = None
            if nature is None:
                from vgc_mcp_core.calc.nature_optimization import find_optimal_nature_for_benchmarks
                
                # Determine attack type and role
                is_physical = offensive_evs > 0 and my_base.attack > my_base.special_attack
                is_special = offensive_evs > 0 and my_base.special_attack > my_base.attack
                role = "offensive" if prioritize == "offense" else "bulk"
                
                # Calculate speed target first (needed for benchmarks)
                target_speed = 0
                if outspeed_pokemon:
                    try:
                        target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                        target_nature = Nature(outspeed_pokemon_nature.lower())
                        target_speed_mod = get_nature_modifier(target_nature, "speed")
                        target_speed = calculate_stat(
                            target_base.speed, 31, outspeed_pokemon_evs, 50, target_speed_mod
                        )
                        if outspeed_target_has_booster:
                            target_speed = int(target_speed * 1.5)
                        if outspeed_at_speed_stage != 0:
                            stage_mult = SPEED_STAGE_MULTIPLIERS.get(outspeed_at_speed_stage, 1)
                            target_speed = int(target_speed * stage_mult)
                        if outspeed_target_has_tailwind:
                            target_speed = int(target_speed * 2)
                    except Exception:
                        pass
                
                # Build benchmarks dict
                benchmarks = {
                    "speed_target": target_speed if outspeed_pokemon else None,
                    "prioritize": prioritize,
                    "offensive_evs": offensive_evs if prioritize == "offense" else None,
                }
                
                # Find optimal nature
                nature_result = find_optimal_nature_for_benchmarks(
                    base_stats=my_base,
                    benchmarks=benchmarks,
                    is_physical=is_physical,
                    is_special=is_special,
                    role=role
                )
                
                if nature_result:
                    nature = nature_result.best_nature.value
                    nature_reasoning = nature_result.reasoning
                else:
                    # Fallback to neutral if optimization fails
                    nature = "serious"
                    nature_reasoning = "Could not optimize nature, using neutral nature"
            
            parsed_nature = Nature(nature.lower())

            results = {
                "pokemon": pokemon_name,
                "nature": nature,
                "benchmarks": {}
            }
            
            if nature_reasoning:
                results["nature_selection_reasoning"] = nature_reasoning

            # 1. Calculate speed benchmark
            speed_evs_needed = 0
            target_speed = 0

            if outspeed_pokemon:
                try:
                    target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                    target_nature = Nature(outspeed_pokemon_nature.lower())
                    target_speed_mod = get_nature_modifier(target_nature, "speed")
                    target_speed = calculate_stat(
                        target_base.speed, 31, outspeed_pokemon_evs, 50, target_speed_mod
                    )

                    # Apply Protosynthesis/Quark Drive speed boost if active (1.5x, floored)
                    original_target_speed = target_speed
                    if outspeed_target_has_booster:
                        target_speed = int(target_speed * 1.5)

                    # Apply speed stage modifier (e.g., -1 for after Icy Wind)
                    # Pokemon floors the result: floor(speed * multiplier)
                    pre_stage_speed = target_speed
                    if outspeed_at_speed_stage != 0:
                        stage_mult = SPEED_STAGE_MULTIPLIERS.get(outspeed_at_speed_stage, 1)
                        target_speed = int(target_speed * stage_mult)

                    # Apply Tailwind (2x speed, floored)
                    pre_tailwind_speed = target_speed
                    if outspeed_target_has_tailwind:
                        target_speed = int(target_speed * 2)

                    # Find minimum EVs to outspeed (level 50 breakpoints)
                    # Apply MY Pokemon's booster/tailwind modifiers when comparing
                    my_speed_mod = get_nature_modifier(parsed_nature, "speed")
                    for ev in EV_BREAKPOINTS_LV50:
                        my_speed = calculate_stat(my_base.speed, 31, ev, 50, my_speed_mod)
                        my_effective_speed = my_speed
                        # Apply MY Booster Energy (Protosynthesis/Quark Drive) - 1.5x, floored
                        if my_pokemon_has_booster:
                            my_effective_speed = int(my_effective_speed * 1.5)
                        # Apply MY Tailwind - 2x, floored
                        if my_pokemon_has_tailwind:
                            my_effective_speed = int(my_effective_speed * 2)
                        if my_effective_speed > target_speed:
                            speed_evs_needed = ev
                            break
                    else:
                        speed_evs_needed = 252  # Max out if can't outspeed

                    # Calculate final speeds for display
                    my_base_speed = calculate_stat(my_base.speed, 31, speed_evs_needed, 50, my_speed_mod)
                    my_final_speed = my_base_speed
                    if my_pokemon_has_booster:
                        my_final_speed = int(my_final_speed * 1.5)
                    if my_pokemon_has_tailwind:
                        my_final_speed = int(my_final_speed * 2)

                    speed_benchmark = {
                        "target": outspeed_pokemon,
                        "target_speed": target_speed,
                        "evs_needed": speed_evs_needed,
                        "my_speed": my_base_speed,
                        "my_effective_speed": my_final_speed,
                        "outspeeds": my_final_speed > target_speed
                    }
                    # Add booster, speed stage, and tailwind info if applicable
                    if outspeed_target_has_booster:
                        speed_benchmark["target_base_speed"] = original_target_speed
                        speed_benchmark["target_boosted_speed"] = pre_stage_speed
                        speed_benchmark["booster_note"] = f"Protosynthesis/Quark Drive: {original_target_speed} -> {pre_stage_speed}"
                    if outspeed_at_speed_stage != 0:
                        if not outspeed_target_has_booster:
                            speed_benchmark["target_base_speed"] = original_target_speed
                        speed_benchmark["target_speed_stage"] = outspeed_at_speed_stage
                        stage_name = "after Icy Wind" if outspeed_at_speed_stage == -1 else f"at {outspeed_at_speed_stage:+d} stage"
                        speed_benchmark["speed_stage_note"] = f"Target at {pre_tailwind_speed} Speed ({stage_name})"
                    if outspeed_target_has_tailwind:
                        speed_benchmark["target_tailwind_speed"] = target_speed
                        speed_benchmark["tailwind_note"] = f"Target with Tailwind: {pre_tailwind_speed} -> {target_speed}"
                    # Add MY Pokemon's modifiers info
                    if my_pokemon_has_booster:
                        speed_benchmark["my_booster_note"] = f"My Protosynthesis/Quark Drive: {my_base_speed} -> {int(my_base_speed * 1.5)}"
                    if my_pokemon_has_tailwind:
                        pre_tw = int(my_base_speed * 1.5) if my_pokemon_has_booster else my_base_speed
                        speed_benchmark["my_tailwind_note"] = f"My Tailwind: {pre_tw} -> {my_final_speed}"
                    results["benchmarks"]["speed"] = speed_benchmark
                except Exception as e:
                    results["benchmarks"]["speed"] = {"error": str(e)}

            # 2. Calculate remaining EVs for bulk/offense
            remaining_evs = 508 - speed_evs_needed

            # Auto-fill offensive_evs to 252 when prioritize=offense but no value given
            if prioritize == "offense" and offensive_evs == 0:
                offensive_evs = 252

            if prioritize == "offense" and offensive_evs > 0:
                atk_evs = normalize_evs(min(offensive_evs, remaining_evs))
                remaining_evs -= atk_evs
            else:
                atk_evs = 0

            # 3. Distribute remaining EVs to bulk
            # If we have a survival benchmark, optimize for that
            hp_evs = 0
            def_evs = 0
            spd_evs = 0

            if survive_pokemon and survive_move:
                try:
                    atk_base = await pokeapi.get_base_stats(survive_pokemon)
                    atk_types = await pokeapi.get_pokemon_types(survive_pokemon)
                    move = await pokeapi.get_move(survive_move, user_name=survive_pokemon)

                    is_physical = move.category == MoveCategory.PHYSICAL

                    # Fetch attacker's most common spread from Smogon if not specified
                    smogon_spread = await _get_common_spread(survive_pokemon)
                    smogon_used = False

                    if smogon_spread:
                        # Use Smogon spread if user didn't override
                        if survive_pokemon_nature == "adamant":  # default value - replace with Smogon
                            survive_pokemon_nature = smogon_spread.get("nature", survive_pokemon_nature)
                            smogon_used = True
                        if survive_pokemon_evs == 252:  # default value - replace with Smogon
                            evs = smogon_spread.get("evs", {})
                            if is_physical:
                                survive_pokemon_evs = evs.get("attack", 252)
                            else:
                                survive_pokemon_evs = evs.get("special_attack", 252)
                            smogon_used = True
                        if survive_pokemon_item is None:
                            survive_pokemon_item = smogon_spread.get("item")
                            smogon_used = True
                        if survive_pokemon_ability is None:
                            survive_pokemon_ability = smogon_spread.get("ability")
                            smogon_used = True

                    # Fallback to known meta synergies if Smogon didn't provide item/ability
                    attacker_key = survive_pokemon.lower().replace(" ", "-")
                    if attacker_key in META_SYNERGIES:
                        default_item, default_ability = META_SYNERGIES[attacker_key]
                        if survive_pokemon_item is None:
                            survive_pokemon_item = default_item
                        if survive_pokemon_ability is None:
                            survive_pokemon_ability = default_ability

                    atk_nature = Nature(survive_pokemon_nature.lower())
                    atk_nature_mod = get_nature_modifier(
                        atk_nature,
                        "attack" if is_physical else "special_attack"
                    )

                    # Auto-detect Unseen Fist for Urshifu forms
                    normalized_attacker = survive_pokemon.lower().replace(" ", "-")
                    if normalized_attacker in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
                        if not survive_pokemon_ability:
                            survive_pokemon_ability = "unseen-fist"

                    # Auto-detect Ruinous abilities from attacker
                    from vgc_mcp_core.calc.abilities import normalize_ability_name

                    sword_of_ruin = False
                    beads_of_ruin = False
                    tablets_of_ruin = False
                    vessel_of_ruin = False

                    if survive_pokemon_ability:
                        ability_lower = normalize_ability_name(survive_pokemon_ability)
                        if ability_lower == "sword-of-ruin":
                            sword_of_ruin = True
                        elif ability_lower == "beads-of-ruin":
                            beads_of_ruin = True
                        elif ability_lower == "tablets-of-ruin":
                            tablets_of_ruin = True
                        elif ability_lower == "vessel-of-ruin":
                            vessel_of_ruin = True
                    else:
                        # Auto-detect from Pokemon
                        atk_abilities = await pokeapi.get_pokemon_abilities(survive_pokemon)
                        if atk_abilities:
                            ability_lower = normalize_ability_name(atk_abilities[0])
                            if ability_lower == "sword-of-ruin":
                                sword_of_ruin = True
                                survive_pokemon_ability = "sword-of-ruin"
                            elif ability_lower == "beads-of-ruin":
                                beads_of_ruin = True
                                survive_pokemon_ability = "beads-of-ruin"
                            elif ability_lower == "tablets-of-ruin":
                                tablets_of_ruin = True
                                survive_pokemon_ability = "tablets-of-ruin"
                            elif ability_lower == "vessel-of-ruin":
                                vessel_of_ruin = True
                                survive_pokemon_ability = "vessel-of-ruin"

                    # Create attacker build
                    attacker = PokemonBuild(
                        name=survive_pokemon,
                        base_stats=atk_base,
                        types=atk_types,
                        nature=atk_nature,
                        evs=EVSpread(
                            attack=survive_pokemon_evs if is_physical else 0,
                            special_attack=0 if is_physical else survive_pokemon_evs
                        ),
                        ability=survive_pokemon_ability,
                        item=survive_pokemon_item,
                        tera_type=survive_pokemon_tera_type
                    )

                    # Find optimal bulk distribution to survive
                    # Math: Effective Bulk = HP × Defense
                    # When HP stat < Def stat, HP EVs are more efficient (benefits both Def and SpD)
                    # We need to try ALL valid (HP, Def) combinations, not just extremes
                    best_survival = -1000
                    best_spread = {"hp": 0, "def": 0, "spd": 0}
                    best_result = None

                    # Get nature modifiers for defense stats
                    def_nature_mod = get_nature_modifier(parsed_nature, "defense")
                    spd_nature_mod = get_nature_modifier(parsed_nature, "special_defense")

                    # Try ALL valid (HP, Def/SpD) combinations
                    for hp_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev > min(252, remaining_evs):
                            break

                        # Determine which defense stat to optimize
                        def_stat_evs = EV_BREAKPOINTS_LV50 if is_physical else [0]
                        spd_stat_evs = [0] if is_physical else EV_BREAKPOINTS_LV50

                        for def_ev in def_stat_evs:
                            if hp_ev + def_ev > remaining_evs:
                                break
                            for spd_ev in spd_stat_evs:
                                if hp_ev + def_ev + spd_ev > remaining_evs:
                                    break

                                # Normalize EVs to valid breakpoints
                                def_ev_norm = normalize_evs(min(252, def_ev))
                                spd_ev_norm = normalize_evs(min(252, spd_ev))

                                # Create defender build
                                defender = PokemonBuild(
                                    name=pokemon_name,
                                    base_stats=my_base,
                                    types=my_types,
                                    nature=parsed_nature,
                                    evs=EVSpread(
                                        hp=hp_ev,
                                        defense=def_ev_norm,
                                        special_defense=spd_ev_norm
                                    ),
                                    tera_type=defender_tera_type
                                )

                                # Calculate damage
                                modifiers = DamageModifiers(
                                    is_doubles=True,
                                    attacker_ability=survive_pokemon_ability,
                                    attacker_item=survive_pokemon_item,
                                    tera_type=survive_pokemon_tera_type,
                                    tera_active=survive_pokemon_tera_type is not None,
                                    defender_tera_type=defender_tera_type,
                                    defender_tera_active=defender_tera_type is not None,
                                    is_critical=move.always_crit,
                                    sword_of_ruin=sword_of_ruin,
                                    beads_of_ruin=beads_of_ruin,
                                    tablets_of_ruin=tablets_of_ruin,
                                    vessel_of_ruin=vessel_of_ruin
                                )
                                result = calculate_damage(attacker, defender, move, modifiers)

                                # Calculate effective bulk for tiebreaker
                                final_hp = calculate_hp(my_base.hp, 31, hp_ev, 50)
                                if is_physical:
                                    final_def = calculate_stat(my_base.defense, 31, def_ev_norm, 50, def_nature_mod)
                                else:
                                    final_def = calculate_stat(my_base.special_defense, 31, spd_ev_norm, 50, spd_nature_mod)
                                effective_bulk = final_hp * final_def

                                # Score: survival margin is priority, then minimum EVs, bulk as tiebreaker
                                survival_margin = 100 - result.max_percent
                                # Prefer: 1) highest survival, 2) minimum EVs, 3) highest bulk
                                total_defensive_evs = hp_ev + def_ev_norm + spd_ev_norm
                                score = survival_margin - (total_defensive_evs / 10000) + (effective_bulk / 100000000)

                                if score > best_survival:
                                    best_survival = score
                                    best_spread = {"hp": hp_ev, "def": def_ev_norm, "spd": spd_ev_norm}
                                    best_result = result

                    hp_evs = best_spread["hp"]
                    def_evs = best_spread["def"]
                    spd_evs = best_spread["spd"]

                    # Check if attacker has Unseen Fist (bypasses Protect)
                    has_unseen_fist = (
                        survive_pokemon_ability and
                        survive_pokemon_ability.lower().replace(" ", "-") == "unseen-fist"
                    )

                    # Calculate attacker's final stats for the spread display
                    atk_nature_mod_atk = get_nature_modifier(atk_nature, "attack")
                    atk_nature_mod_spa = get_nature_modifier(atk_nature, "special_attack")
                    attacker_final_atk = calculate_stat(atk_base.attack, 31, survive_pokemon_evs if is_physical else 0, 50, atk_nature_mod_atk)
                    attacker_final_spa = calculate_stat(atk_base.special_attack, 31, 0 if is_physical else survive_pokemon_evs, 50, atk_nature_mod_spa)
                    attacker_final_hp = calculate_hp(atk_base.hp, 31, 0, 50)

                    # Build attacker spread string (Showdown format: "252+ Atk")
                    stat_name = "Atk" if is_physical else "SpA"
                    nature_boost = "+" if (is_physical and atk_nature_mod_atk > 1.0) or (not is_physical and atk_nature_mod_spa > 1.0) else ""
                    nature_penalty = "-" if (is_physical and atk_nature_mod_atk < 1.0) or (not is_physical and atk_nature_mod_spa < 1.0) else ""
                    nature_indicator = nature_boost or nature_penalty
                    item_str = f" {survive_pokemon_item.replace('-', ' ').title()}" if survive_pokemon_item else ""
                    attacker_spread_str = f"{survive_pokemon_evs}{nature_indicator} {stat_name}{item_str} {survive_pokemon}"

                    # Build defender spread string
                    relevant_def_evs = best_spread["def"] if is_physical else best_spread["spd"]
                    def_stat_name = "Def" if is_physical else "SpD"
                    defender_spread_str = f"{best_spread['hp']} HP / {relevant_def_evs} {def_stat_name} {pokemon_name}"

                    # Build analysis string
                    analysis_str = f"{attacker_spread_str}'s {survive_move} vs {defender_spread_str}: {format_percent(best_result.min_percent)}-{format_percent(best_result.max_percent)}%"

                    results["benchmarks"]["survival"] = {
                        "attacker": survive_pokemon,
                        "move": survive_move,
                        "attacker_spread": attacker_spread_str,
                        "attacker_nature": survive_pokemon_nature,
                        "attacker_evs": survive_pokemon_evs,
                        "attacker_ability": survive_pokemon_ability,
                        "attacker_item": survive_pokemon_item,
                        "attacker_tera": survive_pokemon_tera_type,
                        "attacker_final_stats": {
                            "hp": attacker_final_hp,
                            "attack": attacker_final_atk,
                            "special_attack": attacker_final_spa
                        },
                        "smogon_spread_used": smogon_used,
                        "defender_tera": defender_tera_type,
                        "damage_range": best_result.damage_range,
                        "damage_percent": f"{format_percent(best_result.min_percent)}-{format_percent(best_result.max_percent)}%",
                        "survives": best_result.max_percent < 100,
                        "hp_remaining": f"{100 - best_result.max_percent:.1f}%",
                        "analysis": analysis_str,
                        "unseen_fist_warning": (
                            "WARNING: Attacker has Unseen Fist - contact moves bypass Protect!"
                            if has_unseen_fist else None
                        )
                    }

                except Exception as e:
                    results["benchmarks"]["survival"] = {"error": str(e)}
                    # Default bulk distribution
                    hp_evs = min(252, remaining_evs)
                    remaining_evs -= hp_evs
                    def_evs = min(252, remaining_evs)
            else:
                # No survival benchmark, just max HP
                hp_evs = normalize_evs(min(252, remaining_evs))
                remaining_evs -= hp_evs
                def_evs = normalize_evs(min(252, remaining_evs // 2))
                spd_evs = normalize_evs(min(252, remaining_evs - def_evs))

            # Ensure EVs total 508 - distribute leftover based on user intent
            total_used = hp_evs + atk_evs + def_evs + spd_evs + speed_evs_needed

            if total_used < 508:
                leftover = 508 - total_used

                # Priority 1: Speed creep (if user provided speed benchmark)
                # User cares about speed - add more to beat others targeting same tier
                if leftover > 0 and outspeed_pokemon and speed_evs_needed < 252:
                    extra_spe = min(252 - speed_evs_needed, leftover)
                    speed_evs_needed += extra_spe
                    leftover -= extra_spe

                # Priority 2 & 3: Optimal bulk distribution based on base stats
                # Use mathematical optimization: effective bulk = HP * Def
                # High base HP → invest more in defenses; High base Def → invest more in HP
                if leftover > 0:
                    # Determine which defense stat to optimize based on survival benchmark
                    optimize_physical = True  # Default to balanced
                    if survive_pokemon and survive_move:
                        try:
                            move_check = await pokeapi.get_move(survive_move)
                            optimize_physical = move_check.category == MoveCategory.PHYSICAL
                        except Exception:
                            pass

                    # Calculate current final stats to determine optimal distribution
                    current_hp = calculate_hp(my_base.hp, 31, hp_evs, 50)
                    def_mod = get_nature_modifier(parsed_nature, "defense")
                    spd_mod = get_nature_modifier(parsed_nature, "special_defense")
                    current_def = calculate_stat(my_base.defense, 31, def_evs, 50, def_mod)
                    current_spd = calculate_stat(my_base.special_defense, 31, spd_evs, 50, spd_mod)

                    # Optimal bulk is when HP ≈ Defense (marginal gains equal)
                    # If HP >> Def, invest in Def; if Def >> HP, invest in HP
                    target_def = current_def if optimize_physical else current_spd

                    while leftover > 0:
                        # Recalculate current stats
                        current_hp = calculate_hp(my_base.hp, 31, hp_evs, 50)
                        if optimize_physical:
                            current_def = calculate_stat(my_base.defense, 31, def_evs, 50, def_mod)
                            target_def = current_def
                            can_add_def = def_evs < 252
                        else:
                            current_spd = calculate_stat(my_base.special_defense, 31, spd_evs, 50, spd_mod)
                            target_def = current_spd
                            can_add_def = spd_evs < 252
                        can_add_hp = hp_evs < 252

                        # If HP > Defense, invest in defense; otherwise invest in HP
                        if current_hp > target_def and can_add_def:
                            if optimize_physical:
                                def_evs = min(252, def_evs + 4)
                            else:
                                spd_evs = min(252, spd_evs + 4)
                            leftover -= 4
                        elif can_add_hp:
                            hp_evs = min(252, hp_evs + 4)
                            leftover -= 4
                        elif can_add_def:
                            if optimize_physical:
                                def_evs = min(252, def_evs + 4)
                            else:
                                spd_evs = min(252, spd_evs + 4)
                            leftover -= 4
                        else:
                            # All relevant stats maxed, put remainder in other defense
                            if optimize_physical:
                                spd_evs = min(252, spd_evs + leftover)
                            else:
                                def_evs = min(252, def_evs + leftover)
                            leftover = 0

                    # Normalize all EVs to valid breakpoints after distribution
                    hp_evs = normalize_evs(hp_evs)
                    def_evs = normalize_evs(def_evs)
                    spd_evs = normalize_evs(spd_evs)

            # 4. Calculate final stats
            speed_mod = get_nature_modifier(parsed_nature, "speed")
            atk_mod = get_nature_modifier(parsed_nature, "attack")
            spa_mod = get_nature_modifier(parsed_nature, "special_attack")
            def_mod = get_nature_modifier(parsed_nature, "defense")
            spd_mod = get_nature_modifier(parsed_nature, "special_defense")

            final_stats = {
                "hp": calculate_hp(my_base.hp, 31, hp_evs, 50),
                "attack": calculate_stat(my_base.attack, 31, atk_evs if my_base.attack > my_base.special_attack else 0, 50, atk_mod),
                "defense": calculate_stat(my_base.defense, 31, def_evs, 50, def_mod),
                "special_attack": calculate_stat(my_base.special_attack, 31, atk_evs if my_base.special_attack > my_base.attack else 0, 50, spa_mod),
                "special_defense": calculate_stat(my_base.special_defense, 31, spd_evs, 50, spd_mod),
                "speed": calculate_stat(my_base.speed, 31, speed_evs_needed, 50, speed_mod)
            }

            # Determine which offensive stat to use
            is_physical = my_base.attack > my_base.special_attack

            results["spread"] = {
                "hp_evs": hp_evs,
                "atk_evs": atk_evs if is_physical else 0,
                "def_evs": def_evs,
                "spa_evs": 0 if is_physical else atk_evs,
                "spd_evs": spd_evs,
                "spe_evs": speed_evs_needed,
                "total": hp_evs + atk_evs + def_evs + spd_evs + speed_evs_needed
            }
            results["final_stats"] = final_stats
            results["summary"] = (
                f"{pokemon_name.title()} @ {nature.title()}: "
                f"{hp_evs} HP / {atk_evs} {'Atk' if is_physical else 'SpA'} / "
                f"{def_evs} Def / {spd_evs} SpD / {speed_evs_needed} Spe"
            )

            # Create PokemonBuild with optimized spread for Showdown export
            optimized_pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=my_base,
                types=my_types,
                nature=parsed_nature,
                evs=EVSpread(
                    hp=hp_evs,
                    attack=atk_evs if is_physical else 0,
                    defense=def_evs,
                    special_attack=0 if is_physical else atk_evs,
                    special_defense=spd_evs,
                    speed=speed_evs_needed
                ),
                tera_type=defender_tera_type
            )
            results["showdown_paste"] = pokemon_build_to_showdown(optimized_pokemon)

            return results

        except Exception as e:
            return {"error": str(e)}

    # Natures to try when auto-selecting, prioritizing BULK-BOOSTING natures
    # Speed EVs are cheap, nature boost is precious - use EVs for speed, nature for bulk
    # Separate lists for physical vs special attackers to avoid -Atk/-SpA penalties on their main stat

    # For PHYSICAL attackers (Atk > SpA): Jolly before Timid, prefer -SpA natures
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

    # For SPECIAL attackers (SpA > Atk): Timid before Jolly, prefer -Atk natures
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

    @mcp.tool()
    async def optimize_dual_survival_spread(
        pokemon_name: str,
        survive_hit1_attacker: str,
        survive_hit1_move: str,
        survive_hit2_attacker: str,
        survive_hit2_move: str,
        nature: Optional[str] = None,
        outspeed_pokemon: Optional[str] = None,
        outspeed_pokemon_nature: str = "timid",
        outspeed_pokemon_evs: int = 252,
        outspeed_at_speed_stage: int = 0,
        outspeed_target_has_booster: bool = False,
        outspeed_target_has_tailwind: bool = False,
        my_pokemon_has_booster: bool = False,
        my_pokemon_has_tailwind: bool = False,
        speed_evs: Optional[int] = None,
        survive_hit1_nature: Optional[str] = None,
        survive_hit1_evs: Optional[int] = None,
        survive_hit1_item: Optional[str] = None,
        survive_hit1_ability: Optional[str] = None,
        survive_hit1_tera_type: Optional[str] = None,
        survive_hit2_nature: Optional[str] = None,
        survive_hit2_evs: Optional[int] = None,
        survive_hit2_item: Optional[str] = None,
        survive_hit2_ability: Optional[str] = None,
        survive_hit2_tera_type: Optional[str] = None,
        defender_tera_type: Optional[str] = None,
        target_survival: float = 100.0
    ) -> dict:
        """
        Find optimal EV spread to survive TWO DIFFERENT attacks while meeting a speed benchmark.

        PRIORITY ORDER: Speed EVs first (minimum needed), then bulk optimization, nature selected last.

        If nature is not specified, the tool automatically selects the best nature that:
        1. Requires minimum Speed EVs to outspeed the target
        2. Can still survive both attacks at 100%
        3. Leaves maximum EVs for bulk/offense

        IMPORTANT - WHEN TO USE THIS TOOL:
        - Use ONLY when the user wants to survive TWO DIFFERENT attacks from TWO DIFFERENT attackers
        - Examples: "survive Wicked Blow AND Sludge Bomb", "live both Moonblast and Sacred Sword"

        DO NOT USE THIS TOOL when:
        - User only mentions ONE attacker or ONE move (use design_spread_with_benchmarks instead)
        - User wants to survive the same attack twice (that's a 2HKO check, not dual survival)
        - User is asking about max Attack/SpA builds (use design_spread_with_benchmarks with prioritize="offense")

        Use this when asked questions like:
        - "I want my Ogerpon-Wellspring to survive Tera Dark Wicked Blow AND Sludge Bomb"
        - "Can Rillaboom live both Moonblast from Flutter Mane AND Heat Wave from Tornadus?"

        This tool searches ALL valid (HP, Def, SpD) combinations to find the optimal spread,
        or reports if the benchmarks are mathematically impossible.

        Args:
            pokemon_name: Your Pokemon (e.g., "ogerpon-wellspring")
            nature: Your Pokemon's nature (optional - auto-selects best if not provided)
            survive_hit1_attacker: First attacker to survive (e.g., "urshifu") - MUST be different from hit2
            survive_hit1_move: First move to survive (e.g., "wicked-blow")
            survive_hit2_attacker: Second attacker to survive (e.g., "landorus-incarnate") - MUST be different from hit1
            survive_hit2_move: Second move to survive (e.g., "sludge-bomb")
            outspeed_pokemon: Pokemon to outspeed (optional)
            outspeed_pokemon_nature: Target's nature (default "timid")
            outspeed_pokemon_evs: Target's speed EVs (default 252)
            outspeed_at_speed_stage: Target's speed stage (-1 = after Icy Wind, -2 = after 2x Icy Wind)
            outspeed_target_has_booster: True if target has Protosynthesis/Quark Drive speed boost (1.5x)
            outspeed_target_has_tailwind: True if target has Tailwind active (2x speed)
            my_pokemon_has_booster: True if YOUR Pokemon has Protosynthesis/Quark Drive speed boost (1.5x)
            my_pokemon_has_tailwind: True if YOUR Pokemon has Tailwind active (2x speed)
            speed_evs: Override speed EVs directly instead of calculating from outspeed target
            survive_hit1_nature: First attacker's nature (auto-fetched from Smogon if not specified)
            survive_hit1_evs: First attacker's offensive EVs
            survive_hit1_item: First attacker's item
            survive_hit1_ability: First attacker's ability
            survive_hit1_tera_type: First attacker's Tera type if Terastallized
            survive_hit2_nature: Second attacker's nature
            survive_hit2_evs: Second attacker's offensive EVs
            survive_hit2_item: Second attacker's item
            survive_hit2_ability: Second attacker's ability
            survive_hit2_tera_type: Second attacker's Tera type if Terastallized
            defender_tera_type: Your Pokemon's Tera type if Terastallizing
            target_survival: Minimum survival % to consider "surviving" (default 93.75 = 15/16 rolls)

        Returns:
            Optimal spread with survival breakdown for each attack, or "IMPOSSIBLE" if no valid spread exists
        """
        try:
            # Auto-assign fixed Tera types (Ogerpon forms, Terapagos)
            from vgc_mcp_core.calc.items import get_fixed_tera_type
            if survive_hit1_tera_type is not None:
                fixed_tera = get_fixed_tera_type(survive_hit1_attacker)
                if fixed_tera and survive_hit1_tera_type.lower() != fixed_tera.lower():
                    survive_hit1_tera_type = fixed_tera
            if survive_hit2_tera_type is not None:
                fixed_tera = get_fixed_tera_type(survive_hit2_attacker)
                if fixed_tera and survive_hit2_tera_type.lower() != fixed_tera.lower():
                    survive_hit2_tera_type = fixed_tera
            if defender_tera_type is not None:
                fixed_tera = get_fixed_tera_type(pokemon_name)
                if fixed_tera and defender_tera_type.lower() != fixed_tera.lower():
                    defender_tera_type = fixed_tera

            # Fetch defender data
            my_base = await pokeapi.get_base_stats(pokemon_name)
            my_types = await pokeapi.get_pokemon_types(pokemon_name)

            # Track if nature was auto-selected
            nature_auto_selected = nature is None

            # If nature specified, validate it
            if nature is not None:
                try:
                    parsed_nature = Nature(nature.lower())
                except ValueError:
                    return {"error": f"Invalid nature: {nature}"}

            # Fetch attacker 1 data
            atk1_base = await pokeapi.get_base_stats(survive_hit1_attacker)
            atk1_types = await pokeapi.get_pokemon_types(survive_hit1_attacker)
            move1 = await pokeapi.get_move(survive_hit1_move, user_name=survive_hit1_attacker)
            is_physical1 = move1.category == MoveCategory.PHYSICAL

            # Fetch attacker 2 data
            atk2_base = await pokeapi.get_base_stats(survive_hit2_attacker)
            atk2_types = await pokeapi.get_pokemon_types(survive_hit2_attacker)
            move2 = await pokeapi.get_move(survive_hit2_move, user_name=survive_hit2_attacker)
            is_physical2 = move2.category == MoveCategory.PHYSICAL

            # Auto-fetch Smogon spreads for attackers
            smogon1 = await _get_common_spread(survive_hit1_attacker)
            smogon2 = await _get_common_spread(survive_hit2_attacker)

            # Fill in attacker 1 defaults
            if smogon1:
                if survive_hit1_nature is None:
                    survive_hit1_nature = smogon1.get("nature", "adamant")
                if survive_hit1_evs is None:
                    evs = smogon1.get("evs", {})
                    survive_hit1_evs = evs.get("attack" if is_physical1 else "special_attack", 252)
                if survive_hit1_item is None:
                    survive_hit1_item = smogon1.get("item")
                if survive_hit1_ability is None:
                    survive_hit1_ability = smogon1.get("ability")
            else:
                survive_hit1_nature = survive_hit1_nature or ("adamant" if is_physical1 else "modest")
                survive_hit1_evs = survive_hit1_evs if survive_hit1_evs is not None else 252

            # Fill in attacker 2 defaults
            if smogon2:
                if survive_hit2_nature is None:
                    survive_hit2_nature = smogon2.get("nature", "adamant")
                if survive_hit2_evs is None:
                    evs = smogon2.get("evs", {})
                    survive_hit2_evs = evs.get("attack" if is_physical2 else "special_attack", 252)
                if survive_hit2_item is None:
                    survive_hit2_item = smogon2.get("item")
                if survive_hit2_ability is None:
                    survive_hit2_ability = smogon2.get("ability")
            else:
                survive_hit2_nature = survive_hit2_nature or ("adamant" if is_physical2 else "modest")
                survive_hit2_evs = survive_hit2_evs if survive_hit2_evs is not None else 252

            # Apply meta synergies fallback
            atk1_key = survive_hit1_attacker.lower().replace(" ", "-")
            if atk1_key in META_SYNERGIES:
                default_item, default_ability = META_SYNERGIES[atk1_key]
                if survive_hit1_item is None:
                    survive_hit1_item = default_item
                if survive_hit1_ability is None:
                    survive_hit1_ability = default_ability

            atk2_key = survive_hit2_attacker.lower().replace(" ", "-")
            if atk2_key in META_SYNERGIES:
                default_item, default_ability = META_SYNERGIES[atk2_key]
                if survive_hit2_item is None:
                    survive_hit2_item = default_item
                if survive_hit2_ability is None:
                    survive_hit2_ability = default_ability

            # Auto-detect Unseen Fist for Urshifu
            if atk1_key in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
                if not survive_hit1_ability:
                    survive_hit1_ability = "unseen-fist"
            if atk2_key in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
                if not survive_hit2_ability:
                    survive_hit2_ability = "unseen-fist"

            # Auto-detect Ruinous abilities for attacker 1
            # First: Direct detection from Pokemon name (most reliable)
            sword_of_ruin1 = atk1_key == "chien-pao"
            beads_of_ruin1 = atk1_key == "chi-yu"
            if sword_of_ruin1 and not survive_hit1_ability:
                survive_hit1_ability = "sword-of-ruin"
            if beads_of_ruin1 and not survive_hit1_ability:
                survive_hit1_ability = "beads-of-ruin"

            # Second: Check from ability string if set
            if not sword_of_ruin1 and not beads_of_ruin1 and survive_hit1_ability:
                ability_lower = survive_hit1_ability.lower().replace(" ", "-").replace("_", "-")
                if ability_lower == "sword-of-ruin":
                    sword_of_ruin1 = True
                elif ability_lower == "beads-of-ruin":
                    beads_of_ruin1 = True

            # Third: Fallback to PokeAPI
            if not sword_of_ruin1 and not beads_of_ruin1 and not survive_hit1_ability:
                atk1_abilities = await pokeapi.get_pokemon_abilities(survive_hit1_attacker)
                if atk1_abilities:
                    ability_lower = atk1_abilities[0].lower().replace(" ", "-")
                    if ability_lower == "sword-of-ruin":
                        sword_of_ruin1 = True
                        survive_hit1_ability = "sword-of-ruin"
                    elif ability_lower == "beads-of-ruin":
                        beads_of_ruin1 = True
                        survive_hit1_ability = "beads-of-ruin"

            # Auto-detect Ruinous abilities for attacker 2
            # First: Direct detection from Pokemon name (most reliable)
            sword_of_ruin2 = atk2_key == "chien-pao"
            beads_of_ruin2 = atk2_key == "chi-yu"
            if sword_of_ruin2 and not survive_hit2_ability:
                survive_hit2_ability = "sword-of-ruin"
            if beads_of_ruin2 and not survive_hit2_ability:
                survive_hit2_ability = "beads-of-ruin"

            # Second: Check from ability string if set
            if not sword_of_ruin2 and not beads_of_ruin2 and survive_hit2_ability:
                ability_lower = survive_hit2_ability.lower().replace(" ", "-").replace("_", "-")
                if ability_lower == "sword-of-ruin":
                    sword_of_ruin2 = True
                elif ability_lower == "beads-of-ruin":
                    beads_of_ruin2 = True

            # Third: Fallback to PokeAPI
            if not sword_of_ruin2 and not beads_of_ruin2 and not survive_hit2_ability:
                atk2_abilities = await pokeapi.get_pokemon_abilities(survive_hit2_attacker)
                if atk2_abilities:
                    ability_lower = atk2_abilities[0].lower().replace(" ", "-")
                    if ability_lower == "sword-of-ruin":
                        sword_of_ruin2 = True
                        survive_hit2_ability = "sword-of-ruin"
                    elif ability_lower == "beads-of-ruin":
                        beads_of_ruin2 = True
                        survive_hit2_ability = "beads-of-ruin"

            # Calculate target speed first (independent of our nature)
            target_speed = 0
            if speed_evs is not None:
                # User specified exact speed EVs
                pass
            elif outspeed_pokemon:
                try:
                    target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                    target_nature_parsed = Nature(outspeed_pokemon_nature.lower())
                    target_speed_mod = get_nature_modifier(target_nature_parsed, "speed")
                    target_speed = calculate_stat(
                        target_base.speed, 31, outspeed_pokemon_evs, 50, target_speed_mod
                    )

                    # Apply Protosynthesis/Quark Drive speed boost if active (1.5x, floored)
                    if outspeed_target_has_booster:
                        target_speed = int(target_speed * 1.5)

                    # Apply speed stage modifier (e.g., -1 for after Icy Wind)
                    if outspeed_at_speed_stage != 0:
                        stage_mult = SPEED_STAGE_MULTIPLIERS.get(outspeed_at_speed_stage, 1)
                        target_speed = int(target_speed * stage_mult)

                    # Apply Tailwind (2x speed, floored)
                    if outspeed_target_has_tailwind:
                        target_speed = int(target_speed * 2)
                except Exception:
                    pass

            def calc_min_speed_evs(base_speed: int, my_speed_mod: float) -> tuple[int, int]:
                """Calculate minimum speed EVs needed to outspeed target. Returns (evs, final_speed)."""
                if speed_evs is not None:
                    my_speed = calculate_stat(base_speed, 31, speed_evs, 50, my_speed_mod)
                    return speed_evs, my_speed
                if target_speed == 0:
                    return 0, calculate_stat(base_speed, 31, 0, 50, my_speed_mod)

                for ev in EV_BREAKPOINTS_LV50:
                    my_speed = calculate_stat(base_speed, 31, ev, 50, my_speed_mod)
                    my_effective_speed = my_speed
                    if my_pokemon_has_booster:
                        my_effective_speed = int(my_effective_speed * 1.5)
                    if my_pokemon_has_tailwind:
                        my_effective_speed = int(my_effective_speed * 2)
                    if my_effective_speed > target_speed:
                        return ev, my_speed
                # Can't outspeed even at max
                return 252, calculate_stat(base_speed, 31, 252, 50, my_speed_mod)

            # Determine natures to try
            if nature_auto_selected:
                # Choose nature list based on whether Pokemon is physical or special attacker
                is_special_attacker = my_base.special_attack > my_base.attack
                natures_to_try = NATURE_CANDIDATES_SPECIAL if is_special_attacker else NATURE_CANDIDATES_PHYSICAL
            else:
                # User specified nature - only try that one
                natures_to_try = [(nature.lower(), {
                    "speed": get_nature_modifier(parsed_nature, "speed"),
                    "defense": get_nature_modifier(parsed_nature, "defense"),
                    "special_defense": get_nature_modifier(parsed_nature, "special_defense"),
                    "attack": get_nature_modifier(parsed_nature, "attack"),
                    "special_attack": get_nature_modifier(parsed_nature, "special_attack"),
                })]

            # Parse attacker natures
            atk1_nature = Nature(survive_hit1_nature.lower())
            atk2_nature = Nature(survive_hit2_nature.lower())

            # Create attacker builds
            attacker1 = PokemonBuild(
                name=survive_hit1_attacker,
                base_stats=atk1_base,
                types=atk1_types,
                nature=atk1_nature,
                evs=EVSpread(
                    attack=survive_hit1_evs if is_physical1 else 0,
                    special_attack=0 if is_physical1 else survive_hit1_evs
                ),
                item=survive_hit1_item,
                ability=survive_hit1_ability,
                tera_type=survive_hit1_tera_type
            )

            attacker2 = PokemonBuild(
                name=survive_hit2_attacker,
                base_stats=atk2_base,
                types=atk2_types,
                nature=atk2_nature,
                evs=EVSpread(
                    attack=survive_hit2_evs if is_physical2 else 0,
                    special_attack=0 if is_physical2 else survive_hit2_evs
                ),
                item=survive_hit2_item,
                ability=survive_hit2_ability,
                tera_type=survive_hit2_tera_type
            )

            # Determine attack categories for HP-first optimization
            both_physical = is_physical1 and is_physical2
            both_special = (not is_physical1) and (not is_physical2)
            is_mixed = not both_physical and not both_special

            # Coarse EV steps for fallback search
            COARSE_EVS = [0, 52, 100, 148, 196, 252]

            # Track ALL valid natures (for alternative suggestions)
            all_valid_natures = []  # List of all natures that meet benchmarks

            for nature_name, nature_mods in natures_to_try:
                # Calculate speed EVs needed for this nature
                speed_mod = nature_mods["speed"]
                speed_evs_needed, my_speed_stat = calc_min_speed_evs(my_base.speed, speed_mod)

                # Check if we can even outspeed (if required)
                if target_speed > 0:
                    test_speed = calculate_stat(my_base.speed, 31, speed_evs_needed, 50, speed_mod)
                    effective_speed = test_speed
                    if my_pokemon_has_booster:
                        effective_speed = int(effective_speed * 1.5)
                    if my_pokemon_has_tailwind:
                        effective_speed = int(effective_speed * 2)
                    if effective_speed <= target_speed:
                        continue  # This nature can't outspeed, skip

                remaining_evs = 508 - speed_evs_needed
                def_nature_mod = nature_mods["defense"]
                spd_nature_mod = nature_mods["special_defense"]

                # Create a nature enum for this iteration
                try:
                    current_nature = Nature(nature_name)
                except ValueError:
                    current_nature = Nature.SERIOUS

                def test_spread(hp_ev: int, def_ev: int, spd_ev: int) -> tuple:
                    """Test a specific spread. Returns (survives_both, margin, result1, result2, pcts)."""
                    defender = PokemonBuild(
                        name=pokemon_name, base_stats=my_base, types=my_types,
                        nature=current_nature,
                        evs=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                        tera_type=defender_tera_type
                    )
                    modifiers1 = DamageModifiers(
                        is_doubles=True, attacker_item=survive_hit1_item,
                        attacker_ability=survive_hit1_ability, tera_type=survive_hit1_tera_type,
                        tera_active=survive_hit1_tera_type is not None,
                        defender_tera_type=defender_tera_type,
                        defender_tera_active=defender_tera_type is not None,
                        is_critical=move1.always_crit,
                        sword_of_ruin=sword_of_ruin1,
                        beads_of_ruin=beads_of_ruin1
                    )
                    result1 = calculate_damage(attacker1, defender, move1, modifiers1)
                    modifiers2 = DamageModifiers(
                        is_doubles=True, attacker_item=survive_hit2_item,
                        attacker_ability=survive_hit2_ability, tera_type=survive_hit2_tera_type,
                        tera_active=survive_hit2_tera_type is not None,
                        defender_tera_type=defender_tera_type,
                        defender_tera_active=defender_tera_type is not None,
                        is_critical=move2.always_crit,
                        sword_of_ruin=sword_of_ruin2,
                        beads_of_ruin=beads_of_ruin2
                    )
                    result2 = calculate_damage(attacker2, defender, move2, modifiers2)
                    survive_rolls1 = sum(1 for r in result1.rolls if r < result1.defender_hp)
                    survive_rolls2 = sum(1 for r in result2.rolls if r < result2.defender_hp)
                    survival_pct1 = (survive_rolls1 / 16) * 100
                    survival_pct2 = (survive_rolls2 / 16) * 100
                    survives1 = survival_pct1 >= target_survival
                    survives2 = survival_pct2 >= target_survival
                    margin = min(100 - result1.max_percent, 100 - result2.max_percent)
                    return (survives1 and survives2, margin, result1, result2, survival_pct1, survival_pct2, survives1, survives2)

                def find_min_stat_to_survive(hp_ev: int, stat_ev_idx: int, attack_idx: int) -> int:
                    """Find minimum Def or SpD EVs to survive a specific attack at given HP."""
                    max_ev = min(252, remaining_evs - hp_ev)
                    for test_ev in EV_BREAKPOINTS_LV50:
                        if test_ev > max_ev:
                            break
                        def_ev = test_ev if stat_ev_idx == 0 else 0
                        spd_ev = test_ev if stat_ev_idx == 1 else 0
                        survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, def_ev, spd_ev)
                        target_survives = s1 if attack_idx == 1 else s2
                        if target_survives:
                            return test_ev
                    return -1

                # HP-first search for this nature
                best_spread = None
                best_results = None
                best_total = float('inf')

                for hp_ev in EV_BREAKPOINTS_LV50:
                    if hp_ev > min(252, remaining_evs):
                        break

                    if is_mixed:
                        phys_attack_idx = 1 if is_physical1 else 2
                        spec_attack_idx = 2 if is_physical1 else 1
                        min_def = find_min_stat_to_survive(hp_ev, 0, phys_attack_idx)
                        min_spd = find_min_stat_to_survive(hp_ev, 1, spec_attack_idx)
                        if min_def < 0 or min_spd < 0:
                            continue
                        if hp_ev + min_def + min_spd > remaining_evs:
                            continue
                        survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, min_def, min_spd)
                        if survives:
                            total = hp_ev + min_def + min_spd
                            if total < best_total:
                                best_total = total
                                best_spread = {"hp": hp_ev, "def": min_def, "spd": min_spd}
                                best_results = {"result1": r1, "result2": r2, "survival_pct1": pct1, "survival_pct2": pct2, "survives1": s1, "survives2": s2}

                    elif both_physical:
                        for def_ev in EV_BREAKPOINTS_LV50:
                            if hp_ev + def_ev > remaining_evs:
                                break
                            survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, def_ev, 0)
                            if survives:
                                total = hp_ev + def_ev
                                if total < best_total:
                                    best_total = total
                                    best_spread = {"hp": hp_ev, "def": def_ev, "spd": 0}
                                    best_results = {"result1": r1, "result2": r2, "survival_pct1": pct1, "survival_pct2": pct2, "survives1": s1, "survives2": s2}
                                break

                    else:  # both_special
                        for spd_ev in EV_BREAKPOINTS_LV50:
                            if hp_ev + spd_ev > remaining_evs:
                                break
                            survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, 0, spd_ev)
                            if survives:
                                total = hp_ev + spd_ev
                                if total < best_total:
                                    best_total = total
                                    best_spread = {"hp": hp_ev, "def": 0, "spd": spd_ev}
                                    best_results = {"result1": r1, "result2": r2, "survival_pct1": pct1, "survival_pct2": pct2, "survives1": s1, "survives2": s2}
                                break

                # If this nature found a valid spread, add it to the list
                if best_spread and best_results and best_results["survives1"] and best_results["survives2"]:
                    total_evs = speed_evs_needed + best_spread["hp"] + best_spread["def"] + best_spread["spd"]
                    all_valid_natures.append({
                        "nature": nature_name,
                        "speed_evs": speed_evs_needed,
                        "spread": best_spread,
                        "results": best_results,
                        "mods": nature_mods,
                        "total_evs": total_evs,
                        "my_speed_stat": my_speed_stat
                    })

            # If no nature found a valid spread, try best effort with first nature
            if not all_valid_natures:
                # Use first nature for best effort
                nature_name, nature_mods = natures_to_try[0]
                speed_mod = nature_mods["speed"]
                speed_evs_needed, my_speed_stat = calc_min_speed_evs(my_base.speed, speed_mod)
                remaining_evs = 508 - speed_evs_needed
                def_nature_mod = nature_mods["defense"]
                spd_nature_mod = nature_mods["special_defense"]
                try:
                    current_nature = Nature(nature_name)
                except ValueError:
                    current_nature = Nature.SERIOUS

                def test_spread_fallback(hp_ev: int, def_ev: int, spd_ev: int) -> tuple:
                    defender = PokemonBuild(
                        name=pokemon_name, base_stats=my_base, types=my_types,
                        nature=current_nature,
                        evs=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                        tera_type=defender_tera_type
                    )
                    modifiers1 = DamageModifiers(
                        is_doubles=True, attacker_item=survive_hit1_item,
                        attacker_ability=survive_hit1_ability, tera_type=survive_hit1_tera_type,
                        tera_active=survive_hit1_tera_type is not None,
                        defender_tera_type=defender_tera_type,
                        defender_tera_active=defender_tera_type is not None,
                        is_critical=move1.always_crit,
                        sword_of_ruin=sword_of_ruin1,
                        beads_of_ruin=beads_of_ruin1
                    )
                    result1 = calculate_damage(attacker1, defender, move1, modifiers1)
                    modifiers2 = DamageModifiers(
                        is_doubles=True, attacker_item=survive_hit2_item,
                        attacker_ability=survive_hit2_ability, tera_type=survive_hit2_tera_type,
                        tera_active=survive_hit2_tera_type is not None,
                        defender_tera_type=defender_tera_type,
                        defender_tera_active=defender_tera_type is not None,
                        is_critical=move2.always_crit,
                        sword_of_ruin=sword_of_ruin2,
                        beads_of_ruin=beads_of_ruin2
                    )
                    result2 = calculate_damage(attacker2, defender, move2, modifiers2)
                    survive_rolls1 = sum(1 for r in result1.rolls if r < result1.defender_hp)
                    survive_rolls2 = sum(1 for r in result2.rolls if r < result2.defender_hp)
                    survival_pct1 = (survive_rolls1 / 16) * 100
                    survival_pct2 = (survive_rolls2 / 16) * 100
                    survives1 = survival_pct1 >= target_survival
                    survives2 = survival_pct2 >= target_survival
                    margin = min(100 - result1.max_percent, 100 - result2.max_percent)
                    return (survives1 and survives2, margin, result1, result2, survival_pct1, survival_pct2, survives1, survives2)

                best_margin = -float('inf')
                best_spread = None
                best_results = None
                for hp_ev in COARSE_EVS:
                    if hp_ev > min(252, remaining_evs):
                        break
                    for def_ev in COARSE_EVS:
                        if hp_ev + def_ev > remaining_evs:
                            break
                        spd_ev = min(252, remaining_evs - hp_ev - def_ev)
                        spd_ev = normalize_evs(spd_ev)
                        survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread_fallback(hp_ev, def_ev, spd_ev)
                        if margin > best_margin:
                            best_margin = margin
                            best_spread = {"hp": hp_ev, "def": def_ev, "spd": spd_ev}
                            best_results = {"result1": r1, "result2": r2, "survival_pct1": pct1, "survival_pct2": pct2, "survives1": s1, "survives2": s2}

                if best_spread is None:
                    return {
                        "verdict": "IMPOSSIBLE",
                        "error": "No valid EV spread found - benchmarks may be impossible",
                        "speed_evs_needed": speed_evs_needed,
                        "remaining_for_bulk": remaining_evs
                    }

                # Store fallback result
                all_valid_natures.append({
                    "nature": nature_name,
                    "speed_evs": speed_evs_needed,
                    "spread": best_spread,
                    "results": best_results,
                    "mods": nature_mods,
                    "total_evs": 508,
                    "my_speed_stat": my_speed_stat
                })

            # Sort all valid natures by speed EVs (ascending), then total EVs (ascending)
            # Prioritize: 1. Less speed EVs needed, 2. Less total EVs
            all_valid_natures.sort(key=lambda x: (x["speed_evs"], x["total_evs"]))

            # Pick optimal (first one)
            optimal = all_valid_natures[0]

            # Generate alternative natures (next 2-3)
            alternative_natures = []
            for alt in all_valid_natures[1:4]:  # Top 3 alternatives
                explanation = _generate_nature_explanation(optimal, alt)
                alternative_natures.append({
                    "nature": alt["nature"],
                    "spread": {
                        "hp_evs": alt["spread"]["hp"],
                        "def_evs": alt["spread"]["def"],
                        "spd_evs": alt["spread"]["spd"],
                        "spe_evs": alt["speed_evs"]
                    },
                    "total_evs": alt["total_evs"],
                    "ev_difference": f"+{alt['total_evs'] - optimal['total_evs']} EVs vs optimal",
                    "explanation": explanation
                })

            # Unpack the optimal result
            chosen_nature = optimal["nature"]
            speed_evs_needed = optimal["speed_evs"]
            best_spread = optimal["spread"]
            best_results = optimal["results"]
            nature_mods = optimal["mods"]
            total_evs = optimal["total_evs"]
            my_speed_stat = optimal["my_speed_stat"]
            def_nature_mod = nature_mods["defense"]
            spd_nature_mod = nature_mods["special_defense"]
            speed_nature_mod = nature_mods["speed"]

            # Calculate offensive EVs (normalized to valid breakpoints)
            raw_offensive = 508 - speed_evs_needed - best_spread["hp"] - best_spread["def"] - best_spread["spd"]
            offensive_evs = normalize_evs(raw_offensive)
            leftover = raw_offensive - offensive_evs

            # Put leftover EVs in SpD (4 EVs = +1 stat point at level 50)
            extra_spd = normalize_evs(leftover) if leftover >= 4 else 0
            final_spd_evs = best_spread["spd"] + extra_spd

            # Calculate final stats (using final_spd_evs for SpD)
            final_hp = calculate_hp(my_base.hp, 31, best_spread["hp"], 50)
            final_def = calculate_stat(my_base.defense, 31, best_spread["def"], 50, def_nature_mod)
            final_spd_stat = calculate_stat(my_base.special_defense, 31, final_spd_evs, 50, spd_nature_mod)
            final_spe = calculate_stat(my_base.speed, 31, speed_evs_needed, 50, speed_nature_mod)

            r1 = best_results["result1"]
            r2 = best_results["result2"]

            both_survive = best_results["survives1"] and best_results["survives2"]

            if both_survive:
                verdict = "POSSIBLE - Survives both attacks (100% of rolls)"
            else:
                verdict = "IMPOSSIBLE - Cannot guarantee survival on both attacks"

            # Build attacker spread strings
            atk1_stat = "Atk" if is_physical1 else "SpA"
            atk1_mod = get_nature_modifier(atk1_nature, "attack" if is_physical1 else "special_attack")
            atk1_nature_ind = "+" if atk1_mod > 1.0 else ("-" if atk1_mod < 1.0 else "")
            atk1_spread_str = f"{survive_hit1_evs}{atk1_nature_ind} {atk1_stat}"
            if survive_hit1_item:
                atk1_spread_str += f" {survive_hit1_item.replace('-', ' ').title()}"
            atk1_spread_str += f" {survive_hit1_attacker}"

            atk2_stat = "Atk" if is_physical2 else "SpA"
            atk2_mod = get_nature_modifier(atk2_nature, "attack" if is_physical2 else "special_attack")
            atk2_nature_ind = "+" if atk2_mod > 1.0 else ("-" if atk2_mod < 1.0 else "")
            atk2_spread_str = f"{survive_hit2_evs}{atk2_nature_ind} {atk2_stat}"
            if survive_hit2_item:
                atk2_spread_str += f" {survive_hit2_item.replace('-', ' ').title()}"
            atk2_spread_str += f" {survive_hit2_attacker}"

            # Build nature reason
            if nature_auto_selected:
                nature_reason = f"Auto-selected: {speed_evs_needed} Spe EVs needed to outspeed target"
            else:
                nature_reason = "User specified"

            # Create PokemonBuild with optimized spread for Showdown export
            chosen_nature_enum = Nature(chosen_nature.lower())
            optimized_pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=my_base,
                types=my_types,
                nature=chosen_nature_enum,
                evs=EVSpread(
                    hp=best_spread["hp"],
                    attack=0,  # This is a defensive spread
                    defense=best_spread["def"],
                    special_attack=offensive_evs,
                    special_defense=final_spd_evs,
                    speed=speed_evs_needed
                ),
                tera_type=defender_tera_type
            )

            return {
                "pokemon": pokemon_name,
                "nature": chosen_nature,
                "nature_auto_selected": nature_auto_selected,
                "nature_reason": nature_reason,
                "verdict": verdict,
                "spread": {
                    "hp_evs": best_spread["hp"],
                    "def_evs": best_spread["def"],
                    "spd_evs": final_spd_evs,  # Includes extra EVs if available
                    "spe_evs": speed_evs_needed,
                    "spa_evs": offensive_evs,  # Leftover EVs for offense (normalized)
                    "total": best_spread["hp"] + best_spread["def"] + final_spd_evs + speed_evs_needed + offensive_evs
                },
                "final_stats": {
                    "hp": final_hp,
                    "defense": final_def,
                    "special_defense": final_spd_stat,
                    "speed": final_spe
                },
                "speed_benchmark": {
                    "outspeeds": outspeed_pokemon,
                    "target_speed": target_speed,
                    "my_speed": final_spe,
                    "outspeeds_target": final_spe > target_speed if outspeed_pokemon else None
                },
                "survival_results": [
                    {
                        "attacker": survive_hit1_attacker,
                        "move": survive_hit1_move,
                        "attacker_spread": atk1_spread_str,
                        "attacker_nature": survive_hit1_nature,
                        "attacker_evs": survive_hit1_evs,
                        "attacker_item": survive_hit1_item,
                        "attacker_ability": survive_hit1_ability,
                        "tera_type": survive_hit1_tera_type,
                        "damage_range": r1.damage_range,
                        "damage_percent": f"{r1.min_percent:.2f}-{r1.max_percent:.2f}%",
                        "survival_chance": f"{best_results['survival_pct1']:.2f}%",
                        "survives_target": best_results["survives1"]
                    },
                    {
                        "attacker": survive_hit2_attacker,
                        "move": survive_hit2_move,
                        "attacker_spread": atk2_spread_str,
                        "attacker_nature": survive_hit2_nature,
                        "attacker_evs": survive_hit2_evs,
                        "attacker_item": survive_hit2_item,
                        "attacker_ability": survive_hit2_ability,
                        "tera_type": survive_hit2_tera_type,
                        "damage_range": r2.damage_range,
                        "damage_percent": f"{r2.min_percent:.2f}-{r2.max_percent:.2f}%",
                        "survival_chance": f"{best_results['survival_pct2']:.2f}%",
                        "survives_target": best_results["survives2"]
                    }
                ],
                "summary": (
                    f"{pokemon_name.title()} @ {chosen_nature.title()}: "
                    f"{best_spread['hp']} HP / {best_spread['def']} Def / {offensive_evs} SpA / {final_spd_evs} SpD / {speed_evs_needed} Spe"
                ),
                "analysis": (
                    f"With {chosen_nature.title()} {best_spread['hp']} HP / {best_spread['def']} Def / {final_spd_evs} SpD / {speed_evs_needed} Spe, "
                    f"{pokemon_name.title()} takes {r1.min_percent:.2f}-{r1.max_percent:.2f}% from {survive_hit1_move} "
                    f"({atk1_spread_str}) ({best_results['survival_pct1']:.2f}% survival) and "
                    f"{r2.min_percent:.2f}-{r2.max_percent:.2f}% from {survive_hit2_move} "
                    f"({atk2_spread_str}) ({best_results['survival_pct2']:.2f}% survival)"
                ),
                "showdown_paste": pokemon_build_to_showdown(optimized_pokemon),
                "alternative_natures": alternative_natures
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def optimize_multi_survival_spread(
        pokemon_name: str,
        threats: list[dict],
        nature: Optional[str] = None,
        outspeed_pokemon: Optional[str] = None,
        outspeed_pokemon_nature: str = "timid",
        outspeed_pokemon_evs: int = 252,
        outspeed_at_speed_stage: int = 0,
        outspeed_target_has_booster: bool = False,
        outspeed_target_has_tailwind: bool = False,
        my_pokemon_has_booster: bool = False,
        my_pokemon_has_tailwind: bool = False,
        speed_evs: Optional[int] = None,
        defender_tera_type: Optional[str] = None,
        target_survival: float = 93.75
    ) -> dict:
        """
        Find optimal EV spread to survive 3-6 different attacks while meeting speed benchmark.

        This tool extends optimize_dual_survival_spread to handle multiple threats (3-6 Pokemon).
        Uses a hybrid algorithm: HP-first optimization for 3 threats, hill climbing for 4-6.

        IMPORTANT - WHEN TO USE THIS TOOL:
        - Use when the user wants to survive THREE OR MORE different attacks
        - Examples: "survive Urshifu, Flutter Mane, AND Chi-Yu"
        - For 2 threats, use optimize_dual_survival_spread instead (faster)

        Args:
            pokemon_name: Your Pokemon (e.g., "ogerpon-hearthflame")
            threats: List of 3-6 threat dicts, each with:
                {
                    "attacker": str,              # Required
                    "move": str,                  # Required
                    "nature": Optional[str],      # Auto-fetched if None
                    "evs": Optional[int],         # Auto-fetched if None
                    "item": Optional[str],        # Auto-fetched if None
                    "ability": Optional[str],     # Auto-fetched if None
                    "tera_type": Optional[str]    # None = no Tera
                }
            nature: Your Pokemon's nature (auto-selected if None)
            outspeed_pokemon: Pokemon to outspeed (optional)
            outspeed_pokemon_nature: Target's nature (default "timid")
            outspeed_pokemon_evs: Target's speed EVs (default 252)
            outspeed_at_speed_stage: Target's speed stage (e.g., -1 after Icy Wind)
            outspeed_target_has_booster: True if target has Protosynthesis/Quark Drive active
            outspeed_target_has_tailwind: True if target has Tailwind
            my_pokemon_has_booster: True if YOUR Pokemon has Protosynthesis/Quark Drive active
            my_pokemon_has_tailwind: True if YOUR Pokemon has Tailwind
            speed_evs: Override speed EVs directly
            defender_tera_type: Your Tera type if Terastallizing
            target_survival: Minimum survival % (default 93.75 = 15/16 rolls)

        Returns:
            {
                "success": bool,
                "optimal_spread": {...} or None,
                "threat_survival_analysis": [...],
                "impossible": bool,
                "partial_solutions": [...] if impossible,
                "tera_suggestion": {...} if impossible,
                "showdown_paste": str,
                "computation_stats": {...}
            }
        """
        start_time = time.time()

        try:
            # Validate threat count
            if len(threats) < 3:
                return {
                    "error": "This tool requires 3-6 threats. For 2 threats, use optimize_dual_survival_spread instead."
                }
            if len(threats) > 6:
                return {
                    "error": "Maximum 6 threats supported. Please reduce the number of threats or prioritize the most important ones."
                }

            # Auto-assign fixed Tera type if needed
            from vgc_mcp_core.calc.items import get_fixed_tera_type
            if defender_tera_type is not None:
                fixed_tera = get_fixed_tera_type(pokemon_name)
                if fixed_tera and defender_tera_type.lower() != fixed_tera.lower():
                    defender_tera_type = fixed_tera

            # Fetch defender data
            my_base = await pokeapi.get_base_stats(pokemon_name)
            my_types = await pokeapi.get_pokemon_types(pokemon_name)

            # Prepare all threats (fetch data, auto-detect spreads)
            prepared_threats = await _prepare_threats(threats, pokeapi)

            # Create damage cache
            cache = DamageCache(prepared_threats, pokemon_name, my_base, my_types)

            # Track if nature was auto-selected
            nature_auto_selected = nature is None

            # Speed stage multipliers (from optimize_dual_survival_spread)
            SPEED_STAGE_MULTIPLIERS = {
                -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
                0: 1,
                1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2
            }

            # Calculate target speed
            target_speed = 0
            if speed_evs is None and outspeed_pokemon:
                try:
                    target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                    target_nature_parsed = Nature(outspeed_pokemon_nature.lower())
                    target_speed_mod = get_nature_modifier(target_nature_parsed, "speed")
                    target_speed = calculate_stat(
                        target_base.speed, 31, outspeed_pokemon_evs, 50, target_speed_mod
                    )

                    if outspeed_target_has_booster:
                        target_speed = int(target_speed * 1.5)
                    if outspeed_at_speed_stage != 0:
                        stage_mult = SPEED_STAGE_MULTIPLIERS.get(outspeed_at_speed_stage, 1)
                        target_speed = int(target_speed * stage_mult)
                    if outspeed_target_has_tailwind:
                        target_speed = int(target_speed * 2)
                except Exception:
                    pass

            # Helper function to calculate minimum speed EVs needed
            def calc_min_speed_evs(base_speed: int, my_speed_mod: float) -> tuple[int, int]:
                """Calculate minimum speed EVs needed to outspeed target. Returns (evs, final_speed)."""
                if speed_evs is not None:
                    my_speed = calculate_stat(base_speed, 31, speed_evs, 50, my_speed_mod)
                    return speed_evs, my_speed
                if target_speed == 0:
                    return 0, calculate_stat(base_speed, 31, 0, 50, my_speed_mod)

                for ev in EV_BREAKPOINTS_LV50:
                    my_speed = calculate_stat(base_speed, 31, ev, 50, my_speed_mod)
                    my_effective_speed = my_speed
                    if my_pokemon_has_booster:
                        my_effective_speed = int(my_effective_speed * 1.5)
                    if my_pokemon_has_tailwind:
                        my_effective_speed = int(my_effective_speed * 2)
                    if my_effective_speed > target_speed:
                        return ev, my_speed
                return 252, calculate_stat(base_speed, 31, 252, 50, my_speed_mod)

            # Determine natures to try
            is_special_attacker = my_base.special_attack > my_base.attack
            NATURE_CANDIDATES_PHYSICAL = [
                # Bulk-boosting natures FIRST
                ("impish", {"speed": 1.0, "attack": 1.0, "defense": 1.1, "special_attack": 0.9, "special_defense": 1.0}),
                ("careful", {"speed": 1.0, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.1}),
                ("bold", {"speed": 1.0, "attack": 0.9, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
                ("calm", {"speed": 1.0, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
                # Offensive natures (can save EVs for speed benchmarks)
                ("adamant", {"speed": 1.0, "attack": 1.1, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.0}),
                # Speed-boosting natures
                ("jolly", {"speed": 1.1, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.0}),
                ("timid", {"speed": 1.1, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.0}),
                # -Speed natures (for Trick Room or min speed)
                ("brave", {"speed": 0.9, "attack": 1.1, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.0}),
                ("relaxed", {"speed": 0.9, "attack": 1.0, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
                ("sassy", {"speed": 0.9, "attack": 1.0, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
            ]
            NATURE_CANDIDATES_SPECIAL = [
                # Bulk-boosting natures FIRST
                ("bold", {"speed": 1.0, "attack": 0.9, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
                ("calm", {"speed": 1.0, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
                ("impish", {"speed": 1.0, "attack": 1.0, "defense": 1.1, "special_attack": 0.9, "special_defense": 1.0}),
                ("careful", {"speed": 1.0, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.1}),
                # Offensive natures (can save EVs for speed benchmarks)
                ("modest", {"speed": 1.0, "attack": 0.9, "defense": 1.0, "special_attack": 1.1, "special_defense": 1.0}),
                # Speed-boosting natures
                ("timid", {"speed": 1.1, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.0}),
                ("jolly", {"speed": 1.1, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.0}),
                # -Speed natures
                ("quiet", {"speed": 0.9, "attack": 1.0, "defense": 1.0, "special_attack": 1.1, "special_defense": 1.0}),
                ("relaxed", {"speed": 0.9, "attack": 1.0, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
                ("sassy", {"speed": 0.9, "attack": 1.0, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
            ]

            if nature_auto_selected:
                natures_to_try = NATURE_CANDIDATES_SPECIAL if is_special_attacker else NATURE_CANDIDATES_PHYSICAL
            else:
                try:
                    parsed_nature = Nature(nature.lower())
                    natures_to_try = [(nature.lower(), {
                        "speed": get_nature_modifier(parsed_nature, "speed"),
                        "defense": get_nature_modifier(parsed_nature, "defense"),
                        "special_defense": get_nature_modifier(parsed_nature, "special_defense"),
                        "attack": get_nature_modifier(parsed_nature, "attack"),
                        "special_attack": get_nature_modifier(parsed_nature, "special_attack"),
                    })]
                except ValueError:
                    return {"error": f"Invalid nature: {nature}"}

            # Categorize threats by type
            physical_threats = [i for i, t in enumerate(prepared_threats) if t.is_physical]
            special_threats = [i for i, t in enumerate(prepared_threats) if not t.is_physical]
            is_mixed = len(physical_threats) > 0 and len(special_threats) > 0

            # Track ALL valid natures (for alternative suggestions)
            all_valid_natures_multi = []  # List of all natures that meet benchmarks

            for nature_name, nature_mods in natures_to_try:
                speed_mod = nature_mods["speed"]
                speed_evs_needed, my_speed_stat = calc_min_speed_evs(my_base.speed, speed_mod)

                # Check if we can outspeed
                if target_speed > 0:
                    test_speed = calculate_stat(my_base.speed, 31, speed_evs_needed, 50, speed_mod)
                    effective_speed = test_speed
                    if my_pokemon_has_booster:
                        effective_speed = int(effective_speed * 1.5)
                    if my_pokemon_has_tailwind:
                        effective_speed = int(effective_speed * 2)
                    if effective_speed <= target_speed:
                        continue  # Can't outspeed with this nature

                remaining_evs = 508 - speed_evs_needed
                current_nature = Nature(nature_name)

                # Stage 1: Quick feasibility check
                feasible = _quick_feasibility_check(
                    cache, remaining_evs, current_nature, target_survival, defender_tera_type
                )

                if feasible is None:
                    # This nature can't survive all threats
                    continue

                # Stage 2: HP-first search for optimal spread
                best_spread = None
                best_results = None
                best_total = float('inf')

                for hp_ev in EV_BREAKPOINTS_LV50:
                    if hp_ev > min(252, remaining_evs):
                        break

                    if is_mixed:
                        # Find max Defense needed across all physical threats
                        max_def = 0
                        for threat_idx in physical_threats:
                            min_def = _find_min_bulk_for_threat(
                                cache, threat_idx, hp_ev, current_nature, target_survival, "defense", defender_tera_type
                            )
                            if min_def < 0:
                                max_def = 999
                                break
                            max_def = max(max_def, min_def)

                        # Find max SpD needed across all special threats
                        max_spd = 0
                        for threat_idx in special_threats:
                            min_spd = _find_min_bulk_for_threat(
                                cache, threat_idx, hp_ev, current_nature, target_survival, "special_defense", defender_tera_type
                            )
                            if min_spd < 0:
                                max_spd = 999
                                break
                            max_spd = max(max_spd, min_spd)

                        if max_def == 999 or max_spd == 999:
                            continue  # Impossible at this HP
                        if hp_ev + max_def + max_spd > remaining_evs:
                            continue  # Not enough EVs

                        # Verify all threats
                        all_survive, results = cache.test_spread_all_threats(
                            hp_ev, max_def, max_spd, current_nature, target_survival, defender_tera_type
                        )

                        if all_survive:
                            total = hp_ev + max_def + max_spd
                            if total < best_total:
                                best_total = total
                                best_spread = {"hp": hp_ev, "def": max_def, "spd": max_spd}
                                best_results = results

                    elif len(physical_threats) > 0:  # All physical
                        for def_ev in EV_BREAKPOINTS_LV50:
                            if hp_ev + def_ev > remaining_evs:
                                break

                            all_survive, results = cache.test_spread_all_threats(
                                hp_ev, def_ev, 0, current_nature, target_survival, defender_tera_type
                            )

                            if all_survive:
                                total = hp_ev + def_ev
                                if total < best_total:
                                    best_total = total
                                    best_spread = {"hp": hp_ev, "def": def_ev, "spd": 0}
                                    best_results = results
                                break  # Early exit

                    else:  # All special
                        for spd_ev in EV_BREAKPOINTS_LV50:
                            if hp_ev + spd_ev > remaining_evs:
                                break

                            all_survive, results = cache.test_spread_all_threats(
                                hp_ev, 0, spd_ev, current_nature, target_survival, defender_tera_type
                            )

                            if all_survive:
                                total = hp_ev + spd_ev
                                if total < best_total:
                                    best_total = total
                                    best_spread = {"hp": hp_ev, "def": 0, "spd": spd_ev}
                                    best_results = results
                                break  # Early exit

                # If this nature found a valid spread, add it to the list
                if best_spread and best_results:
                    total_evs = speed_evs_needed + best_spread["hp"] + best_spread["def"] + best_spread["spd"]
                    # Calculate final stats
                    final_hp = calculate_hp(my_base.hp, 31, best_spread["hp"], 50)
                    final_def = calculate_stat(my_base.defense, 31, best_spread["def"], 50, nature_mods["defense"])
                    final_spd = calculate_stat(my_base.special_defense, 31, best_spread["spd"], 50, nature_mods["special_defense"])

                    all_valid_natures_multi.append({
                        "nature": nature_name,
                        "speed_evs": speed_evs_needed,
                        "spread": best_spread,
                        "results": best_results,
                        "mods": nature_mods,
                        "total_evs": total_evs,
                        "my_speed_stat": my_speed_stat,
                        "final_hp": final_hp,
                        "final_def": final_def,
                        "final_spd": final_spd
                    })

            # Calculate computation stats
            end_time = time.time()
            time_ms = int((end_time - start_time) * 1000)
            cache_stats = cache.get_stats()

            # Check if we found a solution
            if all_valid_natures_multi:
                # Sort by speed EVs (ascending), then total EVs (ascending)
                all_valid_natures_multi.sort(key=lambda x: (x["speed_evs"], x["total_evs"]))

                # Pick optimal (first one)
                optimal_multi = all_valid_natures_multi[0]

                # Generate alternative natures (next 2-3)
                alternative_natures_multi = []
                for alt in all_valid_natures_multi[1:4]:  # Top 3 alternatives
                    explanation = _generate_nature_explanation(optimal_multi, alt)
                    alternative_natures_multi.append({
                        "nature": alt["nature"],
                        "spread": {
                            "hp_evs": alt["spread"]["hp"],
                            "def_evs": alt["spread"]["def"],
                            "spd_evs": alt["spread"]["spd"],
                            "spe_evs": alt["speed_evs"]
                        },
                        "total_evs": alt["total_evs"],
                        "ev_difference": f"+{alt['total_evs'] - optimal_multi['total_evs']} EVs vs optimal",
                        "explanation": explanation
                    })

                # Unpack optimal result
                nature_name = optimal_multi["nature"]
                speed_evs_needed = optimal_multi["speed_evs"]
                best_spread = optimal_multi["spread"]
                best_results = optimal_multi["results"]
                total_evs = optimal_multi["total_evs"]
                my_speed_stat = optimal_multi["my_speed_stat"]
                final_hp = optimal_multi["final_hp"]
                final_def = optimal_multi["final_def"]
                final_spd = optimal_multi["final_spd"]

                # Build optimized Pokemon for Showdown paste
                optimized_pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=my_base,
                    types=my_types,
                    nature=Nature(nature_name),
                    evs=EVSpread(
                        hp=best_spread["hp"],
                        defense=best_spread["def"],
                        special_defense=best_spread["spd"],
                        speed=speed_evs_needed
                    ),
                    tera_type=defender_tera_type
                )

                # Build threat survival analysis
                threat_analysis = []
                for i, (survives, result) in enumerate(best_results):
                    threat = prepared_threats[i]
                    survive_rolls = sum(1 for roll in result.rolls if roll < result.defender_hp)
                    survival_pct = (survive_rolls / 16) * 100

                    # Format attacker spread
                    atk_ev_str = f"{threat.evs}"
                    nature_boost = "+" if threat.nature.lower() in ("adamant", "jolly", "modest", "timid", "brave", "quiet") else ""
                    atk_spread = f"{threat.nature.title()} {atk_ev_str} {'Atk' if threat.is_physical else 'SpA'}"

                    threat_analysis.append({
                        "attacker": threat.attacker_name,
                        "move": threat.move.name,
                        "spread": atk_spread,
                        "item": threat.item,
                        "ability": threat.ability,
                        "tera_type": threat.tera_type,
                        "damage_range": result.damage_range,
                        "damage_percent": f"{format_percent(result.min_percent)}-{format_percent(result.max_percent)}%",
                        "survival_rate": f"{survival_pct:.2f}%",
                        "survives": survives
                    })

                return {
                    "success": True,
                    "optimal_spread": {
                        "hp_evs": best_spread["hp"],
                        "def_evs": best_spread["def"],
                        "spd_evs": best_spread["spd"],
                        "speed_evs": speed_evs_needed,
                        "nature": nature_name.title(),
                        "nature_auto_selected": nature_auto_selected,
                        "total_evs": total_evs,
                        "remaining_evs": 508 - total_evs,
                        "final_stats": {
                            "hp": final_hp,
                            "defense": final_def,
                            "special_defense": final_spd,
                            "speed": my_speed_stat
                        }
                    },
                    "threat_survival_analysis": threat_analysis,
                    "showdown_paste": pokemon_build_to_showdown(optimized_pokemon),
                    "alternative_natures": alternative_natures_multi,
                    "computation_stats": {
                        "threats_count": len(prepared_threats),
                        "time_ms": time_ms,
                        "cache_size": cache_stats["total_cached"]
                    }
                }

            else:
                # No solution found - report impossibility
                return {
                    "success": False,
                    "impossible": True,
                    "reason": "No EV spread can survive all threats simultaneously",
                    "threat_count": len(prepared_threats),
                    "suggestions": [
                        "Consider dropping one threat to make survival possible",
                        "Try a different Tera type to improve type matchups",
                        f"Reduce target survival rate (currently {target_survival}%)"
                    ],
                    "computation_stats": {
                        "threats_count": len(prepared_threats),
                        "time_ms": time_ms,
                        "cache_size": cache_stats["total_cached"]
                    }
                }

        except Exception as e:
            return {"error": str(e)}