"""Team diff tools for comparing Pokemon team versions.

This module provides tools to compare two versions of a team and identify
what changed between them. No HTML UI - returns structured data only.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokepaste import PokePasteClient, PokePasteError
from vgc_mcp_core.formats.showdown import parse_showdown_team, ShowdownParseError
from vgc_mcp_core.diff import generate_team_diff


def register_diff_tools(mcp: FastMCP):
    """Register team diff tools with the MCP server."""

    @mcp.tool()
    async def compare_team_versions(
        version1: str,
        version2: str,
        v1_name: Optional[str] = None,
        v2_name: Optional[str] = None,
    ) -> dict:
        """Compare two versions of a Pokemon team and show what changed.

        Accepts either Pokepaste URLs or raw Showdown paste text.
        Pokemon are matched by species name (not slot position), so
        reordering the team won't count as changes.

        Detects changes to:
        - EVs/IVs - with explanations like "Moved 52 EVs from Spe to Def"
        - Nature - with stat trade explanations
        - Item - with role change explanations
        - Ability
        - Tera Type
        - Moves - shows added/removed

        Args:
            version1: First team version (Pokepaste URL or raw paste text)
            version2: Second team version (Pokepaste URL or raw paste text)
            v1_name: Optional display name for version 1
            v2_name: Optional display name for version 2

        Returns:
            Dict with diff summary, changes per Pokemon, added/removed Pokemon
        """
        pokepaste = PokePasteClient()

        async def parse_team_input(input_str: str) -> tuple[list, str]:
            """Parse team from URL or raw paste.

            Returns: (parsed_team, display_name)
            """
            input_str = input_str.strip()

            # Check if it looks like a pokepaste URL or ID
            paste_id = pokepaste.extract_paste_id(input_str)
            if paste_id:
                try:
                    raw = await pokepaste.get_paste(paste_id)
                    return parse_showdown_team(raw), f"pokepast.es/{paste_id}"
                except PokePasteError as e:
                    return None, f"Failed to fetch pokepaste: {e}"

            # Check if it has newlines (looks like raw paste)
            if "\n" in input_str or len(input_str) > 50:
                try:
                    team = parse_showdown_team(input_str)
                    if team:
                        return team, "Raw Paste"
                except ShowdownParseError:
                    pass

            return None, "Could not parse input as team"

        # Parse both teams
        team1, name1 = await parse_team_input(version1)
        if team1 is None:
            return {
                "success": False,
                "error": f"Failed to parse version 1: {name1}",
            }

        team2, name2 = await parse_team_input(version2)
        if team2 is None:
            return {
                "success": False,
                "error": f"Failed to parse version 2: {name2}",
            }

        # Use provided names or detected names
        display_v1 = v1_name or name1
        display_v2 = v2_name or name2

        # Generate diff
        diff = generate_team_diff(team1, team2, display_v1, display_v2)

        # Categorize diffs by change type
        from vgc_mcp_core.diff.models import ChangeType

        added = [d for d in diff.pokemon_diffs if d.change_type == ChangeType.ADDED]
        removed = [d for d in diff.pokemon_diffs if d.change_type == ChangeType.REMOVED]
        modified = [d for d in diff.pokemon_diffs if d.change_type == ChangeType.MODIFIED]

        return {
            "success": True,
            "summary": diff.summary,
            "version1_name": display_v1,
            "version2_name": display_v2,
            "added_pokemon": [p.species for p in added],
            "removed_pokemon": [p.species for p in removed],
            "changed_pokemon": [
                {
                    "species": c.species,
                    "changes": [
                        {
                            "field": change.field.value if hasattr(change.field, 'value') else change.field,
                            "before": change.before,
                            "after": change.after,
                            "explanation": change.reason,
                        }
                        for change in c.changes
                    ]
                }
                for c in modified
            ],
            "unchanged_pokemon": diff.unchanged,
            "diff": diff.to_dict(),
        }
