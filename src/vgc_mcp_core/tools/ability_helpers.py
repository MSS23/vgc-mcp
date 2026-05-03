"""Shared ability-resolution and Intimidate-handling helpers.

Many MCP tools build `PokemonBuild` objects for damage calc but never set
`ability=` on them, which silently drops every offensive AND defensive ability
the engine knows about (Multiscale, Ice Scales, Thick Fat, Fluffy, Filter,
Levitate, Flash Fire, Sheer Force, Adaptability, Tough Claws, Aerilate, Tinted
Lens, etc.). The damage engine in `calc/damage.py` auto-applies all of these
when `attacker.ability` / `defender.ability` are populated — see
`calculate_damage` lines 544-547.

These helpers give every tool a one-liner to:
  1. Resolve a Pokemon's competitive ability (mega-form > Smogon usage > pokeapi).
  2. Compute the Intimidate stat-stage event for physical attacks, accounting
     for attacker-side blockers (Clear Body, Inner Focus, Hyper Cutter, etc.)
     and punishers (Defiant, Contrary, Competitive).

Intimidate is special-cased because it is a switch-in *event* that lowers a
stat stage; the engine cannot infer it passively from the ability name alone.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..calc.abilities import INTIMIDATE_BLOCKERS
from ..calc.mega_evolution import get_mega_ability
from ..utils.normalize import normalize_smogon_name
from .smogon_helpers import get_common_spread

logger = logging.getLogger(__name__)


async def resolve_ability(
    pokemon_name: str,
    *,
    pokeapi: Any,
    smogon_client: Optional[Any] = None,
    user_override: Optional[str] = None,
    use_smogon: bool = True,
) -> tuple[Optional[str], str]:
    """Resolve a Pokemon's competitive ability.

    Resolution order:
      1. `user_override` — explicit user input wins.
      2. Mega-form lookup — Mega Manectric → Intimidate, etc.
      3. Smogon's most-used ability (matches VGC reality, e.g. Dragonite's
         Multiscale rather than pokeapi's first-listed Inner Focus).
      4. PokeAPI's first-listed ability — fallback.

    Returns `(ability_name, source)` where source is one of "custom",
    "mega-form", "smogon", "pokeapi", or "unknown". The ability string is
    in pokeapi-style hyphen-lowercase (e.g. "sheer-force") when from Smogon
    or pokeapi, but may be Title Case from the mega-form lookup. Callers
    should treat it case-insensitively (the damage engine normalizes).
    """
    if user_override:
        return user_override, "custom"

    mega_ability = get_mega_ability(pokemon_name)
    if mega_ability:
        return mega_ability, "mega-form"

    if use_smogon and smogon_client is not None:
        try:
            spread = await get_common_spread(smogon_client, pokemon_name)
            if spread and spread.get("ability"):
                return normalize_smogon_name(spread["ability"]), "smogon"
        except Exception as e:  # noqa: BLE001
            logger.warning("Smogon ability lookup failed for %s: %s", pokemon_name, e)

    try:
        abilities = await pokeapi.get_pokemon_abilities(pokemon_name)
        if abilities:
            return abilities[0], "pokeapi"
    except Exception as e:  # noqa: BLE001
        logger.warning("PokeAPI ability lookup failed for %s: %s", pokemon_name, e)

    return None, "unknown"


def _normalize(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    return name.lower().replace(" ", "-")


def compute_intimidate_attack_stage(
    *,
    defender_ability: Optional[str],
    attacker_ability: Optional[str],
    is_physical: bool,
    apply: bool = True,
) -> tuple[int, Optional[str]]:
    """Compute the attack-stage modifier from a defender's Intimidate.

    Returns `(attack_stage, note)`. `attack_stage` is added to the modifier's
    `attack_stage` field; `note` is a human-readable string for surfacing in
    the response (None when no Intimidate effect applies).

    Rules:
      - Special moves: Intimidate doesn't drop SpA, no effect.
      - Defender lacks Intimidate: no effect.
      - Attacker has Clear Body / Hyper Cutter / Inner Focus / Oblivious /
        Own Tempo / Scrappy / Full Metal Body / White Smoke / Mirror Armor /
        Guard Dog: blocked, 0.
      - Attacker has Defiant: -1 + 2 = net +1.
      - Attacker has Contrary: Intimidate's -1 reversed to +1.
      - Attacker has Competitive: -1 (Competitive boosts SpA, doesn't help
        physical).
      - Otherwise: -1.
    """
    if not apply:
        return 0, None
    if not is_physical:
        return 0, None
    if _normalize(defender_ability) != "intimidate":
        return 0, None

    atk = _normalize(attacker_ability)
    if atk in INTIMIDATE_BLOCKERS:
        return 0, (
            f"Defender's Intimidate is blocked by attacker's "
            f"{attacker_ability.replace('-', ' ').title()}"
        )
    if atk == "defiant":
        return 1, "Attacker's Defiant: net +1 Atk after Intimidate"
    if atk == "contrary":
        return 1, "Attacker's Contrary: Intimidate reversed to +1 Atk"
    if atk == "competitive":
        return -1, (
            "Defender's Intimidate (-1 Atk). Attacker's Competitive boosts "
            "SpA but does not affect this physical move."
        )
    return -1, "Defender's Intimidate (-1 attacker Atk)"


def compute_static_attacker_stat_stages(
    *,
    attacker_ability: Optional[str],
    attacker_name: Optional[str] = None,
    is_physical: bool = True,
    tera_active: bool = False,
) -> tuple[int, int, Optional[str]]:
    """Compute auto-applicable attacker stat stages from the attacker's own ability.

    Models switch-in / Tera-on stat stages that are mechanically guaranteed
    when the ability is present, the same way Intimidate is modelled on the
    defender side.

    Currently handled:
      - Intrepid Sword: +1 Atk on switch-in (Zacian-Crowned)
      - Dauntless Shield: +1 Def on switch-in (Zamazenta-Crowned, defensive only;
        does not affect offensive damage so we report it but don't apply)
      - Embody Aspect (Hearthflame): +1 Atk on Tera (Ogerpon-Hearthflame)
      - Embody Aspect (Wellspring): +1 SpD on Tera (no offensive effect)
      - Embody Aspect (Cornerstone): +1 Def on Tera (no offensive effect)
      - Embody Aspect (Teal): +1 Speed on Tera (no offensive effect)

    Returns `(attack_stage, special_attack_stage, note)`. Stages stack additively
    with caller-supplied stages and with defender Intimidate.
    """
    if not attacker_ability:
        return 0, 0, None
    ab = _normalize(attacker_ability)
    name = (attacker_name or "").lower().replace(" ", "-")

    if ab == "intrepid-sword":
        return 1, 0, "Attacker's Intrepid Sword: +1 Atk on switch-in"
    if ab == "embody-aspect-hearthflame" or (ab == "embody-aspect" and "hearthflame" in name):
        if tera_active:
            return 1, 0, "Embody Aspect (Hearthflame): +1 Atk on Tera"
    if ab == "embody-aspect-teal" or (ab == "embody-aspect" and "teal" in name):
        # Speed boost — not directly relevant to damage modifiers, but worth surfacing
        if tera_active:
            return 0, 0, "Embody Aspect (Teal): +1 Speed on Tera (no damage effect)"
    return 0, 0, None


async def resolve_attacker_and_defender_abilities(
    *,
    attacker_name: str,
    defender_name: str,
    pokeapi: Any,
    smogon_client: Optional[Any] = None,
    attacker_override: Optional[str] = None,
    defender_override: Optional[str] = None,
    use_smogon: bool = True,
) -> dict:
    """Convenience wrapper resolving both sides in one call.

    Returns dict with keys: `attacker_ability`, `attacker_ability_source`,
    `defender_ability`, `defender_ability_source`.
    """
    atk_ab, atk_src = await resolve_ability(
        attacker_name,
        pokeapi=pokeapi,
        smogon_client=smogon_client,
        user_override=attacker_override,
        use_smogon=use_smogon,
    )
    def_ab, def_src = await resolve_ability(
        defender_name,
        pokeapi=pokeapi,
        smogon_client=smogon_client,
        user_override=defender_override,
        use_smogon=use_smogon,
    )
    return {
        "attacker_ability": atk_ab,
        "attacker_ability_source": atk_src,
        "defender_ability": def_ab,
        "defender_ability_source": def_src,
    }
