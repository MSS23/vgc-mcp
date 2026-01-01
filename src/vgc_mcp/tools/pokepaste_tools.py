"""MCP tools for PokePaste integration - fetch and analyze teams from pokepast.es."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from ..api.pokepaste import PokePasteClient, PokePasteError
from ..formats.showdown import parse_showdown_team, ShowdownParseError


def register_pokepaste_tools(mcp: FastMCP, pokepaste: PokePasteClient, pokeapi=None, smogon=None):
    """Register PokePaste tools with the MCP server."""

    @mcp.tool()
    async def fetch_pokepaste(
        url_or_id: str
    ) -> dict:
        """
        Fetch a team from a PokePaste URL and parse it.

        Accepts various formats:
        - Full URL: "https://pokepast.es/abc123"
        - Partial URL: "pokepast.es/abc123"
        - Just the paste ID: "abc123"

        Args:
            url_or_id: PokePaste URL or paste ID

        Returns:
            Parsed team with all Pokemon details (species, EVs, moves, items, etc.)
        """
        try:
            # Fetch the raw paste
            raw_paste = await pokepaste.get_paste(url_or_id)

            # Parse it
            parsed_team = parse_showdown_team(raw_paste)

            if not parsed_team:
                return {
                    "error": "Could not parse any Pokemon from the paste",
                    "raw_preview": raw_paste[:500] if raw_paste else None
                }

            # Format the team for output
            team_data = []
            for pokemon in parsed_team:
                mon_data = {
                    "species": pokemon.species,
                    "item": pokemon.item,
                    "ability": pokemon.ability,
                    "tera_type": pokemon.tera_type,
                    "nature": pokemon.nature,
                    "evs": pokemon.evs,
                    "ivs": {k: v for k, v in pokemon.ivs.items() if v != 31},  # Only non-31 IVs
                    "moves": pokemon.moves,
                    "level": pokemon.level,
                }

                # Add EV total for quick validation
                ev_total = sum(pokemon.evs.values())
                mon_data["ev_total"] = ev_total
                if ev_total > 510:
                    mon_data["ev_warning"] = f"EV total {ev_total} exceeds maximum 510"

                if pokemon.nickname:
                    mon_data["nickname"] = pokemon.nickname

                team_data.append(mon_data)

            # Extract paste ID for reference
            paste_id = pokepaste.extract_paste_id(url_or_id)

            return {
                "success": True,
                "paste_id": paste_id,
                "paste_url": f"https://pokepast.es/{paste_id}",
                "pokemon_count": len(team_data),
                "team": team_data,
                "raw_paste": raw_paste
            }

        except PokePasteError as e:
            return {
                "error": str(e),
                "suggestion": "Check the URL is correct and the paste exists"
            }
        except ShowdownParseError as e:
            return {
                "error": f"Failed to parse paste: {e}",
                "suggestion": "The paste format may be invalid"
            }
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}

    @mcp.tool()
    async def analyze_pokepaste(
        url_or_id: str,
        include_usage_data: bool = True
    ) -> dict:
        """
        Fetch a PokePaste and provide comprehensive analysis.

        Analyzes:
        - EV spread efficiency and potential improvements
        - Speed tier analysis (who outspeeds what)
        - Type coverage and weaknesses
        - Common items/abilities vs Smogon usage
        - Team composition (roles, synergies)

        Args:
            url_or_id: PokePaste URL or paste ID
            include_usage_data: Whether to compare against Smogon usage stats

        Returns:
            Full team analysis with optimization suggestions
        """
        try:
            # First fetch and parse the paste
            raw_paste = await pokepaste.get_paste(url_or_id)
            parsed_team = parse_showdown_team(raw_paste)

            if not parsed_team:
                return {"error": "Could not parse any Pokemon from the paste"}

            paste_id = pokepaste.extract_paste_id(url_or_id)
            analysis = {
                "paste_url": f"https://pokepast.es/{paste_id}",
                "pokemon_count": len(parsed_team),
                "pokemon_analysis": [],
                "team_analysis": {
                    "types": [],
                    "type_weaknesses": {},
                    "roles": [],
                    "speed_tiers": [],
                    "suggestions": []
                }
            }

            all_types = []
            speed_tiers = []
            has_speed_control = False
            has_fake_out = False
            has_redirection = False
            restricted_count = 0

            # Common restricted Pokemon (Reg G/H)
            RESTRICTED = {
                "koraidon", "miraidon", "calyrex-ice", "calyrex-shadow",
                "kyogre", "groudon", "rayquaza", "palkia", "dialga",
                "zacian", "zamazenta", "eternatus", "lunala", "solgaleo",
                "necrozma-dusk-mane", "necrozma-dawn-wings"
            }

            # Speed control moves
            SPEED_CONTROL_MOVES = {"tailwind", "trick room", "icy wind", "electroweb", "scary face"}
            REDIRECTION_ABILITIES = {"follow me", "rage powder", "ally switch"}
            FAKE_OUT_POKEMON = {"incineroar", "rillaboom", "mienshao", "persian", "persian-alola"}

            for pokemon in parsed_team:
                species_lower = pokemon.species.lower().replace(" ", "-")
                mon_analysis = {
                    "species": pokemon.species,
                    "item": pokemon.item,
                    "ability": pokemon.ability,
                    "nature": pokemon.nature,
                    "tera_type": pokemon.tera_type,
                    "evs": pokemon.evs,
                    "moves": pokemon.moves,
                    "analysis": {}
                }

                # Check for restricted
                if species_lower in RESTRICTED:
                    restricted_count += 1
                    mon_analysis["analysis"]["restricted"] = True

                # EV analysis
                ev_total = sum(pokemon.evs.values())
                mon_analysis["ev_total"] = ev_total

                if ev_total < 508:
                    wasted = 508 - ev_total
                    mon_analysis["analysis"]["ev_inefficiency"] = f"{wasted} EVs unused"

                # Check EV efficiency (4/8 leftover pattern)
                for stat, value in pokemon.evs.items():
                    if value > 0 and value % 4 != 0:
                        mon_analysis["analysis"]["ev_warning"] = f"{stat} EVs ({value}) not divisible by 4"

                # Speed calculation (approximate without base stats)
                speed_evs = pokemon.evs.get("spe", 0)
                nature_lower = pokemon.nature.lower()
                speed_nature_boost = nature_lower in ["jolly", "timid", "hasty", "naive"]
                speed_nature_drop = nature_lower in ["brave", "quiet", "relaxed", "sassy"]

                mon_analysis["analysis"]["speed_investment"] = {
                    "evs": speed_evs,
                    "nature_boost": speed_nature_boost,
                    "nature_drop": speed_nature_drop
                }

                # Check for speed control moves
                for move in pokemon.moves:
                    if move.lower().replace(" ", "") in [m.replace(" ", "") for m in SPEED_CONTROL_MOVES]:
                        has_speed_control = True
                        mon_analysis["analysis"]["speed_control"] = move

                    if move.lower() in ["follow me", "rage powder"]:
                        has_redirection = True
                        mon_analysis["analysis"]["redirection"] = move

                # Check for Fake Out users
                if species_lower in FAKE_OUT_POKEMON or "fake out" in [m.lower() for m in pokemon.moves]:
                    has_fake_out = True
                    mon_analysis["analysis"]["fake_out_user"] = True

                # Fetch Smogon usage data for comparison
                if include_usage_data and smogon:
                    try:
                        usage_data = await smogon.get_pokemon_usage(pokemon.species)
                        if usage_data:
                            top_items = list(usage_data.get("items", {}).items())[:3]
                            top_abilities = list(usage_data.get("abilities", {}).items())[:2]

                            # Compare items
                            if pokemon.item:
                                item_lower = pokemon.item.lower().replace(" ", "")
                                common_items = [i[0].lower().replace(" ", "") for i in top_items]
                                if item_lower not in common_items:
                                    mon_analysis["analysis"]["unusual_item"] = {
                                        "using": pokemon.item,
                                        "common": [i[0] for i in top_items]
                                    }

                            # Compare abilities
                            if pokemon.ability:
                                ability_lower = pokemon.ability.lower().replace(" ", "")
                                common_abilities = [a[0].lower().replace(" ", "") for a in top_abilities]
                                if ability_lower not in common_abilities and len(top_abilities) > 1:
                                    mon_analysis["analysis"]["unusual_ability"] = {
                                        "using": pokemon.ability,
                                        "common": [a[0] for a in top_abilities]
                                    }

                            mon_analysis["analysis"]["usage_percent"] = usage_data.get("usage_percent", 0)

                    except Exception:
                        pass  # Smogon data not available

                analysis["pokemon_analysis"].append(mon_analysis)

            # Team-level analysis
            if not has_speed_control:
                analysis["team_analysis"]["suggestions"].append(
                    "No speed control detected - consider adding Tailwind or Trick Room"
                )

            if not has_fake_out:
                analysis["team_analysis"]["suggestions"].append(
                    "No Fake Out user detected - consider Incineroar or Rillaboom for disruption"
                )

            if not has_redirection:
                analysis["team_analysis"]["suggestions"].append(
                    "No redirection detected - Follow Me/Rage Powder can protect setup"
                )

            if restricted_count > 2:
                analysis["team_analysis"]["suggestions"].append(
                    f"Warning: {restricted_count} restricted Pokemon detected (max 2 allowed in most formats)"
                )
            elif restricted_count == 0:
                analysis["team_analysis"]["suggestions"].append(
                    "No restricted Pokemon - this may be a non-restricted format team"
                )

            analysis["team_analysis"]["restricted_count"] = restricted_count
            analysis["team_analysis"]["has_speed_control"] = has_speed_control
            analysis["team_analysis"]["has_fake_out"] = has_fake_out
            analysis["team_analysis"]["has_redirection"] = has_redirection

            return analysis

        except PokePasteError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Analysis failed: {e}"}

    @mcp.tool()
    async def optimize_pokepaste_pokemon(
        url_or_id: str,
        pokemon_index: int = 0
    ) -> dict:
        """
        Analyze a specific Pokemon from a PokePaste and suggest optimizations.

        Provides:
        - EV spread optimization suggestions
        - Move coverage analysis
        - Item alternatives from Smogon usage
        - Nature recommendations

        Args:
            url_or_id: PokePaste URL or paste ID
            pokemon_index: Which Pokemon to optimize (0-5, default first)

        Returns:
            Optimization suggestions for the specified Pokemon
        """
        try:
            raw_paste = await pokepaste.get_paste(url_or_id)
            parsed_team = parse_showdown_team(raw_paste)

            if not parsed_team:
                return {"error": "Could not parse any Pokemon from the paste"}

            if pokemon_index < 0 or pokemon_index >= len(parsed_team):
                return {
                    "error": f"Pokemon index {pokemon_index} out of range",
                    "available_pokemon": [p.species for p in parsed_team]
                }

            pokemon = parsed_team[pokemon_index]
            suggestions = {
                "species": pokemon.species,
                "current_build": {
                    "item": pokemon.item,
                    "ability": pokemon.ability,
                    "nature": pokemon.nature,
                    "tera_type": pokemon.tera_type,
                    "evs": pokemon.evs,
                    "moves": pokemon.moves
                },
                "optimizations": []
            }

            # Check EV total
            ev_total = sum(pokemon.evs.values())
            if ev_total < 508:
                wasted = 508 - ev_total
                suggestions["optimizations"].append({
                    "type": "ev_efficiency",
                    "issue": f"{wasted} EVs unused (total: {ev_total}/508)",
                    "suggestion": "Distribute remaining EVs to improve bulk or speed"
                })

            # Check for suboptimal EV values (not following 4/12/20/28 pattern at L50)
            for stat, value in pokemon.evs.items():
                if value > 0 and value < 252:
                    remainder = value % 8
                    if remainder not in [0, 4]:  # Valid breakpoints
                        nearest = value - remainder if remainder < 4 else value + (8 - remainder)
                        if nearest != value and 0 <= nearest <= 252:
                            suggestions["optimizations"].append({
                                "type": "ev_breakpoint",
                                "stat": stat,
                                "current": value,
                                "suggested": nearest,
                                "reason": "Aligns with level 50 stat breakpoints"
                            })

            # Fetch Smogon data for comparison
            if smogon:
                try:
                    usage_data = await smogon.get_pokemon_usage(pokemon.species)
                    if usage_data:
                        suggestions["smogon_comparison"] = {
                            "usage_percent": usage_data.get("usage_percent", 0),
                            "top_items": list(usage_data.get("items", {}).items())[:5],
                            "top_abilities": list(usage_data.get("abilities", {}).items())[:3],
                            "top_moves": list(usage_data.get("moves", {}).items())[:10],
                            "top_tera_types": list(usage_data.get("tera_types", {}).items())[:3],
                            "top_spreads": usage_data.get("spreads", [])[:3]
                        }

                        # Check if moves match meta
                        top_moves = [m[0].lower() for m in usage_data.get("moves", {}).items()][:10]
                        current_moves = [m.lower() for m in pokemon.moves]
                        unusual_moves = [m for m in current_moves if m not in top_moves and m]
                        if unusual_moves:
                            suggestions["optimizations"].append({
                                "type": "unusual_moves",
                                "moves": unusual_moves,
                                "note": "These moves are less common - may be innovative or suboptimal"
                            })

                except Exception:
                    pass

            return suggestions

        except PokePasteError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Optimization failed: {e}"}
