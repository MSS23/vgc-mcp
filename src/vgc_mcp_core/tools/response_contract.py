"""One response contract for calc tools.

Every calc tool returns the same four fields on top of its own payload:

- ``headline``: one sentence under ~120 characters with the verdict. Phones
  show this first.
- ``spreads_used``: the exact sets the numbers came from, one line per side,
  e.g. ``{"attacker": "Adamant 4/252/0/0/0/252 Urshifu @ Choice Scarf"}``.
- ``data_source``: where usage-derived sets came from (chaos month, format,
  rating, stale notice), or ``None`` when every set was user-supplied.
- ``showdown_paste``: a paste the user can copy, when one applies.

``CalcResult`` is the typed output schema for these tools. It allows extra
fields, so a tool keeps its full payload while clients get a machine-checked
shape for the four shared fields. Error responses validate too.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from ..formats.showdown import format_showdown_species
from ..models.pokemon import PokemonBuild

HEADLINE_MAX = 120

_STAT_ORDER = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")


class DataSource(BaseModel):
    """Smogon chaos provenance for usage-derived sets."""

    model_config = ConfigDict(extra="allow")

    format: Optional[str] = None
    month: Optional[str] = None
    rating: Optional[int] = None
    notice: Optional[str] = None


class CalcResult(BaseModel):
    """Output schema shared by calc tools. Extra fields pass through."""

    model_config = ConfigDict(extra="allow")

    success: Optional[bool] = None
    headline: Optional[str] = None
    spreads_used: Optional[dict[str, str]] = None
    data_source: Optional[DataSource] = None
    showdown_paste: Optional[str] = None


def spread_label(build: PokemonBuild) -> str:
    """Compact set line: ``Adamant 4/252/0/0/0/252 Urshifu @ Choice Scarf``.

    Champions builds show Stat Points with an ``SP`` suffix. The ability is
    appended in parentheses when known.
    """
    if build.format_system == "champions" and build.sps is not None:
        values = "/".join(str(getattr(build.sps, s)) for s in _STAT_ORDER) + " SP"
    else:
        values = "/".join(str(getattr(build.evs, s)) for s in _STAT_ORDER)
    nature = build.nature.value.title() if hasattr(build.nature, "value") else str(build.nature)
    label = f"{nature} {values} {format_showdown_species(build.name)}"
    if build.item:
        label += f" @ {_words(build.item)}"
    if build.ability:
        label += f" ({_words(build.ability)})"
    return label


def data_source_from_meta(meta: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Reduce a chaos ``_meta`` dict to the contract's data_source fields."""
    if not meta:
        return None
    source = {
        "format": meta.get("format"),
        "month": meta.get("month"),
        "rating": meta.get("rating"),
        "notice": meta.get("notice"),
    }
    return {k: v for k, v in source.items() if v is not None} or None


def apply_contract(
    result: dict[str, Any],
    *,
    headline: str,
    spreads_used: Optional[dict[str, str]] = None,
    data_source: Optional[dict[str, Any]] = None,
    showdown_paste: Optional[str] = None,
) -> dict[str, Any]:
    """Add the four contract fields to a tool result in place and return it.

    Existing values win for ``data_source`` and ``showdown_paste`` so a tool
    that already set them richly is not overwritten with ``None``.
    """
    result["headline"] = _clip(headline)
    if spreads_used is not None:
        result["spreads_used"] = spreads_used
    if data_source is not None or "data_source" not in result:
        result["data_source"] = data_source if data_source is not None else result.get("data_source")
    if showdown_paste is not None or "showdown_paste" not in result:
        result["showdown_paste"] = (
            showdown_paste if showdown_paste is not None else result.get("showdown_paste")
        )
    return result


def _clip(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= HEADLINE_MAX else text[: HEADLINE_MAX - 1].rstrip() + "…"


def _words(name: str) -> str:
    """'choice-scarf' -> 'Choice Scarf'. Already-spaced display names pass through."""
    if " " in name or any(c.isupper() for c in name):
        return name
    return " ".join(part.capitalize() for part in name.split("-"))
