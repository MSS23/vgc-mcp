"""MCP tools for Smogon-integrated speed analysis.

This module provides speed probability analysis using real Smogon usage data.
Complements speed_analysis_tools.py with live data integration.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.stats import calculate_speed
from vgc_mcp_core.models.pokemon import Nature


# Common VGC Pokemon with their base speeds and common speed investments
# Used as fallback when Smogon data is unavailable
META_SPEED_TIERS = {
    # Ultra fast (200+)
    "regieleki": {"base": 200, "common_speeds": [277, 252, 200]},

    # Very fast (135-150)
    "electrode-hisui": {"base": 150, "common_speeds": [222, 202]},
    "dragapult": {"base": 142, "common_speeds": [213, 194]},
    "iron-bundle": {"base": 136, "common_speeds": [205, 187, 136]},
    "flutter-mane": {"base": 135, "common_speeds": [205, 187, 157]},
    "miraidon": {"base": 135, "common_speeds": [205, 187]},
    "koraidon": {"base": 135, "common_speeds": [205, 187]},
    "meowscarada": {"base": 123, "common_speeds": [192, 175]},

    # Fast (100-120)
    "chien-pao": {"base": 135, "common_speeds": [205, 187]},
    "iron-moth": {"base": 110, "common_speeds": [178, 162]},
    "raging-bolt": {"base": 110, "common_speeds": [178, 162, 110]},
    "gouging-fire": {"base": 110, "common_speeds": [178, 162]},
    "walking-wake": {"base": 109, "common_speeds": [177, 161]},
    "entei": {"base": 100, "common_speeds": [167, 152, 157]},
    "urshifu": {"base": 97, "common_speeds": [163, 148]},
    "urshifu-rapid-strike": {"base": 97, "common_speeds": [163, 148]},
    "landorus": {"base": 101, "common_speeds": [168, 153]},
    "garchomp": {"base": 102, "common_speeds": [169, 154]},
    "arcanine": {"base": 95, "common_speeds": [161, 146, 95]},
    "arcanine-hisui": {"base": 90, "common_speeds": [156, 141, 90]},

    # Medium (70-95)
    "ogerpon": {"base": 110, "common_speeds": [178, 162]},
    "ogerpon-wellspring": {"base": 110, "common_speeds": [178, 162]},
    "ogerpon-hearthflame": {"base": 110, "common_speeds": [178, 162]},
    "ogerpon-cornerstone": {"base": 110, "common_speeds": [178, 162]},
    "kingambit": {"base": 50, "common_speeds": [70, 50]},
    "gholdengo": {"base": 84, "common_speeds": [150, 136]},
    "palafin": {"base": 100, "common_speeds": [167, 152]},
    "annihilape": {"base": 90, "common_speeds": [156, 142]},
    "dragonite": {"base": 80, "common_speeds": [145, 132, 80]},
    "gyarados": {"base": 81, "common_speeds": [146, 133]},
    "pelipper": {"base": 65, "common_speeds": [126, 85]},

    # Slow (50-70)
    "rillaboom": {"base": 85, "common_speeds": [150, 137, 85]},
    "incineroar": {"base": 60, "common_speeds": [123, 92, 60]},
    "amoonguss": {"base": 30, "common_speeds": [31, 30]},
    "porygon2": {"base": 60, "common_speeds": [92, 60]},
    "dondozo": {"base": 35, "common_speeds": [75, 35]},
    "torkoal": {"base": 20, "common_speeds": [40, 20]},

    # Very Slow / Trick Room (under 50)
    "iron-hands": {"base": 50, "common_speeds": [70, 50]},
    "ursaluna": {"base": 50, "common_speeds": [70, 50]},
    "ursaluna-bloodmoon": {"base": 52, "common_speeds": [73, 52]},
    "calyrex-ice": {"base": 50, "common_speeds": [70, 50, 36]},
    "calyrex-shadow": {"base": 150, "common_speeds": [222, 202]},
    "glimmora": {"base": 70, "common_speeds": [134, 122]},
    "hatterene": {"base": 29, "common_speeds": [49, 29]},
    "indeedee-f": {"base": 95, "common_speeds": [161, 146]},
    "farigiraf": {"base": 60, "common_speeds": [123, 60]},
    "kyogre": {"base": 90, "common_speeds": [156, 142]},
    "groudon": {"base": 90, "common_speeds": [156, 142]},
}


def register_speed_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register Smogon-integrated speed tools with the MCP server."""

    @mcp.tool()
    async def analyze_outspeed_probability(
        pokemon_name: str,
        target_pokemon: str,
        nature: str = "serious",
        speed_evs: int = 0,
        speed_stat: Optional[int] = None
    ) -> dict:
        """
        Analyze what percentage of a target Pokemon's common spreads you outspeed.
        Uses real Smogon usage data when available, falls back to hardcoded meta tiers.

        Args:
            pokemon_name: Your Pokemon's name
            target_pokemon: The target Pokemon to compare against
            nature: Your Pokemon's nature (ignored if speed_stat provided)
            speed_evs: Your Pokemon's Speed EVs (ignored if speed_stat provided)
            speed_stat: Your Pokemon's final Speed stat (overrides nature/EVs calculation)

        Returns:
            Analysis showing what percentage of target spreads you outspeed
        """
        try:
            # Get base stats for your Pokemon
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            # Calculate your speed - use speed_stat directly if provided
            if speed_stat is not None:
                your_speed = speed_stat
            else:
                your_speed = calculate_speed(base_stats.speed, 31, speed_evs, 50, parsed_nature)

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

            # Fallback 1: META_SPEED_TIERS (hardcoded)
            if not target_spreads:
                target_data = META_SPEED_TIERS.get(target_lower)
                if target_data:
                    common_speeds = target_data["common_speeds"]
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
                    target_spreads = [
                        {"speed": calculate_speed(target_base.speed, 31, 252, 50, Nature.JOLLY), "usage": 35},
                        {"speed": calculate_speed(target_base.speed, 31, 252, 50, Nature.SERIOUS), "usage": 25},
                        {"speed": calculate_speed(target_base.speed, 31, 0, 50, Nature.SERIOUS), "usage": 20},
                        {"speed": calculate_speed(target_base.speed, 31, 0, 50, Nature.BRAVE), "usage": 20},
                    ]
                    target_base_speed = target_base.speed
                    data_source = "calculated"
                except Exception:
                    return {"error": f"Could not find data for {target_pokemon}"}

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
                speed_source = f"At {your_speed} Speed ({nature}, {speed_evs} EVs):"

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
                "speed_evs": speed_evs if speed_stat is None else None,
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
            return {"error": str(e)}
