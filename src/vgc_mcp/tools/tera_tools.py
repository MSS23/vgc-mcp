"""MCP tools for Tera type optimization."""

from typing import Annotated, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.config import logger
from vgc_mcp_core.models.pokemon import EVSpread, Nature, PokemonBuild, StatPointSpread
from vgc_mcp_core.utils.errors import api_error, pokemon_not_found_error
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name


def _detect_champions(pokemon_name: Optional[str] = None) -> bool:
    """Return True when the active session is the Champions (Reg MA) SP system.

    Optionally runs Pokemon-name inference first (mirroring the wave-2 tools)
    so a Mega/Reg MA mention auto-selects Champions without an explicit set.
    The mainline path is taken whenever this returns False.
    """
    from vgc_mcp_core.rules.format_detect import detect_champions_format
    return detect_champions_format(pokemon_name)

# All 18 Pokemon types
ALL_TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
]


def register_tera_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register Tera type optimization tools."""

    @mcp.tool(
        title="Optimize Tera Type",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def optimize_tera_type(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        spread: Annotated[dict, Field(description="Build dict with 'nature', 'evs', 'item', 'ability' (in Champions sessions an 'sps' dict, or 'evs' interpreted on the 0-32 SP scale)")],
        role: Annotated[str, Field(description="Build role: 'attacker', 'support', or 'tank'")] = "attacker",
        team_pokemon: Annotated[Optional[List[str]], Field(description="Optional list of team members for synergy scoring")] = None,
        meta_threats: Annotated[Optional[List[str]], Field(description="Optional list of meta threats to optimize against")] = None
    ) -> dict:
        """Find the optimal Tera type for a Pokemon build.

        Scores all 18 types on offensive (STAB) and defensive utility and
        returns a ranked list with reasoning plus a recommended type.
        """
        try:
            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Parse spread
            nature = Nature(spread.get("nature", "serious").lower())
            item = spread.get("item")
            ability = spread.get("ability")

            # Build the SUBJECT Pokemon. For Champions the subject carries a
            # StatPointSpread + format_system='champions' so stats and any
            # returned paste use the SP scale (32/66, 'SPs:'); mainline keeps
            # the EVSpread path byte-for-byte unchanged.
            is_champions = _detect_champions(pokemon_name)
            if is_champions:
                # Accept either an explicit 'sps' dict or treat a passed 'evs'
                # dict as SP-scale (capping each stat at 32) so callers in a
                # Champions session always get an SP build.
                sp_input = spread.get("sps")
                if sp_input is None:
                    sp_input = {
                        k: min(int(v), 32)
                        for k, v in (spread.get("evs") or {}).items()
                    }
                sps = StatPointSpread.from_sps_dict(sp_input) if any(
                    short in sp_input for short in ("hp", "at", "df", "sa", "sd", "sp")
                ) else StatPointSpread(**sp_input)
                pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=base_stats,
                    types=types,
                    nature=nature,
                    format_system="champions",
                    sps=sps,
                    item=item,
                    ability=ability
                )
            else:
                evs = EVSpread(**spread.get("evs", {}))
                pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=base_stats,
                    types=types,
                    nature=nature,
                    evs=evs,
                    item=item,
                    ability=ability
                )

            # Score each Tera type
            tera_scores = []

            for tera_type in ALL_TYPES:
                score = 0
                reasoning = []

                # Offensive scoring (STAB boost)
                if role == "attacker":
                    # Check if Tera type matches any moves
                    # For now, give bonus for matching original types (STAB boost)
                    if tera_type in [t.title() for t in types]:
                        score += 30
                        reasoning.append("STAB boost on original type moves")
                    else:
                        score += 15
                        reasoning.append("New STAB option")

                # Defensive scoring
                from vgc_mcp_core.calc.modifiers import get_type_effectiveness

                # Check defensive utility against common threats
                if meta_threats:
                    for threat_name in meta_threats[:5]:  # Top 5 threats
                        try:
                            threat_types = await pokeapi.get_pokemon_types(threat_name)
                            # Check if Tera type resists common threat moves
                            # Simplified: give bonus for resisting common types
                            for threat_type in threat_types:
                                eff = get_type_effectiveness(threat_type, [tera_type])
                                if eff < 1.0:
                                    score += 5
                                    reasoning.append(f"Resists {threat_type}")
                        except Exception:
                            continue

                # Type synergy scoring
                if team_pokemon:
                    # Give bonus for covering team weaknesses
                    team_types = []
                    for team_member in team_pokemon[:3]:  # Check first 3
                        try:
                            member_types = await pokeapi.get_pokemon_types(team_member)
                            team_types.extend(member_types)
                        except Exception:
                            continue

                    # If team is weak to a type, Tera that resists it gets bonus
                    # Simplified scoring
                    score += 5

                tera_scores.append({
                    "type": tera_type,
                    "score": score,
                    "reasoning": reasoning[:3]  # Top 3 reasons
                })

            # Sort by score
            tera_scores.sort(key=lambda x: x["score"], reverse=True)

            # Build markdown output. For Champions the subject's allocation is
            # SP-scale (read from the StatPointSpread); mainline reads EVs.
            if is_champions:
                _alloc = pokemon.sps
                build_label = "SPs"
            else:
                _alloc = pokemon.evs
                build_label = "EVs"
            markdown_lines = [
                f"## Tera Type Analysis: {pokemon_name.title()}",
                "",
                "### Current Build",
                f"{spread.get('nature', 'Serious').title()} | "
                f"{_alloc.hp}/"
                f"{_alloc.attack}/"
                f"{_alloc.defense}/"
                f"{_alloc.special_attack}/"
                f"{_alloc.special_defense}/"
                f"{_alloc.speed} {build_label} | "
                f"{item or 'No item'}",
                "",
                "### Tera Rankings",
                "| Rank | Type | Score | Reasoning |",
                "|------|------|-------|-----------|"
            ]

            for i, tera_data in enumerate(tera_scores[:5], 1):  # Top 5
                reasoning_str = "; ".join(tera_data["reasoning"]) or "General utility"
                markdown_lines.append(
                    f"| {i} | **{tera_data['type']}** | {tera_data['score']} | {reasoning_str} |"
                )

            response = {
                "pokemon": pokemon_name,
                "role": role,
                "format_system": "champions" if is_champions else "mainline",
                "tera_rankings": tera_scores[:10],  # Top 10
                "recommended": tera_scores[0]["type"] if tera_scores else None,
                "markdown_summary": "\n".join(markdown_lines)
            }

            if is_champions:
                response["champions_warning"] = (
                    "Pokemon Champions (Reg MA/MB) has no Terastallization — "
                    "these rankings only apply to mainline VGC formats."
                )

            return response

        except Exception as e:
            logger.error(f"Error in optimize_tera_type: {e}", exc_info=True)
            error_str = str(e).lower()
            if "not found" in error_str:
                suggestions = suggest_pokemon_name(pokemon_name)
                return pokemon_not_found_error(pokemon_name, suggestions)
            return api_error(str(e))
