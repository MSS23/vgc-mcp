"""Battle state manager for live game-coaching workflows.

Holds the state of an in-progress VGC match so the agent can give
turn-by-turn coaching that depends on remembering:

- Each Pokémon's HP %, status, stat stages
- Active conditions: weather, terrain, screens, Tailwind / Trick Room timers
- Items revealed, abilities revealed (the opponent's hidden info)
- Field hazards (sticky web, etc. — niche in VGC but tracked)
- Per-Pokémon flags: Choice locked move, has Terastallized, Booster Energy spent
- Turn history so the agent can review prior decisions

The manager doesn't simulate damage — it just remembers facts. The
existing damage / speed / matchup tools are called against this state
to produce coaching output.

Concurrency model: single-session, single-user. Mirrors BuildStateManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as df_field
from typing import Optional


@dataclass
class PokemonBattleState:
    """Per-Pokémon mutable state inside an active battle."""

    name: str
    side: str  # "me" or "opp"
    slot: int  # 0..5 (party order)
    hp_percent: float = 100.0
    status: Optional[str] = None  # "burn" | "poison" | "para" | "sleep" | "frozen"
    stages: dict[str, int] = df_field(
        default_factory=lambda: {
            "attack": 0, "defense": 0,
            "special_attack": 0, "special_defense": 0,
            "speed": 0, "accuracy": 0, "evasion": 0,
        }
    )
    revealed_item: Optional[str] = None
    revealed_ability: Optional[str] = None
    revealed_moves: list[str] = df_field(default_factory=list)
    revealed_tera_type: Optional[str] = None
    has_terastallized: bool = False
    booster_energy_spent: bool = False
    choice_locked_move: Optional[str] = None
    on_field: bool = False
    fainted: bool = False


@dataclass
class FieldState:
    """Field-wide conditions in an active battle."""

    weather: Optional[str] = None       # "rain" | "sun" | "sand" | "snow"
    weather_turns_left: int = 0
    terrain: Optional[str] = None       # "grassy" | "psychic" | "electric" | "misty"
    terrain_turns_left: int = 0
    my_tailwind_turns: int = 0
    opp_tailwind_turns: int = 0
    trick_room_turns: int = 0
    my_reflect_turns: int = 0
    my_light_screen_turns: int = 0
    opp_reflect_turns: int = 0
    opp_light_screen_turns: int = 0
    my_aurora_veil_turns: int = 0
    opp_aurora_veil_turns: int = 0
    sticky_web_my_side: bool = False
    sticky_web_opp_side: bool = False


@dataclass
class TurnRecord:
    """A single turn's recorded events for replay / review."""

    turn: int
    my_lead: tuple[str, str]
    opp_lead: tuple[str, str]
    notes: str = ""              # free-form user description of what happened
    moves_used: list[str] = df_field(default_factory=list)
    coaching_at_time: str = ""   # what the agent recommended


@dataclass
class BattleState:
    """One active battle's full state."""

    battle_id: str
    format: str = "reg_h"            # active VGC regulation
    turn: int = 1
    my_team: list[PokemonBattleState] = df_field(default_factory=list)
    opp_team: list[PokemonBattleState] = df_field(default_factory=list)
    field: FieldState = df_field(default_factory=FieldState)
    history: list[TurnRecord] = df_field(default_factory=list)
    notes: str = ""

    def find(self, side: str, name: str) -> Optional[PokemonBattleState]:
        team = self.my_team if side == "me" else self.opp_team
        target = name.lower().replace(" ", "-").strip()
        # exact then prefix match
        for p in team:
            if p.name.lower() == target:
                return p
        for p in team:
            if p.name.lower().startswith(target) or target in p.name.lower():
                return p
        return None


class BattleStateManager:
    """Manages one active battle (single-session)."""

    def __init__(self) -> None:
        self._battle: Optional[BattleState] = None
        self._counter = 0

    @property
    def active(self) -> Optional[BattleState]:
        return self._battle

    def has_active(self) -> bool:
        return self._battle is not None

    def start(
        self,
        my_team_names: list[str],
        opp_team_names: list[str],
        format: str = "reg_h",
    ) -> BattleState:
        """Begin a new battle, replacing any in-flight one."""
        self._counter += 1
        battle_id = f"battle_{self._counter}"
        self._battle = BattleState(
            battle_id=battle_id,
            format=format,
            my_team=[
                PokemonBattleState(name=n, side="me", slot=i)
                for i, n in enumerate(my_team_names)
            ],
            opp_team=[
                PokemonBattleState(name=n, side="opp", slot=i)
                for i, n in enumerate(opp_team_names)
            ],
        )
        return self._battle

    def end(self) -> Optional[BattleState]:
        """End the current battle and return the final state."""
        b = self._battle
        self._battle = None
        return b

    def require(self) -> BattleState:
        """Return the active battle or raise."""
        if self._battle is None:
            raise RuntimeError("no active battle — call start_battle first")
        return self._battle

    def update_pokemon(
        self,
        side: str,
        name: str,
        *,
        hp_percent: Optional[float] = None,
        status: Optional[str] = None,
        revealed_item: Optional[str] = None,
        revealed_ability: Optional[str] = None,
        revealed_move: Optional[str] = None,
        revealed_tera_type: Optional[str] = None,
        has_terastallized: Optional[bool] = None,
        on_field: Optional[bool] = None,
        fainted: Optional[bool] = None,
        stage_changes: Optional[dict[str, int]] = None,
    ) -> PokemonBattleState:
        """Apply observed changes to a Pokémon's state."""
        battle = self.require()
        p = battle.find(side, name)
        if p is None:
            raise ValueError(f"{side}'s {name} not in battle")
        if hp_percent is not None:
            p.hp_percent = max(0.0, min(100.0, hp_percent))
            if p.hp_percent == 0.0:
                p.fainted = True
                p.on_field = False
        if status is not None:
            p.status = status if status != "none" else None
        if revealed_item is not None:
            p.revealed_item = revealed_item
        if revealed_ability is not None:
            p.revealed_ability = revealed_ability
        if revealed_move and revealed_move not in p.revealed_moves:
            p.revealed_moves.append(revealed_move)
        if revealed_tera_type is not None:
            p.revealed_tera_type = revealed_tera_type
        if has_terastallized is not None:
            p.has_terastallized = has_terastallized
        if on_field is not None:
            p.on_field = on_field
        if fainted is not None:
            p.fainted = fainted
        if stage_changes:
            for stat, delta in stage_changes.items():
                if stat in p.stages:
                    p.stages[stat] = max(-6, min(6, p.stages[stat] + delta))
        return p

    def advance_turn(self, note: str = "") -> int:
        """Tick to the next turn; auto-decay timed conditions; record history entry."""
        b = self.require()
        # Decay timers
        f = b.field
        for attr in (
            "weather_turns_left", "terrain_turns_left",
            "my_tailwind_turns", "opp_tailwind_turns", "trick_room_turns",
            "my_reflect_turns", "my_light_screen_turns",
            "opp_reflect_turns", "opp_light_screen_turns",
            "my_aurora_veil_turns", "opp_aurora_veil_turns",
        ):
            cur = getattr(f, attr)
            if cur > 0:
                setattr(f, attr, cur - 1)
        if f.weather_turns_left == 0:
            f.weather = None
        if f.terrain_turns_left == 0:
            f.terrain = None

        # Snapshot turn
        my_on = [p.name for p in b.my_team if p.on_field]
        opp_on = [p.name for p in b.opp_team if p.on_field]
        b.history.append(
            TurnRecord(
                turn=b.turn,
                my_lead=(my_on[0] if my_on else "?", my_on[1] if len(my_on) > 1 else "?"),
                opp_lead=(opp_on[0] if opp_on else "?", opp_on[1] if len(opp_on) > 1 else "?"),
                notes=note,
            )
        )
        b.turn += 1
        return b.turn

    def serialize(self) -> dict:
        """Return a JSON-safe dict of the current battle state."""
        b = self.require()

        def p2d(p: PokemonBattleState) -> dict:
            return {
                "name": p.name,
                "slot": p.slot,
                "hp_percent": p.hp_percent,
                "status": p.status,
                "stages": p.stages,
                "revealed_item": p.revealed_item,
                "revealed_ability": p.revealed_ability,
                "revealed_moves": p.revealed_moves,
                "revealed_tera_type": p.revealed_tera_type,
                "has_terastallized": p.has_terastallized,
                "booster_energy_spent": p.booster_energy_spent,
                "choice_locked_move": p.choice_locked_move,
                "on_field": p.on_field,
                "fainted": p.fainted,
            }

        return {
            "battle_id": b.battle_id,
            "format": b.format,
            "turn": b.turn,
            "field": {
                "weather": b.field.weather,
                "weather_turns_left": b.field.weather_turns_left,
                "terrain": b.field.terrain,
                "terrain_turns_left": b.field.terrain_turns_left,
                "my_tailwind_turns": b.field.my_tailwind_turns,
                "opp_tailwind_turns": b.field.opp_tailwind_turns,
                "trick_room_turns": b.field.trick_room_turns,
                "my_reflect_turns": b.field.my_reflect_turns,
                "my_light_screen_turns": b.field.my_light_screen_turns,
                "opp_reflect_turns": b.field.opp_reflect_turns,
                "opp_light_screen_turns": b.field.opp_light_screen_turns,
                "my_aurora_veil_turns": b.field.my_aurora_veil_turns,
                "opp_aurora_veil_turns": b.field.opp_aurora_veil_turns,
            },
            "my_team": [p2d(p) for p in b.my_team],
            "opp_team": [p2d(p) for p in b.opp_team],
            "history": [
                {"turn": h.turn, "my_lead": list(h.my_lead),
                 "opp_lead": list(h.opp_lead), "notes": h.notes,
                 "moves_used": h.moves_used,
                 "coaching_at_time": h.coaching_at_time}
                for h in b.history
            ],
        }
