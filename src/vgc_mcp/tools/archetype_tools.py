"""Team archetype classifier — labels a paste with its strategic archetype.

Rule-based, no ML needed. Looks for signature pieces:
  - Trick Room setters → Trick Room
  - Weather setters + abusers → Sun / Rain / Sand / Snow
  - Tailwind users + fast attackers → Hyper Offense
  - Redirect + bulky attackers → Bulky Offense / Balance
  - Status spam + recovery + defensive cores → Stall (rare in VGC)

Returns a label, confidence, and the rationale (which Pokémon triggered it).
Useful as input to game_plan, scouting, and matchup tools.
"""

from __future__ import annotations

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.formats.showdown import ShowdownParseError, parse_showdown_team
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.utils.errors import ErrorCodes, error_response

# Archetype signature pieces (lowercase, hyphenated names)
TRICK_ROOM_SETTERS = {
    "indeedee-female", "hatterene", "porygon2", "stakataka", "magearna",
    "cresselia", "pelipper", "gothitelle", "calyrex-ice", "ursaluna",
}
TRICK_ROOM_ABUSERS = {  # slow, hard-hitting Pokemon that benefit from TR
    "calyrex-ice", "ursaluna", "ursaluna-bloodmoon", "hatterene", "torkoal",
    "stakataka", "tyranitar", "rhyperior", "gholdengo",
}
WEATHER_SETTERS = {
    "rain": {"pelipper", "kyogre", "primal-kyogre"},
    "sun": {"torkoal", "groudon", "primal-groudon", "koraidon"},
    "sand": {"tyranitar", "gigalith", "hippowdon"},
    "snow": {"abomasnow", "ninetales-alola"},
}
WEATHER_ABUSERS = {
    "rain": {"barraskewda", "archaludon", "basculegion-male", "kingdra"},
    "sun": {"venusaur", "lilligant-hisui", "walking-wake", "raging-bolt"},
    "sand": {"excadrill", "garchomp", "tyranitar"},
    "snow": {"chien-pao", "baxcalibur", "weavile"},
}
TAILWIND_USERS = {
    "tornadus", "whimsicott", "talonflame", "rillaboom", "tornadus-therian",
    "regieleki", "smeargle",
}
FAKE_OUT_USERS = {
    "incineroar", "rillaboom", "raichu", "weavile", "kangaskhan",
    "scrafty", "infernape",
}
REDIRECT_USERS = {
    "amoonguss", "indeedee-male", "clefairy", "togekiss",
}
INTIMIDATE_USERS = {
    "incineroar", "salamence", "landorus-therian", "arcanine",
    "arcanine-hisui", "luxray", "mabosstiff",
}


def _normalize(name: str) -> str:
    return name.lower().replace(" ", "-").strip()


def register_archetype_tools(mcp: FastMCP, team_manager: Optional[TeamManager] = None):

    @mcp.tool(
        title="Classify Team Archetype",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def classify_team_archetype(
        paste: Annotated[Optional[str], Field(
            description="Showdown team paste. Provide this OR pokemon_names.",
        )] = None,
        pokemon_names: Annotated[Optional[list[str]], Field(
            description="List of 4-6 Pokemon names. Provide this OR paste.",
        )] = None,
    ) -> dict:
        """Classify a team's archetype and return its win condition + bring-3 patterns.

        Rule-based: detects Trick Room, weather (Sun/Rain/Sand/Snow), Tailwind
        Offense, Redirect, and Bulky Balance from signature Pokemon. Returns
        the most-confident archetype label, a 0.0-1.0 confidence, the triggers
        (which Pokemon fired each rule), the team's win condition, and
        recommended brings vs broad opponent types.
        """
        names: list[str] = []
        if paste:
            try:
                parsed = parse_showdown_team(paste)
                names = [_normalize(p.name) for p in parsed]
            except ShowdownParseError as e:
                return error_response(ErrorCodes.PARSE_ERROR,
                                      f"Could not parse paste: {e}")
        elif pokemon_names:
            names = [_normalize(n) for n in pokemon_names]
        else:
            return error_response(ErrorCodes.INVALID_PARAMETER,
                                  "Provide either `paste` or `pokemon_names`.")

        if len(names) < 3:
            return error_response(ErrorCodes.INVALID_PARAMETER,
                                  f"Need at least 3 Pokémon (got {len(names)})")

        team_set = set(names)
        triggers: dict[str, list[str]] = {}
        scores: dict[str, float] = {
            "Trick Room": 0.0, "Sun": 0.0, "Rain": 0.0, "Sand": 0.0, "Snow": 0.0,
            "Tailwind Offense": 0.0, "Bulky Balance": 0.0, "Redirect": 0.0,
        }

        # Trick Room: 1 setter + ≥1 abuser → strong signal
        tr_setters = team_set & TRICK_ROOM_SETTERS
        tr_abusers = team_set & TRICK_ROOM_ABUSERS
        if tr_setters:
            triggers["TR setters"] = sorted(tr_setters)
            scores["Trick Room"] += 0.5 + (0.3 if tr_abusers else 0)
            if tr_abusers:
                triggers["TR abusers"] = sorted(tr_abusers)

        # Weather
        for kind, setters in WEATHER_SETTERS.items():
            ws = team_set & setters
            wa = team_set & WEATHER_ABUSERS[kind]
            if ws:
                triggers[f"{kind} setters"] = sorted(ws)
                scores[kind.title()] += 0.5 + (0.3 if wa else 0)
                if wa:
                    triggers[f"{kind} abusers"] = sorted(wa)

        # Tailwind offense
        tw = team_set & TAILWIND_USERS
        if tw and len(team_set & FAKE_OUT_USERS) > 0:
            triggers["Tailwind users"] = sorted(tw)
            scores["Tailwind Offense"] += 0.4 + (0.2 * len(tw))

        # Bulky / redirect
        red = team_set & REDIRECT_USERS
        if red:
            triggers["Redirect"] = sorted(red)
            scores["Redirect"] += 0.4

        intim = team_set & INTIMIDATE_USERS
        if intim:
            triggers["Intimidate"] = sorted(intim)
            scores["Bulky Balance"] += 0.3

        # Pick top archetype
        top_arch, top_score = max(scores.items(), key=lambda kv: kv[1])
        if top_score < 0.3:
            top_arch = "Balance / Other"
            top_score = 0.3
        confidence = min(1.0, top_score)

        win_condition = _win_condition(top_arch, names)
        recommended = _bring_3(top_arch, names)

        return {
            "success": True,
            "team": names,
            "archetype": top_arch,
            "confidence": round(confidence, 2),
            "all_scores": {k: round(v, 2) for k, v in scores.items()},
            "triggers": triggers,
            "win_condition": win_condition,
            "recommended_brings": recommended,
            "agent_instruction": (
                "Lead with the archetype label and confidence in a one-line summary. "
                "Render `triggers` as a 'Why' section showing which Pokémon fit the "
                "pattern. Render `recommended_brings` as a table: Matchup | Bring | Reason."
            ),
        }


def _win_condition(arch: str, names: list[str]) -> str:
    if arch == "Trick Room":
        return ("Set Trick Room turn 1, sweep with slow heavy hitters before "
                "the 5-turn timer expires.")
    if arch in ("Sun", "Rain", "Sand", "Snow"):
        return (f"Establish {arch.lower()} turn 1, abuse weather-boosted moves "
                "and abilities to overwhelm the opponent.")
    if arch == "Tailwind Offense":
        return ("Set Tailwind early, use Fake Out + spread damage + fast "
                "attackers to KO before the speed advantage runs out.")
    if arch == "Redirect":
        return ("Use Rage Powder/Follow Me to absorb attacks while a setup "
                "sweeper or wallbreaker pressures the field.")
    if arch == "Bulky Balance":
        return ("Pivot with Intimidate and Fake Out, wear down threats with "
                "chip damage, and outlast the opponent.")
    return "Identify the strongest matchup and force trades to a winning endgame."


def _bring_3(arch: str, names: list[str]) -> list[dict]:
    """Lightweight bring-3 suggestions per matchup category."""
    return [
        {"matchup": "vs Hyper Offense",
         "approach": "Lead Fake Out + bulky pivot; preserve Tera for late-game"},
        {"matchup": "vs Trick Room",
         "approach": "Pressure setter T1 (Taunt / KO); fast cleaners on bench"},
        {"matchup": "vs Weather",
         "approach": "Bring weather counter (different setter / weather rock); "
                     "force the weather war"},
        {"matchup": "vs Bulky Balance",
         "approach": "Wallbreakers with crit moves or Mold Breaker; "
                     "avoid Intimidate fishing"},
    ]
