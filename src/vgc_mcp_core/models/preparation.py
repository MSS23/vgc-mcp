"""Validated inputs and provenance for MCP preparation workflows."""

from dataclasses import dataclass, fields
from typing import Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from ..calc.modifiers import DamageModifiers
from .move import Move
from .pokemon import PokemonBuild

_MODIFIERS_ADAPTER = TypeAdapter(DamageModifiers)


def validated_conditions(conditions: dict[str, Any]) -> DamageModifiers:
    unknown = set(conditions) - {field.name for field in fields(DamageModifiers)}
    if unknown:
        raise ValueError(f"Unknown battle conditions: {', '.join(sorted(unknown))}")
    modifiers = _MODIFIERS_ADAPTER.validate_python(conditions)
    for name in ("attack_stage", "defense_stage", "special_attack_stage", "special_defense_stage", "attacker_defense_stage", "defender_attack_stage"):
        if not -6 <= getattr(modifiers, name) <= 6:
            raise ValueError(f"{name} must be between -6 and +6")
    if not 0 <= modifiers.move_hits <= 10:
        raise ValueError("move_hits must be between 0 (automatic) and 10")
    if modifiers.weather not in (None, "sun", "rain", "sand", "snow", "harsh_sun", "heavy_rain"):
        raise ValueError("Unknown weather")
    if modifiers.terrain not in (None, "electric", "grassy", "psychic", "misty"):
        raise ValueError("Unknown terrain")
    return modifiers


class BenchmarkSpec(BaseModel):
    kind: Literal["survive", "ko", "outspeed"]
    opponent_name: str | None = Field(default=None, description="Fetch this opponent's common chaos spread")
    opponent_paste: str | None = Field(default=None, description="Use this exact complete opponent spread")
    move: str | None = Field(default=None, description="Attacker's move; required for survive/ko")
    probability: float | None = Field(default=None, gt=0, le=100, description="Default: 93.75 survival, 100 KO")
    conditions: dict[str, Any] = Field(default_factory=dict, description="DamageModifiers fields such as weather, attack_stage, or defender_tera_type")
    speed_multiplier: float = Field(default=1, gt=0, le=8, description="Explicit combined multiplier on raw Speed, including items/speed control; not auto-inferred")
    opponent_speed_multiplier: float = Field(default=1, gt=0, le=8, description="Explicit combined multiplier on opponent raw Speed")

    @model_validator(mode="after")
    def require_opponent_and_move(self) -> "BenchmarkSpec":
        if bool(self.opponent_name) == bool(self.opponent_paste):
            raise ValueError("Provide exactly one opponent_name or opponent_paste")
        if self.kind != "outspeed" and not self.move:
            raise ValueError("Damage benchmarks require a move")
        validated_conditions(self.conditions)
        if self.kind == "outspeed" and self.conditions:
            raise ValueError("Speed benchmarks use speed_multiplier fields, not damage conditions")
        return self

    @property
    def required_probability(self) -> float:
        return self.probability if self.probability is not None else (93.75 if self.kind == "survive" else 100)


class SourcedSet(BaseModel):
    pokemon: PokemonBuild
    regulation: str
    source_name: str = Field(min_length=1, max_length=200)
    source_url: str | None = Field(default=None, pattern=r"^https?://")
    source_kind: Literal["user_imported_complete"] = "user_imported_complete"
    source_verified: bool = False


@dataclass(frozen=True)
class ResolvedBenchmark:
    request: BenchmarkSpec
    opponent: PokemonBuild
    move: Move | None
    modifiers: DamageModifiers
    source: dict[str, Any]
