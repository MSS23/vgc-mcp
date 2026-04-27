"""Shared helpers for fetching Smogon spread data.

Two near-identical copies of `_get_common_spread` and `_get_common_spreads`
existed in tool files (damage_tools, item_optimization_tools, plus the lite
forks). They're consolidated here.

These are *async* and take an explicit smogon client — no module-level state.
Callers in MCP tool modules can pass their cached `smogon_client` reference
through to these helpers.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..utils.synergies import get_synergy_ability

logger = logging.getLogger(__name__)


async def get_common_spreads(
    smogon_client: Optional[Any], pokemon_name: str, limit: int = 3
) -> list[dict]:
    """Fetch the top `limit` common spreads for a Pokemon from Smogon usage stats.

    Each spread dict includes `rank`, `nature`, `evs`, `usage`, `item`,
    `item_usage`, `ability`, `ability_usage`. Item/ability are derived from
    the top usage of each, with item-ability synergy applied (e.g. Life Orb
    pulls Sheer Force when the Pokemon learns it).

    Returns an empty list if the smogon client is None, the Pokemon is not in
    usage data, or the request fails. Errors are logged at WARNING level so
    callers don't need to wrap this in try/except.
    """
    if smogon_client is None:
        return []
    try:
        usage = await smogon_client.get_pokemon_usage(pokemon_name)
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to fetch Smogon spreads for %s: %s", pokemon_name, e)
        return []

    if not usage or not usage.get("spreads"):
        return []

    spreads = usage["spreads"][:limit]
    items = usage.get("items", {})
    abilities = usage.get("abilities", {})
    top_item = next(iter(items), None)
    top_item_usage = items[top_item] if top_item else 0

    # Item-ability synergy (e.g., Life Orb -> Sheer Force when the Pokemon has it)
    top_ability, top_ability_usage = get_synergy_ability(top_item, abilities)

    return [
        {
            "rank": i + 1,
            "nature": spread.get("nature", "Serious"),
            "evs": spread.get("evs", {}),
            "usage": spread.get("usage", 0),
            "item": top_item,
            "item_usage": top_item_usage,
            "ability": top_ability,
            "ability_usage": top_ability_usage,
        }
        for i, spread in enumerate(spreads)
    ]


async def get_common_spread(
    smogon_client: Optional[Any], pokemon_name: str
) -> Optional[dict]:
    """Fetch the single most common spread for a Pokemon. None if not found."""
    spreads = await get_common_spreads(smogon_client, pokemon_name, limit=1)
    return spreads[0] if spreads else None
