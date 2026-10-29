"""Response-contract helpers for spread design and preparation calc tools.

Headlines lead with the designed build ("Bold 252/0/4/0/252/0 Amoonguss") and
then the verdicts, e.g. "... survives Incineroar's Flare Blitz (78-92%) and
outspeeds Tornadus". See response_contract for the four contract fields.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from ..formats.showdown import format_showdown_species
from ..models.pokemon import PokemonBuild
from .response_contract import apply_contract, data_source_from_meta, spread_label

__all__ = [
    "apply_contract", "attackers", "benchmark_parts", "contract", "data_source_from_meta",
    "first_meta", "hit_part", "species", "speed_part", "spread_label", "subject", "words",
]


def subject(build: PokemonBuild) -> str:
    """Nature, allocation and species without item/ability."""
    return spread_label(build.model_copy(update={"item": None, "ability": None}))


def species(name: str) -> str:
    return format_showdown_species(name)


def words(name: str) -> str:
    return name.replace("-", " ").title()


def hit_part(attacker: str, move: str, survives: bool, damage: Optional[str] = None) -> str:
    text = f"{'survives' if survives else 'does not survive'} {species(attacker)}'s {words(move)}"
    return f"{text} ({damage})" if damage else text


def speed_part(target: str, outspeeds: bool) -> str:
    return f"{'outspeeds' if outspeeds else 'does not outspeed'} {species(target)}"


def benchmark_parts(benchmarks: Any) -> list[str]:
    """Verdict phrases from a design_spread_with_benchmarks 'benchmarks' block."""
    parts = []
    survival = benchmarks.get("survival") or {}
    if "survives" in survival:
        damage = survival.get("damage_percent") or (
            f"max {survival['max_percent']:.1f}%" if "max_percent" in survival else None)
        parts.append(hit_part(survival["attacker"], survival["move"], survival["survives"], damage))
    speed = benchmarks.get("speed") or {}
    if "outspeeds" in speed:
        parts.append(speed_part(speed["target"], speed["outspeeds"]))
    return parts


def attackers(builds: Sequence[PokemonBuild]) -> dict[str, PokemonBuild]:
    if len(builds) == 1:
        return {"attacker": builds[0]}
    return {f"attacker_{i}": b for i, b in enumerate(builds, 1)}


def first_meta(metas: Iterable[Optional[dict[str, Any]]]) -> Optional[dict[str, Any]]:
    return next((m for m in metas if m), None)


def contract(
    result: dict[str, Any],
    build: PokemonBuild,
    parts: list[str],
    others: dict[str, PokemonBuild],
    metas: Iterable[Optional[dict[str, Any]]] = (),
    *,
    item: Optional[str] = None,
    ability: Optional[str] = None,
    key: str = "pokemon",
) -> dict[str, Any]:
    """Apply the contract for a result whose subject is `build`.

    item/ability fill gaps on the label when the paste build omits them.
    """
    labelled = build.model_copy(update={"item": build.item or item, "ability": build.ability or ability})
    headline = f"{subject(build)} " + (" and ".join(parts) if parts else "spread")
    return apply_contract(
        result,
        headline=headline,
        spreads_used={key: spread_label(labelled), **{k: spread_label(b) for k, b in others.items()}},
        data_source=data_source_from_meta(first_meta(metas)),
        showdown_paste=result.get("showdown_paste"),
    )
