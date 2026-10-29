"""Speed tool handlers shared by canonical tools and their deprecated aliases."""

import logging
from typing import Any, Optional

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.speed import (
    META_SPEED_TIERS,
    SPEED_BENCHMARKS,
    get_competitive_speed_benchmarks,
)
from vgc_mcp_core.calc.stats import calculate_speed
from vgc_mcp_core.calc.stats_champions import calculate_speed_sp
from vgc_mcp_core.formats.showdown import format_showdown_species
from vgc_mcp_core.models.pokemon import Nature
from vgc_mcp_core.rules.format_detect import detect_champions_format
from vgc_mcp_core.tools.build_helpers import parse_ev_dict, parse_ev_string
from vgc_mcp_core.tools.response_contract import apply_contract, data_source_from_meta
from vgc_mcp_core.utils.errors import ErrorCodes, error_response

logger = logging.getLogger(__name__)


def speed_label(name: str, nature: Optional[str], invest: Optional[int], champions: bool) -> str:
    """spread_label-style line for a Speed-only investment: 'Jolly 0/0/0/0/0/252 Garchomp'."""
    species = format_showdown_species(name)
    if nature is None or invest is None:
        return species
    unit = " SP" if champions else ""
    return f"{str(nature).title()} 0/0/0/0/0/{invest}{unit} {species}"


async def outspeed_contract(result: dict[str, Any], smogon: Optional[SmogonStatsClient]) -> dict[str, Any]:
    """Response contract for `analyze_outspeed_probability`.

    The pre-contract string in ``data_source`` ('smogon', 'meta_tiers',
    'calculated', 'fallback') moves to ``speed_data_source``; ``data_source``
    becomes the chaos provenance when Smogon spreads were used.
    """
    if "error" in result:
        return result
    kind = result.pop("data_source", None)
    result["speed_data_source"] = kind
    meta = None
    if kind == "smogon" and smogon is not None:
        try:
            usage = await smogon.get_pokemon_usage(result["target_pokemon"])
            meta = usage.get("_meta") if isinstance(usage, dict) else None
        except Exception:  # noqa: BLE001 - provenance is best effort
            meta = None
    champions = result.get("format_system") == "champions"
    invest = result.get("speed_sps" if champions else "speed_evs")
    if result.get("speed_stat") is not None:
        mine = f"{result['your_speed']} Spe {format_showdown_species(result['pokemon'])}"
    else:
        mine = speed_label(result["pokemon"], result.get("nature"), invest, champions)
    return apply_contract(
        result,
        headline=(
            f"{format_showdown_species(result['pokemon'])} at {result['your_speed']} Speed outspeeds "
            f"{result['outspeed_percent']}% of {format_showdown_species(result['target_pokemon'])} "
            f"spreads (tie {result['tie_percent']}%)"
        ),
        spreads_used={"pokemon": mine},
        data_source=data_source_from_meta(meta),
    )


def speed_evs_contract(result: dict[str, Any], nature: str) -> dict[str, Any]:
    """Response contract for `find_speed_evs_to_outspeed`."""
    if "error" in result:
        return result
    champions = result.get("format_system") == "champions"
    unit = "SP" if champions else "EVs"
    name = result["pokemon"]
    species = format_showdown_species(name)
    if result.get("achievable"):
        invest = result["sps_needed" if champions else "evs_needed"]
        headline = (
            f"{species} needs {invest} Speed {unit} ({str(nature).title()}) to reach "
            f"{result['actual_speed']} Speed (target {result['target_speed']})"
        )
    else:
        invest = 32 if champions else 252
        best = result.get("max_speed_with_32_sps" if champions else "max_speed_with_252_evs")
        headline = (
            f"No, {species} can't reach {result['target_speed']} Speed with "
            f"{str(nature).title()}; max is {best}"
        )
    return apply_contract(
        result,
        headline=headline,
        spreads_used={"pokemon": speed_label(name, nature, invest, champions)},
    )


def speed_investment(value: int | str) -> int:
    """Speed EVs (or SPs) from an int or the Spe slot of an 'HP/Atk/Def/SpA/SpD/Spe' string."""
    if isinstance(value, int):
        return value
    speed = int(value) if value.strip().isdigit() else parse_ev_string(value)["speed"]
    if not 0 <= speed <= 252:
        raise ValueError(f"Speed investment must be 0-252, got {speed}")
    return speed


async def analyze_outspeed_probability(
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    *,
    pokemon_name: str,
    target_pokemon: str,
    nature: str = "serious",
    speed_evs: int | str = 0,
    speed_stat: Optional[int] = None,
) -> dict[str, Any]:
    """Share of a target's common spreads that a given Speed outspeeds."""
    try:
        speed_evs = speed_investment(speed_evs)
    except ValueError as ve:
        return error_response(ErrorCodes.INVALID_PARAMETER, f"speed_evs: {ve}")
    try:
        is_champions = detect_champions_format(pokemon_name)
        speed_calc = calculate_speed_sp if is_champions else calculate_speed
        if is_champions and speed_stat is None and speed_evs > 32:
            return error_response(ErrorCodes.INVALID_PARAMETER, "Speed Stat Points must be between 0 and 32")
        # Get base stats for your Pokemon
        base_stats = await pokeapi.get_base_stats(pokemon_name)

        try:
            parsed_nature = Nature(nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

        # Calculate your speed - use speed_stat directly if provided
        if speed_stat is not None:
            your_speed = speed_stat
        else:
            your_speed = speed_calc(base_stats.speed, 31, speed_evs, 50, parsed_nature)

        # Normalize target name
        target_lower = target_pokemon.lower().replace(" ", "-")
        if target_lower.endswith("-mask"):
            target_lower = target_lower.replace("-mask", "")

        target_spreads = None
        target_base_speed = None
        target_stats = None
        data_source = "fallback"

        # Try Smogon data first (using get_speed_distribution)
        if smogon:
            try:
                target_base = await pokeapi.get_base_stats(target_pokemon)
                speed_dist = await smogon.get_speed_distribution(
                    target_pokemon,
                    target_base.speed
                )
                if speed_dist and speed_dist.get("distribution"):
                    target_spreads = speed_dist["distribution"]
                    target_base_speed = speed_dist["base_speed"]
                    target_stats = speed_dist.get("stats", {})
                    data_source = "smogon"
            except Exception:
                pass  # Fall through to fallbacks

        # Fallback 1: META_SPEED_TIERS (calculated dynamically from spreads)
        if not target_spreads and not is_champions:
            from vgc_mcp_core.calc.speed import get_meta_speed_tier
            target_data = get_meta_speed_tier(target_pokemon)
            if target_data:
                # Calculate speeds dynamically from spreads if available
                common_speeds = target_data.get("common_speeds", [])
                if not common_speeds and "spreads" in target_data:
                    # Calculate from spreads (use module-level calculate_speed)
                    NATURE_MAP = {
                        "adamant": Nature.ADAMANT, "bashful": Nature.BASHFUL, "bold": Nature.BOLD,
                        "brave": Nature.BRAVE, "calm": Nature.CALM, "careful": Nature.CAREFUL,
                        "docile": Nature.DOCILE, "gentle": Nature.GENTLE, "hardy": Nature.HARDY,
                        "hasty": Nature.HASTY, "impish": Nature.IMPISH, "jolly": Nature.JOLLY,
                        "lax": Nature.LAX, "lonely": Nature.LONELY, "mild": Nature.MILD,
                        "modest": Nature.MODEST, "naive": Nature.NAIVE, "naughty": Nature.NAUGHTY,
                        "quiet": Nature.QUIET, "quirky": Nature.QUIRKY, "rash": Nature.RASH,
                        "relaxed": Nature.RELAXED, "sassy": Nature.SASSY, "serious": Nature.SERIOUS,
                        "timid": Nature.TIMID,
                    }
                    base = target_data["base"]
                    speed_set = set()
                    for spread in target_data["spreads"]:
                        nature_str = spread.get("nature", "Serious").lower()
                        # Distinct names: these must not clobber the caller's
                        # nature / speed_evs, which the response echoes back.
                        spread_evs = spread.get("evs", 0)
                        spread_nature = NATURE_MAP.get(nature_str, Nature.SERIOUS)
                        speed = calculate_speed(base, 31, spread_evs, 50, spread_nature)
                        if speed not in speed_set:
                            speed_set.add(speed)
                            common_speeds.append(speed)
                    common_speeds.sort(reverse=True)

                usage_per = 100 // len(common_speeds) if common_speeds else 100
                target_spreads = [
                    {"speed": s, "usage": usage_per}
                    for s in common_speeds
                ]
                target_base_speed = target_data["base"]
                data_source = "meta_tiers"

        # Fallback 2: Calculate standard spreads from base stats
        if not target_spreads:
            try:
                target_base = await pokeapi.get_base_stats(target_pokemon)
                max_investment = 32 if is_champions else 252
                target_spreads = [
                    {"speed": speed_calc(target_base.speed, 31, max_investment, 50, Nature.JOLLY), "usage": 35},
                    {"speed": speed_calc(target_base.speed, 31, max_investment, 50, Nature.SERIOUS), "usage": 25},
                    {"speed": speed_calc(target_base.speed, 31, 0, 50, Nature.SERIOUS), "usage": 20},
                    {"speed": speed_calc(target_base.speed, 31, 0, 50, Nature.BRAVE), "usage": 20},
                ]
                target_base_speed = target_base.speed
                data_source = "calculated"
            except Exception:
                return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Could not find data for {target_pokemon}')

        # Calculate outspeed percentage with interpolation for speeds between known tiers
        total_usage = sum(s["usage"] for s in target_spreads)
        sorted_by_speed = sorted(target_spreads, key=lambda s: s["speed"])
        speeds = [s["speed"] for s in sorted_by_speed]

        # Base calculation: speeds we definitively outspeed or tie
        outsped_usage = sum(
            s["usage"] for s in target_spreads
            if your_speed > s["speed"]
        )
        tied_usage = sum(
            s["usage"] for s in target_spreads
            if your_speed == s["speed"]
        )

        # Interpolation: if user speed is between two known tiers, estimate partial credit
        interpolation_bonus = 0.0
        if your_speed not in speeds and len(speeds) >= 2:
            lower_tier = None
            upper_tier = None
            for i, spd in enumerate(speeds):
                if spd > your_speed:
                    upper_tier = sorted_by_speed[i]
                    if i > 0:
                        lower_tier = sorted_by_speed[i - 1]
                    break

            if lower_tier and upper_tier:
                lower_speed = lower_tier["speed"]
                upper_speed = upper_tier["speed"]
                upper_usage = upper_tier["usage"]
                gap_progress = (your_speed - lower_speed) / (upper_speed - lower_speed)
                interpolation_bonus = upper_usage * gap_progress * 0.5

        outsped_usage += interpolation_bonus
        outspeed_percent = (outsped_usage / total_usage * 100) if total_usage > 0 else 0
        tie_percent = (tied_usage / total_usage * 100) if total_usage > 0 else 0
        outsped_by_percent = round(100 - outspeed_percent - tie_percent, 1)

        used_interpolation = interpolation_bonus > 0

        # Determine result description
        if outspeed_percent >= 100:
            result_text = f"{pokemon_name} outspeeds all common {target_pokemon} spreads"
        elif outspeed_percent > 50:
            result_text = f"{pokemon_name} outspeeds most common {target_pokemon} spreads"
        elif outspeed_percent > 0:
            result_text = f"{pokemon_name} outspeeds some common {target_pokemon} spreads"
        else:
            result_text = f"{pokemon_name} is outsped by all common {target_pokemon} spreads"

        # Build compact summary with full breakdown
        if speed_stat is not None:
            speed_source = f"At {your_speed} Speed:"
        else:
            unit = "SPs" if is_champions else "EVs"
            speed_source = f"At {your_speed} Speed ({nature}, {speed_evs} {unit}):"

        disclaimer = "(Estimated from Smogon usage data)"

        summary_lines = [
            speed_source,
            f"You outspeed: {round(outspeed_percent, 1)}% | Tie: {round(tie_percent, 1)}% | They outspeed you: {outsped_by_percent}%",
            disclaimer,
            "",
            "Speed Tier Breakdown:",
        ]
        # Sort spreads by speed for cleaner display
        sorted_spreads = sorted(target_spreads, key=lambda s: s["speed"])
        # Normalize percentages so they add up to 100%
        raw_total = sum(s["usage"] for s in sorted_spreads)
        for spread in sorted_spreads:
            speed = spread["speed"]
            raw_usage = spread["usage"]
            # Normalize to 100% of known spreads
            normalized_usage = (raw_usage / raw_total * 100) if raw_total > 0 else 0
            if your_speed > speed:
                result_label = "faster"
            elif your_speed == speed:
                result_label = "tie"
            else:
                result_label = "slower"
            summary_lines.append(f"{speed} Spe ({normalized_usage:.1f}%) - {result_label}")

        analysis_str = f"{pokemon_name} at {your_speed} Speed: You outspeed {round(outspeed_percent, 1)}% | Tie {round(tie_percent, 1)}% | They outspeed you {outsped_by_percent}% {disclaimer}"

        return {
            "pokemon": pokemon_name,
            "your_speed": your_speed,
            "nature": nature if speed_stat is None else None,
            "speed_sps" if is_champions else "speed_evs": speed_evs if speed_stat is None else None,
            **({"format_system": "champions"} if is_champions else {}),
            "speed_stat": speed_stat,
            "target_pokemon": target_pokemon,
            "target_base_speed": target_base_speed,
            "target_spreads": target_spreads,
            "target_stats": target_stats,
            "outspeed_percent": round(outspeed_percent, 1),
            "tie_percent": round(tie_percent, 1),
            "outsped_by_percent": outsped_by_percent,
            "used_interpolation": used_interpolation,
            "result": result_text,
            "data_source": data_source,
            "summary_table": "\n".join(summary_lines),
            "analysis": analysis_str
        }

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


def benchmark_speed_tiers(min_base_speed: int, max_base_speed: int, investment: str) -> dict[str, Any]:
    """Fixed-benchmark speed tiers at one investment level, fastest first."""
    try:
        tiers = []

        for mon_name, data in SPEED_BENCHMARKS.items():
            base = data.get("base", 0)

            if not (min_base_speed <= base <= max_base_speed):
                continue

            if investment == "max":
                speed = data.get("max_positive", calculate_speed(base, 31, 252, 50, Nature.JOLLY))
                config = "+Speed nature, 252 EVs, 31 IV"
            elif investment == "neutral":
                speed = data.get("max_neutral", calculate_speed(base, 31, 252, 50, Nature.SERIOUS))
                config = "Neutral nature, 252 EVs, 31 IV"
            elif investment == "min":
                speed = data.get("min_negative", calculate_speed(base, 0, 0, 50, Nature.BRAVE))
                config = "-Speed nature, 0 EVs, 0 IV"
            else:
                speed = data.get("neutral_0ev", calculate_speed(base, 31, 0, 50, Nature.SERIOUS))
                config = "Neutral nature, 0 EVs, 31 IV"

            tiers.append({
                "pokemon": mon_name.replace("-", " ").title(),
                "base_speed": base,
                "final_speed": speed,
                "config": config
            })

        # Sort by final speed descending
        tiers.sort(key=lambda x: x["final_speed"], reverse=True)

        return {
            "investment": investment,
            "speed_tiers": tiers
        }

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def meta_speed_tiers(
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    *,
    format_type: str = "general",
    tier: Optional[str] = None,
    use_competitive_data: bool = True,
    min_base_speed: int = 0,
    max_base_speed: int = 999,
) -> dict[str, Any]:
    """Current-meta speed tiers from Smogon spreads (theoretical fallback)."""
    result = []

    if use_competitive_data:
        # Fetch competitive speed benchmarks from Smogon
        try:
            competitive_benchmarks = await get_competitive_speed_benchmarks(
                smogon,
                top_n_pokemon=30,
                top_n_speeds=3
            )

            for mon_name, speeds in competitive_benchmarks.items():
                if not speeds:
                    continue

                # Get base speed for categorization
                base = SPEED_BENCHMARKS.get(mon_name, {}).get("base", 0)
                if base == 0:
                    # Try to fetch from PokeAPI if not in benchmarks
                    try:
                        base_stats = await pokeapi.get_base_stats(mon_name)
                        base = base_stats.speed
                    except Exception:
                        continue

                entry = {
                    "pokemon": mon_name,
                    "base_speed": base,
                    "competitive_speeds": speeds,  # List of dicts with speed, nature, evs, usage
                    "max_speed_positive": calculate_speed(base, 31, 252, 50, Nature.JOLLY),
                    "max_speed_neutral": calculate_speed(base, 31, 252, 50, Nature.HARDY),
                    "min_speed": calculate_speed(base, 0, 0, 50, Nature.BRAVE),
                }

                # Categorize
                if base >= 120:
                    entry["tier"] = "fast"
                elif base >= 80:
                    entry["tier"] = "medium"
                else:
                    entry["tier"] = "slow"

                # Filter by tier if specified
                if tier and entry["tier"] != tier.lower():
                    continue
                if not (min_base_speed <= base <= max_base_speed):
                    continue

                result.append(entry)

        except Exception:
            # Fallback to META_SPEED_TIERS if Smogon fetch fails
            use_competitive_data = False

    if not use_competitive_data:
        # Fallback to theoretical speeds from META_SPEED_TIERS
        from vgc_mcp_core.calc.speed import get_meta_speed_tier

        for mon in META_SPEED_TIERS.keys():
            data = get_meta_speed_tier(mon)
            if not data:
                continue
            base = data["base"]
            speeds = data.get("common_speeds", [])

            entry = {
                "pokemon": mon,
                "base_speed": base,
                "common_speeds": speeds,
                "max_speed_positive": calculate_speed(base, 31, 252, 50, Nature.JOLLY),
                "max_speed_neutral": calculate_speed(base, 31, 252, 50, Nature.HARDY),
                "min_speed": calculate_speed(base, 0, 0, 50, Nature.BRAVE),
            }

            # Categorize
            if base >= 120:
                entry["tier"] = "fast"
            elif base >= 80:
                entry["tier"] = "medium"
            else:
                entry["tier"] = "slow"

            # Filter by tier if specified
            if tier and entry["tier"] != tier.lower():
                continue
            if not (min_base_speed <= base <= max_base_speed):
                continue

            result.append(entry)

    # Sort by base speed
    result.sort(key=lambda x: -x["base_speed"])

    # Add tailwind/TR info if requested
    if format_type == "tailwind":
        for entry in result:
            entry["tailwind_max"] = entry["max_speed_positive"] * 2
    elif format_type == "trick_room":
        result.sort(key=lambda x: x["base_speed"])  # Reverse order

    return {
        "format": format_type,
        "tier_filter": tier,
        "pokemon_count": len(result),
        "speed_tiers": result
    }


async def speed_tiers(
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    *,
    min_base_speed: int = 50,
    max_base_speed: int = 200,
    investment: str = "max",
    format_type: str = "general",
) -> dict[str, Any]:
    """`get_speed_tiers`: fixed benchmarks, or the live meta when investment='meta'."""
    if investment == "meta":
        result = await meta_speed_tiers(
            pokeapi, smogon, format_type=format_type,
            min_base_speed=min_base_speed, max_base_speed=max_base_speed,
        )
        return {"investment": "meta", **result}
    result = benchmark_speed_tiers(min_base_speed, max_base_speed, investment)
    if "speed_tiers" in result and format_type == "trick_room":
        result["speed_tiers"].sort(key=lambda x: x["final_speed"])
    elif "speed_tiers" in result and format_type == "tailwind":
        for entry in result["speed_tiers"]:
            entry["tailwind_speed"] = entry["final_speed"] * 2
    if format_type != "general":
        result["format"] = format_type
    return result


async def _speed_from_spread(pokeapi: PokeAPIClient, entry: dict[str, Any]) -> int:
    """Final Speed for a chart entry from 'nature' + 'evs' (dict, slash string or int)."""
    base = await pokeapi.get_base_stats(entry["name"])
    nature = Nature(str(entry.get("nature") or "serious").lower())
    evs = entry.get("evs") or {}
    if isinstance(evs, str):
        speed_evs = parse_ev_string(evs)["speed"]
    elif isinstance(evs, int):
        speed_evs = evs
    else:
        speed_evs = parse_ev_dict(evs).speed
    return calculate_speed(base.speed, 31, speed_evs, 50, nature)


async def visualize_speed_tiers(
    pokeapi: PokeAPIClient,
    *,
    pokemon_speeds: list[dict[str, Any]],
    include_tailwind: bool = False,
    include_trick_room: bool = False,
    compare_to_meta: bool = True,
) -> dict[str, Any]:
    """Text speed-tier chart; entries give 'speed' or 'nature' + 'evs'."""
    all_pokemon = []

    # Add user's Pokemon
    for p in pokemon_speeds:
        try:
            speed = p["speed"] if "speed" in p else await _speed_from_spread(pokeapi, p)
        except Exception as e:  # noqa: BLE001 - skip one bad entry, chart the rest
            logger.warning("Skipping %s in speed chart: %s", p.get("name"), e)
            continue
        all_pokemon.append({
            "name": p["name"],
            "speed": speed,
            "is_yours": True,
            "tailwind_speed": speed * 2 if include_tailwind else None
        })

    # Add meta Pokemon for reference
    if compare_to_meta:
        from vgc_mcp_core.calc.speed import get_meta_speed_tier
        for mon in META_SPEED_TIERS.keys():
            data = get_meta_speed_tier(mon)
            if data:
                common_speeds = data.get("common_speeds", [])
                for speed in common_speeds[:2]:  # Top 2 common speeds
                    all_pokemon.append({
                        "name": mon,
                        "speed": speed,
                        "is_yours": False,
                        "base_speed": data["base"],
                        "tailwind_speed": speed * 2 if include_tailwind else None
                    })

    # Sort by speed (descending for normal, ascending for TR)
    if include_trick_room:
        all_pokemon.sort(key=lambda x: x["speed"])
    else:
        all_pokemon.sort(key=lambda x: -x["speed"])

    # Build visualization
    lines = []
    mode = "Trick Room" if include_trick_room else "Normal"
    lines.append(f"=== SPEED TIERS ({mode}) ===")
    if include_tailwind:
        lines.append("(TW = speed under Tailwind, 2x)")
    lines.append("")

    current_tier = None
    for p in all_pokemon:
        speed = p["speed"]

        # Determine tier
        if speed >= 200:
            tier = "ULTRA FAST"
        elif speed >= 150:
            tier = "VERY FAST"
        elif speed >= 120:
            tier = "FAST"
        elif speed >= 90:
            tier = "MEDIUM"
        elif speed >= 60:
            tier = "SLOW"
        else:
            tier = "VERY SLOW"

        if tier != current_tier:
            lines.append(f"--- {tier} ---")
            current_tier = tier

        marker = ">>>" if p["is_yours"] else "   "
        tw_info = f" (TW: {p['tailwind_speed']})" if p.get("tailwind_speed") else ""
        lines.append(f"{marker} {speed:3d} | {p['name']}{tw_info}")

    # Summary
    your_pokemon = [p for p in all_pokemon if p["is_yours"]]
    if your_pokemon:
        lines.append("")
        lines.append("=== YOUR TEAM SUMMARY ===")
        fastest = max(your_pokemon, key=lambda x: x["speed"])
        slowest = min(your_pokemon, key=lambda x: x["speed"])
        lines.append(f"Fastest: {fastest['name']} ({fastest['speed']})")
        lines.append(f"Slowest: {slowest['name']} ({slowest['speed']})")

        # What you outspeed/underspeed
        outspeeds = []
        underspeeds = []
        for p in all_pokemon:
            if not p["is_yours"]:
                if fastest["speed"] > p["speed"]:
                    outspeeds.append(p["name"])
                elif slowest["speed"] < p["speed"]:
                    underspeeds.append(p["name"])

        if outspeeds:
            lines.append(f"Your fastest outspeeds: {', '.join(list(set(outspeeds))[:5])}")
        if underspeeds:
            lines.append(f"Faster than your slowest: {', '.join(list(set(underspeeds))[:5])}")

    result = {
        "visualization": "\n".join(lines),
        "your_pokemon": your_pokemon,
        "all_pokemon": all_pokemon,
        "mode": mode
    }

    return result
