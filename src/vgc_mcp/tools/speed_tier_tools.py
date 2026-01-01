"""MCP tools for speed tier visualization."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from ..calc.stats import calculate_speed
from ..models.pokemon import Nature


# Common VGC Pokemon with their base speeds and common speed investments
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
    "arcanine-hisui": {"base": 95, "common_speeds": [161, 146, 95]},

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


def register_speed_tier_tools(mcp: FastMCP, pokeapi):
    """Register speed tier visualization tools."""

    @mcp.tool()
    async def visualize_speed_tiers(
        pokemon_speeds: list[dict],
        include_tailwind: bool = False,
        include_trick_room: bool = False,
        compare_to_meta: bool = True
    ) -> dict:
        """
        Visualize speed tiers as a text-based chart.

        Args:
            pokemon_speeds: List of dicts with 'name' and 'speed' keys
                           e.g., [{"name": "Entei", "speed": 157}, {"name": "Flutter Mane", "speed": 205}]
            include_tailwind: Show doubled speeds
            include_trick_room: Show order reversed (slowest first)
            compare_to_meta: Include common meta Pokemon for reference

        Returns:
            Text-based speed tier visualization
        """
        all_pokemon = []

        # Add user's Pokemon
        for p in pokemon_speeds:
            all_pokemon.append({
                "name": p["name"],
                "speed": p["speed"],
                "is_yours": True,
                "tailwind_speed": p["speed"] * 2 if include_tailwind else None
            })

        # Add meta Pokemon for reference
        if compare_to_meta:
            for mon, data in META_SPEED_TIERS.items():
                for speed in data["common_speeds"][:2]:  # Top 2 common speeds
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
                lines.append(f"Your fastest outspeeds: {', '.join(set(outspeeds)[:5])}")
            if underspeeds:
                lines.append(f"Faster than your slowest: {', '.join(set(underspeeds)[:5])}")

        return {
            "visualization": "\n".join(lines),
            "your_pokemon": your_pokemon,
            "mode": mode
        }

    @mcp.tool()
    async def get_meta_speed_tiers(
        format_type: str = "general",
        tier: Optional[str] = None
    ) -> dict:
        """
        Get common speed tiers in the current VGC metagame.

        Args:
            format_type: "general", "trick_room", or "tailwind"
            tier: Optional filter - "fast", "medium", "slow"

        Returns:
            Speed tier information for meta Pokemon
        """
        result = []

        for mon, data in META_SPEED_TIERS.items():
            base = data["base"]
            speeds = data["common_speeds"]

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

    @mcp.tool()
    async def find_speed_benchmark(
        target_speed: int,
        nature: str = "jolly",
        pokemon_name: Optional[str] = None
    ) -> dict:
        """
        Find what Pokemon/spreads hit a specific speed stat.

        Args:
            target_speed: The speed stat to analyze
            nature: Nature to assume for calculations
            pokemon_name: Optional - find EVs needed for this Pokemon to hit target

        Returns:
            Analysis of what Pokemon hit this speed tier
        """
        results = {
            "target_speed": target_speed,
            "pokemon_at_this_speed": [],
            "pokemon_above": [],
            "pokemon_below": []
        }

        try:
            nature_enum = Nature(nature.lower())
        except ValueError:
            nature_enum = Nature.JOLLY

        # If specific Pokemon requested, calculate EVs needed
        if pokemon_name:
            try:
                data = await pokeapi.get_pokemon(pokemon_name)
                base_speed = data["base_stats"]["speed"]

                from ..config import EV_BREAKPOINTS_LV50

                evs_needed = None
                for ev in EV_BREAKPOINTS_LV50:
                    speed = calculate_speed(base_speed, 31, ev, 50, nature_enum)
                    if speed >= target_speed:
                        evs_needed = ev
                        break

                results["your_pokemon"] = {
                    "name": pokemon_name,
                    "base_speed": base_speed,
                    "evs_needed": evs_needed,
                    "resulting_speed": calculate_speed(base_speed, 31, evs_needed or 252, 50, nature_enum) if evs_needed else None,
                    "can_reach": evs_needed is not None
                }
            except Exception as e:
                results["your_pokemon"] = {"error": str(e)}

        # Check meta Pokemon
        for mon, data in META_SPEED_TIERS.items():
            max_speed = calculate_speed(data["base"], 31, 252, 50, Nature.JOLLY)
            neutral_max = calculate_speed(data["base"], 31, 252, 50, Nature.HARDY)
            no_invest = calculate_speed(data["base"], 31, 0, 50, Nature.HARDY)

            if max_speed == target_speed or neutral_max == target_speed:
                results["pokemon_at_this_speed"].append({
                    "pokemon": mon,
                    "base": data["base"],
                    "investment": "252 EVs" + (" +Speed" if max_speed == target_speed else " neutral")
                })
            elif max_speed > target_speed:
                results["pokemon_above"].append({
                    "pokemon": mon,
                    "max_speed": max_speed
                })
            else:
                results["pokemon_below"].append({
                    "pokemon": mon,
                    "max_speed": max_speed
                })

        # Sort
        results["pokemon_above"].sort(key=lambda x: x["max_speed"])
        results["pokemon_below"].sort(key=lambda x: -x["max_speed"])

        # Trim to top 10
        results["pokemon_above"] = results["pokemon_above"][:10]
        results["pokemon_below"] = results["pokemon_below"][:10]

        return results
