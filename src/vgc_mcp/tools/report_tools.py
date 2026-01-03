# -*- coding: utf-8 -*-
"""MCP tools for generating shareable team build reports.

This module provides tools to generate build reports documenting
the team building journey. Returns structured data (no HTML UI).
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.pokepaste import PokePasteClient, PokePasteError
from vgc_mcp_core.formats.showdown import parse_showdown_team, ShowdownParseError


def register_report_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register report generation tools with the MCP server."""

    @mcp.tool()
    async def generate_build_report(
        initial_pokepaste_url: Optional[str] = None,
        initial_team: Optional[list[dict]] = None,
        final_pokepaste_url: Optional[str] = None,
        final_team: Optional[list[dict]] = None,
        conversation: Optional[list[dict]] = None,
        changes: Optional[list[dict]] = None,
        takeaways: Optional[list[str]] = None,
        title: Optional[str] = None,
    ) -> dict:
        """
        Generate a shareable team build report showing the building journey.

        Creates a structured report that documents the team building process:
        - Starting team state
        - Discussion points (Q&A exchanges)
        - Changes made with reasoning
        - Final team state
        - Key takeaways and conclusions

        Args:
            initial_pokepaste_url: Pokepaste URL for starting team (optional if initial_team provided)
            initial_team: List of pokemon dicts for starting team (alternative to URL)
            final_pokepaste_url: Pokepaste URL for final team (optional if final_team provided)
            final_team: List of pokemon dicts for final team (alternative to URL)
            conversation: List of Q&A exchanges, each dict with:
                - question: str (the question asked)
                - answer: str (the answer given)
            changes: List of changes made, each dict with:
                - pokemon: str (species name)
                - field: str (what changed, e.g., "Speed EVs", "Tera Type")
                - before: str (old value)
                - after: str (new value)
                - reason: str (why the change was made)
            takeaways: List of key conclusion strings
            title: Optional report title (defaults to "VGC Team Build Report")

        Returns:
            Dict with structured report data
        """
        try:
            pokepaste_client = PokePasteClient()

            # Parse initial team
            initial_team_data = []
            paste_url = None

            if initial_pokepaste_url:
                paste_url = initial_pokepaste_url
                raw_paste = await pokepaste_client.get_paste(initial_pokepaste_url)
                parsed_team = parse_showdown_team(raw_paste)
                initial_team_data = await _enrich_team_data(parsed_team, pokeapi)
            elif initial_team:
                initial_team_data = initial_team

            # Parse final team
            final_team_data = []
            if final_pokepaste_url:
                raw_paste = await pokepaste_client.get_paste(final_pokepaste_url)
                parsed_team = parse_showdown_team(raw_paste)
                final_team_data = await _enrich_team_data(parsed_team, pokeapi)
            elif final_team:
                final_team_data = final_team
            else:
                # If no final team specified, use initial team
                final_team_data = initial_team_data

            # Build markdown report
            report_lines = []
            report_lines.append(f"# {title or 'VGC Team Build Report'}")
            report_lines.append("")

            if paste_url:
                report_lines.append(f"**Starting team:** {paste_url}")
                report_lines.append("")

            # Initial team summary
            if initial_team_data:
                report_lines.append("## Initial Team")
                for pkmn in initial_team_data:
                    species = pkmn.get("species", "Unknown")
                    item = pkmn.get("item", "None")
                    ability = pkmn.get("ability", "Unknown")
                    tera = pkmn.get("tera_type", "Unknown")
                    report_lines.append(f"- **{species}** @ {item} | {ability} | Tera: {tera}")
                report_lines.append("")

            # Conversation/discussion
            if conversation:
                report_lines.append("## Discussion")
                for i, exchange in enumerate(conversation, 1):
                    q = exchange.get("question", "")
                    a = exchange.get("answer", "")
                    report_lines.append(f"**Q{i}:** {q}")
                    report_lines.append(f"**A{i}:** {a}")
                    report_lines.append("")

            # Changes made
            if changes:
                report_lines.append("## Changes Made")
                for change in changes:
                    pkmn = change.get("pokemon", "Unknown")
                    field = change.get("field", "Unknown")
                    before = change.get("before", "?")
                    after = change.get("after", "?")
                    reason = change.get("reason", "")
                    report_lines.append(f"- **{pkmn}** - {field}: {before} -> {after}")
                    if reason:
                        report_lines.append(f"  - Reason: {reason}")
                report_lines.append("")

            # Final team
            if final_team_data and final_team_data != initial_team_data:
                report_lines.append("## Final Team")
                for pkmn in final_team_data:
                    species = pkmn.get("species", "Unknown")
                    item = pkmn.get("item", "None")
                    ability = pkmn.get("ability", "Unknown")
                    tera = pkmn.get("tera_type", "Unknown")
                    report_lines.append(f"- **{species}** @ {item} | {ability} | Tera: {tera}")
                report_lines.append("")

            # Takeaways
            if takeaways:
                report_lines.append("## Key Takeaways")
                for takeaway in takeaways:
                    report_lines.append(f"- {takeaway}")
                report_lines.append("")

            markdown_report = "\n".join(report_lines)

            return {
                "success": True,
                "title": title or "VGC Team Build Report",
                "initial_pokemon_count": len(initial_team_data),
                "final_pokemon_count": len(final_team_data),
                "conversation_count": len(conversation or []),
                "changes_count": len(changes or []),
                "takeaways_count": len(takeaways or []),
                "report": markdown_report,
                "initial_team": initial_team_data,
                "final_team": final_team_data,
                "changes": changes or [],
                "takeaways": takeaways or [],
            }

        except PokePasteError as e:
            return {
                "success": False,
                "error": "fetch_error",
                "message": str(e),
            }
        except ShowdownParseError as e:
            return {
                "success": False,
                "error": "parse_error",
                "message": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "unknown_error",
                "message": str(e),
            }


async def _enrich_team_data(parsed_team: list, pokeapi: PokeAPIClient) -> list[dict]:
    """Convert parsed Showdown team to enriched dict format with base stats."""
    pokemon_list = []

    for parsed in parsed_team:
        species_name = parsed.species.lower().replace(" ", "-")

        try:
            base_stats = await pokeapi.get_base_stats(species_name)
            types = await pokeapi.get_pokemon_types(species_name)
        except Exception:
            base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 80}
            types = ["Normal"]

        # Normalize base_stats keys
        base_stats_short = {
            "hp": base_stats.get("hp", base_stats.get("hp", 80)),
            "atk": base_stats.get("attack", base_stats.get("atk", 80)),
            "def": base_stats.get("defense", base_stats.get("def", 80)),
            "spa": base_stats.get("special_attack", base_stats.get("spa", 80)),
            "spd": base_stats.get("special_defense", base_stats.get("spd", 80)),
            "spe": base_stats.get("speed", base_stats.get("spe", 80)),
        }

        evs_short = {
            "hp": parsed.evs.get("hp", 0),
            "atk": parsed.evs.get("atk", 0),
            "def": parsed.evs.get("def", 0),
            "spa": parsed.evs.get("spa", 0),
            "spd": parsed.evs.get("spd", 0),
            "spe": parsed.evs.get("spe", 0),
        }

        ivs_short = {}
        for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
            iv_val = parsed.ivs.get(stat, 31)
            if iv_val != 31:
                ivs_short[stat] = iv_val

        pokemon_list.append({
            "species": parsed.species,
            "types": types,
            "item": parsed.item,
            "ability": parsed.ability,
            "nature": parsed.nature,
            "evs": evs_short,
            "ivs": ivs_short,
            "moves": parsed.moves,
            "tera_type": parsed.tera_type,
            "level": parsed.level,
            "base_stats": base_stats_short,
        })

    return pokemon_list
