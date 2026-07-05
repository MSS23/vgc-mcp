"""Live battle copilot — turn-by-turn coaching against a remembered battle.

The agent can drive a real game with these tools:

  start_battle({"my_team": ["flutter-mane","urshifu-rapid-strike",...],
                "opp_team": ["incineroar","rillaboom","tornadus","amoonguss"]})

  record_turn({"my_lead": ["flutter-mane","urshifu"], "opp_lead": [...],
               "events": "Incin Intimidated my Urshifu (-1 Atk).
                          Tornadus revealed Covert Cloak.
                          My Flutter Mane Tera'd Fairy.",
               "hp_changes": {"opp/incineroar": 65, "me/flutter-mane": 90}})

  suggest_next_move()  -> ranked recommendations, KO possibilities,
                          speed control matchups, win condition assessment

  get_battle_state()   -> structured snapshot of the remembered battle
  end_battle()         -> archives the battle and returns the final state
"""

from __future__ import annotations

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.calc.priority import normalize_move_name
from vgc_mcp_core.state import BattleStateManager
from vgc_mcp_core.utils.errors import ErrorCodes, error_response

logger = logging.getLogger(__name__)


def register_battle_tools(mcp: FastMCP, battle_manager: BattleStateManager):
    """Live battle copilot tools — keep state across turns."""

    @mcp.tool()
    async def start_battle(
        my_team: list[str],
        opp_team: list[str],
        format: Optional[str] = None,
        my_lead: Optional[list[str]] = None,
        opp_lead: Optional[list[str]] = None,
    ) -> dict:
        """Begin a new battle. Replaces any active battle.

        Args:
            my_team: 4-6 Pokémon names on YOUR side (full party).
            opp_team: 4-6 Pokémon names on OPPONENT'S side (revealed at team preview).
            format: Active VGC regulation. Defaults to the current regulation
                from the regulation config when omitted.
            my_lead: Your two leads. If omitted, no Pokémon are marked on-field yet.
            opp_lead: Opponent's two leads. Same default.

        Returns the battle's initial state including suggested lead matchup
        thoughts. Call `record_turn` after each turn to advance state, and
        `suggest_next_move` any time for an updated recommendation.
        """
        if not (4 <= len(my_team) <= 6) or not (4 <= len(opp_team) <= 6):
            return error_response(
                ErrorCodes.INVALID_PARAMETER,
                "Each team must be 4-6 Pokémon at battle start.",
            )

        battle = battle_manager.start(my_team, opp_team, format=format or None)
        if my_lead:
            for n in my_lead:
                battle_manager.update_pokemon("me", n, on_field=True)
        if opp_lead:
            for n in opp_lead:
                battle_manager.update_pokemon("opp", n, on_field=True)

        return {
            "success": True,
            "battle_id": battle.battle_id,
            "turn": battle.turn,
            "my_team": [p.name for p in battle.my_team],
            "opp_team": [p.name for p in battle.opp_team],
            "my_lead": my_lead or [],
            "opp_lead": opp_lead or [],
            "next_step": (
                "Use `record_turn` after each turn with hp_changes, status changes, "
                "and any revealed items/abilities. Call `suggest_next_move` to get "
                "the agent's recommendation for the upcoming turn."
            ),
        }

    @mcp.tool()
    async def record_turn(
        my_lead: Optional[list[str]] = None,
        opp_lead: Optional[list[str]] = None,
        events: str = "",
        hp_changes: Optional[dict[str, float]] = None,
        status_changes: Optional[dict[str, str]] = None,
        revealed_items: Optional[dict[str, str]] = None,
        revealed_abilities: Optional[dict[str, str]] = None,
        revealed_moves: Optional[dict[str, str]] = None,
        teras: Optional[list[str]] = None,
        weather: Optional[str] = None,
        terrain: Optional[str] = None,
        tailwind: Optional[str] = None,
        trick_room: bool = False,
        screens: Optional[list[str]] = None,
        stage_changes: Optional[dict[str, dict[str, int]]] = None,
        coaching_used: str = "",
    ) -> dict:
        """Record one turn of an active battle.

        Identifier format: "side/pokemon" — e.g. `me/flutter-mane`, `opp/incineroar`.

        Args:
            my_lead / opp_lead: New lead pairs if you switched in.
            events: Free-form description ("Intimidate dropped Urshifu, Incineroar
                used Fake Out on Flutter Mane, my Urshifu Surging Strikes KO'd Incin").
                Parsed loosely — prefer structured fields when possible.
            hp_changes: { "opp/incineroar": 65, "me/flutter-mane": 90 } — new HP %.
            status_changes: { "me/amoonguss": "burn" }.
            revealed_items: { "opp/tornadus": "covert-cloak" } — when an item activates.
            revealed_abilities: { "opp/incineroar": "intimidate" }.
            revealed_moves: { "opp/rillaboom": "fake-out" }.
            teras: ["me/flutter-mane:fairy", "opp/incineroar:ghost"] — Tera activations.
            weather: "rain" | "sun" | "sand" | "snow" if started this turn.
            terrain: "grassy" | "psychic" | "electric" | "misty" if started.
            tailwind: "me" | "opp" if Tailwind started for that side.
            trick_room: True if Trick Room was set this turn.
            screens: ["me/light-screen", "opp/reflect"] — screens set up.
            stage_changes: { "me/urshifu": {"attack": -1} } — net stage deltas.
            coaching_used: optional record of what advice was followed.

        Auto-decays existing weather/terrain/tailwind/trick-room/screen timers.
        """
        if not battle_manager.has_active():
            return error_response(
                ErrorCodes.INVALID_PARAMETER,
                "No active battle. Call `start_battle` first.",
            )
        b = battle_manager.require()

        # First, mark anyone newly on the field
        if my_lead:
            for p in b.my_team:
                p.on_field = False
            for n in my_lead:
                try:
                    battle_manager.update_pokemon("me", n, on_field=True)
                except ValueError as e:
                    return error_response(ErrorCodes.POKEMON_NOT_FOUND, str(e))
        if opp_lead:
            for p in b.opp_team:
                p.on_field = False
            for n in opp_lead:
                try:
                    battle_manager.update_pokemon("opp", n, on_field=True)
                except ValueError as e:
                    return error_response(ErrorCodes.POKEMON_NOT_FOUND, str(e))

        # Parse "side/pokemon" identifiers
        def _split(key: str) -> tuple[str, str]:
            if "/" in key:
                side, name = key.split("/", 1)
            else:
                side, name = "me", key
            return side, name

        for k, v in (hp_changes or {}).items():
            side, name = _split(k)
            try:
                battle_manager.update_pokemon(side, name, hp_percent=float(v))
            except ValueError as e:
                return error_response(ErrorCodes.POKEMON_NOT_FOUND, str(e))

        for k, v in (status_changes or {}).items():
            side, name = _split(k)
            battle_manager.update_pokemon(side, name, status=v)
        for k, v in (revealed_items or {}).items():
            side, name = _split(k)
            battle_manager.update_pokemon(side, name, revealed_item=v)
        for k, v in (revealed_abilities or {}).items():
            side, name = _split(k)
            battle_manager.update_pokemon(side, name, revealed_ability=v)
        for k, v in (revealed_moves or {}).items():
            side, name = _split(k)
            battle_manager.update_pokemon(side, name, revealed_move=normalize_move_name(v))

        for entry in teras or []:
            # "me/flutter-mane:fairy"
            if ":" not in entry:
                continue
            who, tera = entry.split(":", 1)
            side, name = _split(who)
            battle_manager.update_pokemon(
                side, name, has_terastallized=True, revealed_tera_type=tera.lower(),
            )

        for k, deltas in (stage_changes or {}).items():
            side, name = _split(k)
            battle_manager.update_pokemon(side, name, stage_changes=deltas)

        # Field state — VGC defaults: weather 5 turns, terrain 5, screens 5,
        # tailwind 4 (3 after the turn it sets), trick room 5
        f = b.field
        if weather:
            f.weather = weather
            f.weather_turns_left = 5
        if terrain:
            f.terrain = terrain
            f.terrain_turns_left = 5
        if tailwind == "me":
            f.my_tailwind_turns = 4
        elif tailwind == "opp":
            f.opp_tailwind_turns = 4
        if trick_room:
            f.trick_room_turns = 5
        for s in screens or []:
            side, kind = _split(s)
            kind = kind.replace("-", "_")
            attr = f"{'my' if side == 'me' else 'opp'}_{kind}_turns"
            if hasattr(f, attr):
                setattr(f, attr, 5)

        # Append a turn-history record (also decays timers)
        battle_manager.advance_turn(note=events or "")
        b.history[-1].coaching_at_time = coaching_used

        return {
            "success": True,
            "turn": b.turn,
            "summary": _short_state_summary(battle_manager),
            "next_step": "Call `suggest_next_move` for the recommendation, or `get_battle_state` for the full snapshot.",
        }

    @mcp.tool()
    async def suggest_next_move() -> dict:
        """Recommend the next turn given the remembered battle state.

        Returns:
            * Top recommendation ("Surging Strikes opp/incineroar; protect Flutter Mane")
            * Reasoning (KO maths, speed matchups, hidden info)
            * Alternatives (2nd / 3rd best plays)
            * Risk callouts (priority moves to watch, Tera scarcity, item triggers)
            * Win-condition assessment

        This tool deliberately calls into existing damage/speed/matchup tools
        rather than re-implementing them — it's an *orchestrator* over the
        remembered state. The actual recommendation phrasing is up to the agent;
        this returns the structured facts it should reason from.
        """
        if not battle_manager.has_active():
            return error_response(
                ErrorCodes.INVALID_PARAMETER,
                "No active battle. Call `start_battle` first.",
            )
        b = battle_manager.require()

        my_on = [p for p in b.my_team if p.on_field and not p.fainted]
        opp_on = [p for p in b.opp_team if p.on_field and not p.fainted]

        # Categorize state for the agent to reason over
        threats: list[dict] = []
        for o in opp_on:
            threat = {
                "pokemon": o.name,
                "hp_percent": o.hp_percent,
                "revealed_item": o.revealed_item,
                "revealed_ability": o.revealed_ability,
                "revealed_moves": o.revealed_moves,
                "has_terastallized": o.has_terastallized,
                "stages": {k: v for k, v in o.stages.items() if v != 0},
                "status": o.status,
            }
            threats.append(threat)

        my_summary: list[dict] = []
        for m in my_on:
            my_summary.append({
                "pokemon": m.name,
                "hp_percent": m.hp_percent,
                "has_terastallized": m.has_terastallized,
                "stages": {k: v for k, v in m.stages.items() if v != 0},
                "status": m.status,
                "booster_energy_spent": m.booster_energy_spent,
            })

        bench = {
            "me": [p.name for p in b.my_team if not p.on_field and not p.fainted],
            "opp": [p.name for p in b.opp_team if not p.on_field and not p.fainted],
        }
        fainted = {
            "me": [p.name for p in b.my_team if p.fainted],
            "opp": [p.name for p in b.opp_team if p.fainted],
        }

        # Tera-availability accounting
        my_tera_used = any(p.has_terastallized for p in b.my_team)
        opp_tera_used = any(p.has_terastallized for p in b.opp_team)

        # Speed-control window awareness
        f = b.field
        speed_control = []
        if f.my_tailwind_turns > 0:
            speed_control.append(f"my Tailwind active ({f.my_tailwind_turns} turns left)")
        if f.opp_tailwind_turns > 0:
            speed_control.append(f"opp Tailwind active ({f.opp_tailwind_turns} turns left)")
        if f.trick_room_turns > 0:
            speed_control.append(f"Trick Room active ({f.trick_room_turns} turns left)")

        # Win-condition heuristic: count remaining vs fainted
        my_alive = sum(1 for p in b.my_team if not p.fainted)
        opp_alive = sum(1 for p in b.opp_team if not p.fainted)
        if my_alive > opp_alive:
            position = "ahead"
        elif my_alive < opp_alive:
            position = "behind"
        else:
            position = "even"

        return {
            "success": True,
            "turn": b.turn,
            "position": position,
            "score": {"me_alive": my_alive, "opp_alive": opp_alive},
            "my_field": my_summary,
            "opp_field": threats,
            "bench": bench,
            "fainted": fainted,
            "field": {
                "weather": f.weather, "weather_turns_left": f.weather_turns_left,
                "terrain": f.terrain, "terrain_turns_left": f.terrain_turns_left,
                "speed_control": speed_control,
                "screens_my": _list_active_screens(f, "me"),
                "screens_opp": _list_active_screens(f, "opp"),
            },
            "tera_available": {
                "me": not my_tera_used,
                "opp": not opp_tera_used,
            },
            "recommendation_seed": _recommendation_seed(b, my_on, opp_on, my_tera_used),
            "agent_instruction": (
                "Use this snapshot as ground truth. Call `calculate_damage_output` "
                "or `analyze_speed_matchup` for any specific KO maths you need to "
                "justify the recommendation. Pay attention to revealed_item / "
                "revealed_ability — never assume hidden info. Tera availability "
                "is binding (one Tera per side per battle). End with: "
                "'Lead action: <move targets>; Bench plan: <next switch-in>; "
                "Risk: <opp's most dangerous response>.'"
            ),
        }

    @mcp.tool()
    async def get_battle_state() -> dict:
        """Return the full structured snapshot of the active battle."""
        if not battle_manager.has_active():
            return error_response(
                ErrorCodes.INVALID_PARAMETER,
                "No active battle. Call `start_battle` first.",
            )
        return {"success": True, **battle_manager.serialize()}

    @mcp.tool()
    async def end_battle(outcome: str = "unknown", notes: str = "") -> dict:
        """Close the active battle and return its final state.

        Args:
            outcome: "win" | "loss" | "draw" | "unknown".
            notes: Free-form post-game notes for the agent's coaching summary.

        Returns the archived battle plus a coaching summary template the agent
        should fill in (key turning points, what worked, what to revisit).
        """
        if not battle_manager.has_active():
            return error_response(
                ErrorCodes.INVALID_PARAMETER,
                "No active battle.",
            )
        snapshot = battle_manager.serialize()
        battle_manager.end()
        return {
            "success": True,
            "outcome": outcome,
            "notes": notes,
            "final_state": snapshot,
            "post_game_template": [
                "1. Win condition we played around: ...",
                "2. Most impactful turn: ...",
                "3. Biggest read we hit / missed: ...",
                "4. What we'd do differently: ...",
                "5. Tech to remember for this opponent: ...",
            ],
        }


# ───────────────────────── helpers ─────────────────────────

def _short_state_summary(mgr: BattleStateManager) -> str:
    b = mgr.require()
    my = " / ".join(
        f"{p.name} ({int(p.hp_percent)}%{'/'+p.status if p.status else ''})"
        for p in b.my_team if p.on_field and not p.fainted
    )
    opp = " / ".join(
        f"{p.name} ({int(p.hp_percent)}%{'/'+p.status if p.status else ''})"
        for p in b.opp_team if p.on_field and not p.fainted
    )
    return f"Turn {b.turn}: ME [{my}] vs OPP [{opp}]"


def _list_active_screens(f, side: str) -> list[str]:
    out = []
    prefix = "my" if side == "me" else "opp"
    for kind in ("reflect", "light_screen", "aurora_veil"):
        attr = f"{prefix}_{kind}_turns"
        turns = getattr(f, attr, 0)
        if turns > 0:
            out.append(f"{kind.replace('_','-')} ({turns} turns)")
    return out


def _recommendation_seed(b, my_on, opp_on, my_tera_used: bool) -> dict:
    """Produce structured recommendation hints the agent can prioritize."""
    hints: list[str] = []
    # Threat HP hints
    for o in opp_on:
        if 0 < o.hp_percent <= 30:
            hints.append(f"Finish opp/{o.name} — {o.hp_percent:.0f}% HP, in range of priority.")
        elif 30 < o.hp_percent <= 55:
            hints.append(f"Pressure opp/{o.name} — {o.hp_percent:.0f}% HP, double-into might KO.")
    # Tera-window hints
    if not my_tera_used:
        for m in my_on:
            if m.hp_percent < 60 and not m.has_terastallized:
                hints.append(
                    f"Consider Tera on me/{m.name} ({m.hp_percent:.0f}% HP) "
                    "if it changes a key matchup defensively."
                )
    # Status hints
    for m in my_on:
        if m.status == "para":
            hints.append(f"me/{m.name} is paralyzed — speed reads are unreliable; consider switching out.")
        if m.status == "burn":
            hints.append(f"me/{m.name} is burned — physical attackers lose 50% damage; pivot if possible.")
    # Field hints
    f = b.field
    if f.opp_tailwind_turns > 0 and f.my_tailwind_turns == 0:
        hints.append("Opp has Tailwind — you're slower; consider Trick Room or switching to bulky pivots.")
    if f.trick_room_turns >= 3:
        hints.append("Long Trick Room window — slow attackers should sweep now.")

    return {
        "priority_actions": hints,
        "guidance": (
            "Rank moves by: (1) immediate KO, (2) preserves Tera, (3) "
            "denies opp's win condition, (4) generates double-up momentum."
        ),
    }
