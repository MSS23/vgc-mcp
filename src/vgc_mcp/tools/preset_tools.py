"""MCP tools for EV spread presets - pulls LIVE data from Smogon Chaos."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from ..data.spread_presets import (
    get_presets_for_pokemon,
    get_preset_by_name,
    get_all_pokemon_with_presets,
    SpreadPreset,
)


def register_preset_tools(mcp: FastMCP, smogon=None):
    """Register spread preset tools with the MCP server."""

    @mcp.tool()
    async def get_smogon_spreads(
        pokemon_name: str,
        limit: int = 5,
        format_name: Optional[str] = None
    ) -> dict:
        """
        Get the most popular EV spreads from LIVE Smogon Chaos data.

        This fetches real-time usage data from Smogon's latest stats,
        showing what spreads top players are actually using right now.

        Args:
            pokemon_name: Pokemon name (e.g., "Incineroar", "Flutter Mane")
            limit: Number of top spreads to return (default 5)
            format_name: Optional format override (auto-detects current VGC format)

        Returns:
            Top spreads with usage %, nature, EVs, and metadata about the data source
        """
        if smogon is None:
            return {"error": "Smogon client not available"}

        try:
            data = await smogon.get_pokemon_usage(pokemon_name, format_name)
            if not data:
                return {
                    "error": f"No Smogon data found for {pokemon_name}",
                    "suggestion": "Check the Pokemon name spelling"
                }

            spreads = data.get("spreads", [])[:limit]
            meta = data.get("_meta", {})

            return {
                "pokemon": data.get("name", pokemon_name),
                "usage_percent": data.get("usage_percent", 0),
                "data_source": {
                    "source": "Smogon Chaos Stats",
                    "format": meta.get("format", "unknown"),
                    "month": meta.get("month", "unknown"),
                    "rating": meta.get("rating", 1760)
                },
                "spread_count": len(spreads),
                "spreads": [
                    {
                        "rank": i + 1,
                        "nature": s.get("nature", "Unknown"),
                        "evs": s.get("evs", {}),
                        "spread_string": s.get("spread_string", ""),
                        "usage_percent": s.get("usage", 0)
                    }
                    for i, s in enumerate(spreads)
                ],
                "top_items": list(data.get("items", {}).items())[:3],
                "top_abilities": list(data.get("abilities", {}).items())[:2],
                "top_tera_types": list(data.get("tera_types", {}).items())[:3]
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_spread_presets(
        pokemon_name: str,
        preset_name: Optional[str] = None
    ) -> dict:
        """
        Get curated EV spread presets with benchmark explanations.

        These are manually curated spreads with explanations of what
        benchmarks they hit. For LIVE usage data, use get_smogon_spreads instead.

        Args:
            pokemon_name: Pokemon name (e.g., "Incineroar", "Flutter Mane")
            preset_name: Optional specific preset to get (e.g., "Bulky Pivot")

        Returns:
            List of preset spreads with EVs, nature, item, and benchmark info
        """
        if preset_name:
            preset = get_preset_by_name(pokemon_name, preset_name)
            if not preset:
                available = get_presets_for_pokemon(pokemon_name)
                preset_names = [p.name for p in available] if available else []
                return {
                    "error": f"Preset '{preset_name}' not found for {pokemon_name}",
                    "available_presets": preset_names,
                    "suggestion": "Use get_smogon_spreads for live data from Smogon"
                }
            return _format_preset(preset)

        presets = get_presets_for_pokemon(pokemon_name)
        if not presets:
            return {
                "error": f"No curated presets for {pokemon_name}",
                "suggestion": "Use get_smogon_spreads(pokemon_name) for live Smogon data instead"
            }

        return {
            "pokemon": pokemon_name,
            "preset_count": len(presets),
            "presets": [_format_preset(p) for p in presets],
            "note": "For live usage data, use get_smogon_spreads instead"
        }

    @mcp.tool()
    async def list_pokemon_with_presets() -> dict:
        """
        List all Pokemon that have curated preset spreads available.

        Returns:
            List of Pokemon names with curated spreads
        """
        pokemon_list = get_all_pokemon_with_presets()
        return {
            "count": len(pokemon_list),
            "pokemon": sorted(set(pokemon_list)),
            "usage": "Use get_spread_presets(pokemon_name) for curated spreads with benchmarks",
            "alternative": "Use get_smogon_spreads(pokemon_name) for ANY Pokemon with live Smogon data"
        }

    @mcp.tool()
    async def suggest_spread_for_role(
        pokemon_name: str,
        role: str
    ) -> dict:
        """
        Suggest a spread preset based on the role you want the Pokemon to fill.

        Args:
            pokemon_name: Pokemon name
            role: Role description (e.g., "bulky", "fast", "support", "sweeper", "trick room")

        Returns:
            Recommended preset(s) matching the role
        """
        presets = get_presets_for_pokemon(pokemon_name)
        if not presets:
            return {
                "error": f"No curated presets for {pokemon_name}",
                "suggestion": "Use get_smogon_spreads(pokemon_name) for live Smogon data"
            }

        role_lower = role.lower()
        matches = []

        # Match based on keywords in name, context, and benchmarks
        role_keywords = {
            "bulky": ["bulky", "tank", "defensive", "vest", "sitrus"],
            "fast": ["fast", "speed", "max speed", "jolly", "timid"],
            "support": ["support", "pivot", "tailwind", "fake out", "redirect"],
            "sweeper": ["attacker", "sweeper", "specs", "band", "nuke"],
            "trick room": ["trick room", "tr", "minimum speed", "brave", "quiet", "0 speed"],
            "offensive": ["attacker", "offensive", "specs", "band", "orb"],
            "defensive": ["defensive", "bulk", "vest", "berry"],
        }

        # Find which role category matches
        matched_keywords = []
        for category, keywords in role_keywords.items():
            if any(kw in role_lower for kw in keywords):
                matched_keywords.extend(keywords)

        if not matched_keywords:
            matched_keywords = [role_lower]

        for preset in presets:
            score = 0
            searchable = (
                preset.name.lower() +
                preset.usage_context.lower() +
                " ".join(b.lower() for b in preset.benchmarks)
            )

            for keyword in matched_keywords:
                if keyword in searchable:
                    score += 1

            if score > 0:
                matches.append((preset, score))

        matches.sort(key=lambda x: -x[1])

        if not matches:
            return {
                "pokemon": pokemon_name,
                "role": role,
                "message": f"No presets match '{role}' well",
                "all_presets": [_format_preset(p) for p in presets],
                "suggestion": "Review all presets above to find what you need"
            }

        return {
            "pokemon": pokemon_name,
            "role": role,
            "recommended": _format_preset(matches[0][0]),
            "alternatives": [_format_preset(m[0]) for m in matches[1:3]] if len(matches) > 1 else []
        }


def _format_preset(preset: SpreadPreset) -> dict:
    """Format a preset for output."""
    ev_string = "/".join([
        str(preset.evs.get("hp", 0)),
        str(preset.evs.get("attack", 0)),
        str(preset.evs.get("defense", 0)),
        str(preset.evs.get("special_attack", 0)),
        str(preset.evs.get("special_defense", 0)),
        str(preset.evs.get("speed", 0)),
    ])

    result = {
        "name": preset.name,
        "pokemon": preset.pokemon,
        "nature": preset.nature,
        "evs": preset.evs,
        "ev_string": f"{preset.nature.title()}: {ev_string}",
        "benchmarks": preset.benchmarks,
        "usage_context": preset.usage_context,
    }

    if preset.item:
        result["item"] = preset.item
    if preset.ability:
        result["ability"] = preset.ability
    if preset.tera_type:
        result["tera_type"] = preset.tera_type
    if preset.source:
        result["source"] = preset.source

    return result
