"""Showdown replay analyzer.

Pulls a public Pokémon Showdown replay JSON, parses the protocol log,
and produces a turn-by-turn breakdown suitable for post-game coaching:

- Each turn's lead pair, moves chosen, damage/HP %, status changes
- KO attribution per turn
- Speed-control timeline (Tailwind / TR / weather)
- Tera activations, items revealed
- Coaching prompts: "missed KO this turn", "could have switched", etc.

The agent is expected to summarize this in plain English afterwards.
This tool just produces the structured facts.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.utils.errors import ErrorCodes, error_response

logger = logging.getLogger(__name__)


REPLAY_ID_RE = re.compile(r"replay\.pokemonshowdown\.com/([a-zA-Z0-9_\-]+)")


def _replay_url_to_json(url_or_id: str) -> str:
    """Accept either a Showdown replay URL, replay ID, or .json URL — return .json URL."""
    s = url_or_id.strip()
    if s.endswith(".json"):
        return s
    m = REPLAY_ID_RE.search(s)
    if m:
        return f"https://replay.pokemonshowdown.com/{m.group(1)}.json"
    # Treat as raw replay id
    if "/" not in s and "." not in s:
        return f"https://replay.pokemonshowdown.com/{s}.json"
    # Fall back: append .json
    if s.startswith("http") and not s.endswith(".json"):
        return s.rstrip("/") + ".json"
    return s


async def _fetch_replay(url_or_id: str) -> dict:
    """Fetch the replay JSON from Showdown."""
    url = _replay_url_to_json(url_or_id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def _parse_log(log: str) -> list[dict]:
    """Parse Showdown's protocol log into per-turn structured events.

    Showdown format ref: https://github.com/smogon/pokemon-showdown/blob/master/sim/SIM-PROTOCOL.md
    Each line starts with `|<command>|...`. We're interested in:
      |turn|N
      |move|p1a: Pokemon|MoveName|p2a: Target
      |-damage|p1a: Pokemon|HP/TotalHP|...
      |-heal|...
      |-status|p1a: Pokemon|brn|...
      |faint|p2a: Pokemon
      |-terastallize|p1a: Pokemon|TeraType
      |-weather|Weather|[from] ability
      |-fieldstart|move: Trick Room|...
      |-sidestart|p1: User|move: Tailwind
      |-item|p1a: Pokemon|Item|[from] ability  (item reveal)
      |-ability|p1a: Pokemon|Ability|...       (ability reveal)
    """
    turns: list[dict] = [{"turn": 0, "events": []}]  # Pre-game
    current = turns[0]

    for raw in log.splitlines():
        if not raw.startswith("|"):
            continue
        parts = raw.split("|")[1:]
        if not parts:
            continue
        cmd = parts[0]
        args = parts[1:]

        if cmd == "turn":
            turn_num = int(args[0]) if args else len(turns)
            current = {"turn": turn_num, "events": []}
            turns.append(current)
            continue

        ev: Optional[dict[str, Any]] = None

        if cmd == "move" and len(args) >= 2:
            ev = {"type": "move", "user": args[0], "move": args[1],
                  "target": args[2] if len(args) > 2 else None}
        elif cmd in ("-damage", "-heal") and len(args) >= 2:
            ev = {"type": cmd[1:], "target": args[0], "hp": args[1],
                  "from": _parse_from(args[2:]) if len(args) > 2 else None}
        elif cmd == "-status" and len(args) >= 2:
            ev = {"type": "status", "target": args[0], "status": args[1],
                  "from": _parse_from(args[2:])}
        elif cmd == "-curestatus" and len(args) >= 2:
            ev = {"type": "curestatus", "target": args[0], "status": args[1]}
        elif cmd == "faint" and args:
            ev = {"type": "faint", "target": args[0]}
        elif cmd == "-terastallize" and len(args) >= 2:
            ev = {"type": "terastallize", "user": args[0], "tera_type": args[1]}
        elif cmd == "-weather" and args:
            ev = {"type": "weather", "weather": args[0],
                  "from": _parse_from(args[1:])}
        elif cmd == "-fieldstart" and args:
            ev = {"type": "fieldstart", "effect": args[0],
                  "from": _parse_from(args[1:])}
        elif cmd == "-fieldend" and args:
            ev = {"type": "fieldend", "effect": args[0]}
        elif cmd == "-sidestart" and len(args) >= 2:
            ev = {"type": "sidestart", "side": args[0], "effect": args[1]}
        elif cmd == "-sideend" and len(args) >= 2:
            ev = {"type": "sideend", "side": args[0], "effect": args[1]}
        elif cmd == "-item" and len(args) >= 2:
            ev = {"type": "item_reveal", "target": args[0], "item": args[1],
                  "from": _parse_from(args[2:])}
        elif cmd == "-ability" and len(args) >= 2:
            ev = {"type": "ability_reveal", "target": args[0], "ability": args[1],
                  "from": _parse_from(args[2:])}
        elif cmd == "switch" and len(args) >= 2:
            ev = {"type": "switch", "user": args[0], "details": args[1]}
        elif cmd == "-boost" and len(args) >= 3:
            ev = {"type": "boost", "target": args[0],
                  "stat": args[1], "amount": int(args[2])}
        elif cmd == "-unboost" and len(args) >= 3:
            ev = {"type": "unboost", "target": args[0],
                  "stat": args[1], "amount": int(args[2])}
        elif cmd == "-crit" and args:
            ev = {"type": "crit", "target": args[0]}
        elif cmd == "-supereffective" and args:
            ev = {"type": "supereffective", "target": args[0]}
        elif cmd == "-resisted" and args:
            ev = {"type": "resisted", "target": args[0]}
        elif cmd == "-immune" and args:
            ev = {"type": "immune", "target": args[0]}
        elif cmd == "-miss" and args:
            ev = {"type": "miss", "user": args[0]}
        elif cmd == "win" and args:
            ev = {"type": "win", "winner": args[0]}

        if ev is not None:
            current["events"].append(ev)

    # Drop pre-game empty bucket if it has no events
    if turns and turns[0]["turn"] == 0 and not turns[0]["events"]:
        turns.pop(0)
    return turns


def _parse_from(extras: list[str]) -> Optional[str]:
    """Pull the [from] cause out of trailing args, if present."""
    for x in extras:
        if x.startswith("[from] "):
            return x[len("[from] "):]
    return None


def _hp_to_percent(hp: str) -> Optional[float]:
    """Showdown HP fields look like '142/270', 'fnt', or 'a/b status'."""
    if not hp or hp == "fnt":
        return 0.0
    s = hp.split(" ", 1)[0]
    if "/" in s:
        cur, total = s.split("/", 1)
        try:
            return round(float(cur) / float(total) * 100.0, 1)
        except ValueError:
            return None
    return None


def _identify(slot: str) -> tuple[str, str]:
    """Convert 'p1a: Flutter Mane' -> ('p1', 'Flutter Mane')."""
    if ": " in slot:
        side, name = slot.split(": ", 1)
        return side[:2], name
    return "?", slot


def register_replay_tools(mcp: FastMCP):
    """Showdown replay analysis tools."""

    @mcp.tool()
    async def analyze_replay(
        replay_url: str,
        deep: bool = False,
    ) -> dict:
        """Pull a public Showdown replay and produce a turn-by-turn breakdown.

        Accepts any of:
        - `https://replay.pokemonshowdown.com/<id>`
        - `https://replay.pokemonshowdown.com/<id>.json`
        - just the bare replay ID (e.g. `gen9vgc2024regh-1234567890`)

        Returns:
            * `meta` — players, format, winner, turn count
            * `team_preview` — both teams as revealed at preview
            * `turns` — list of turn objects with the full event stream
            * `key_events` — the moments worth coaching on (KOs, Tera uses,
              status applications, weather/TR setup, missed KOs)
            * `agent_instruction` — how to summarise this for the user

        With `deep=True`, includes raw HP-tracked Pokémon state per turn —
        useful for the agent to check "did this move actually KO?" without
        rerunning the damage formula.
        """
        try:
            data = await _fetch_replay(replay_url)
        except httpx.HTTPStatusError as e:
            return error_response(
                ErrorCodes.API_NOT_FOUND,
                f"Replay not found or inaccessible: {e.response.status_code}",
                suggestions=["Check the replay URL", "Make sure the replay is public"],
            )
        except httpx.RequestError as e:
            return error_response(
                ErrorCodes.API_ERROR,
                f"Failed to fetch replay: {e}",
                suggestions=["Try again — Showdown may be temporarily down"],
            )
        except ValueError as e:
            return error_response(ErrorCodes.PARSE_ERROR, f"Replay JSON malformed: {e}")

        log = data.get("log", "")
        if not log:
            return error_response(
                ErrorCodes.PARSE_ERROR,
                "Replay has no log content. May be a private or expired replay.",
            )

        turns = _parse_log(log)

        # Extract meta
        meta = {
            "id": data.get("id"),
            "format": data.get("format") or data.get("formatid"),
            "p1": data.get("p1"),
            "p2": data.get("p2"),
            "uploadtime": data.get("uploadtime"),
            "rating": data.get("rating"),
            "private": data.get("private", 0),
            "turn_count": max((t["turn"] for t in turns), default=0),
        }
        # Winner from final |win| event
        winner = None
        for t in turns:
            for e in t["events"]:
                if e["type"] == "win":
                    winner = e["winner"]
        meta["winner"] = winner

        # Build team preview from the log's `|poke|p1|Pokemon, L50, M|item` lines
        team_preview = _extract_team_preview(log)

        # Identify "key events" worth coaching on
        key_events = _extract_key_events(turns)

        # Compress per-turn HP state if deep=False
        if not deep:
            for t in turns:
                t["events"] = [
                    {k: v for k, v in e.items() if k != "raw"}
                    for e in t["events"]
                    if e["type"] not in {"crit", "resisted", "supereffective"} or len(t["events"]) < 50
                ]

        return {
            "success": True,
            "meta": meta,
            "team_preview": team_preview,
            "turns": turns,
            "key_events": key_events,
            "agent_instruction": (
                "Summarise the replay in 5-8 bullets focused on: "
                "(1) game-flow (who was ahead each turn), "
                "(2) decisive turns (KOs and missed KOs), "
                "(3) Tera timing and whether each player used Tera well, "
                "(4) speed-control swings (Tailwind / TR / weather wars), "
                "(5) one specific lesson the user could take away. "
                "If `winner` differs from the user's side, frame the lesson around what "
                "the LOSER could have done differently. Render the team preview as a "
                "table per the presentation rules. Don't dump raw event lists."
            ),
        }


def _extract_team_preview(log: str) -> dict[str, list[str]]:
    """Pull `|poke|p1|Species, L50, M|item` lines into per-side rosters."""
    out: dict[str, list[str]] = {"p1": [], "p2": []}
    for line in log.splitlines():
        if line.startswith("|poke|"):
            parts = line.split("|")
            if len(parts) >= 4:
                side = parts[2]
                details = parts[3]
                # "Flutter Mane, L50, M" -> "Flutter Mane"
                species = details.split(",")[0].strip()
                if side in out:
                    out[side].append(species)
    return out


def _extract_key_events(turns: list[dict]) -> list[dict]:
    """Surface the events worth coaching on."""
    key: list[dict] = []
    for t in turns:
        turn_num = t["turn"]
        for e in t["events"]:
            etype = e.get("type")
            if etype == "faint":
                side, name = _identify(e["target"])
                key.append({"turn": turn_num, "kind": "KO", "side": side,
                           "pokemon": name})
            elif etype == "terastallize":
                side, name = _identify(e["user"])
                key.append({"turn": turn_num, "kind": "TERA", "side": side,
                           "pokemon": name, "tera_type": e["tera_type"]})
            elif etype == "fieldstart" and "Trick Room" in e.get("effect", ""):
                key.append({"turn": turn_num, "kind": "TRICK_ROOM_SET"})
            elif etype == "sidestart" and "Tailwind" in e.get("effect", ""):
                key.append({"turn": turn_num, "kind": "TAILWIND_SET",
                           "side": e["side"]})
            elif etype == "weather":
                key.append({"turn": turn_num, "kind": "WEATHER",
                           "weather": e["weather"], "from": e.get("from")})
            elif etype == "status":
                side, name = _identify(e["target"])
                key.append({"turn": turn_num, "kind": "STATUS",
                           "side": side, "pokemon": name, "status": e["status"]})
            elif etype == "miss":
                side, name = _identify(e["user"])
                key.append({"turn": turn_num, "kind": "MISS",
                           "side": side, "pokemon": name})
    return key
