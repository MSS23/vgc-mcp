"""Stat calculator for Pokemon Champions VGC (Reg MA, level 50).

Champions uses Stat Points (SPs) instead of EVs:
- 0-32 per stat, 66 total budget across all six stats
- Natures and IVs still apply (same 25 natures, 0-31 IVs)
- Damage formula is otherwise identical to mainline Gen 9

Formula equivalence
-------------------
We model 1 SP as "8 EVs of effectiveness". The mainline EV slot in the stat
formula is `EV/4`, so substituting SP*8 yields `SP*2`. This places SP=32 at
EV-equivalent 256 (a hair above the 252 mainline cap), which matches
observed values from the NCP calculator.

Level-50 formulas:
- HP: floor((2 * Base + IV + 2 * SP) * 0.5 + 60)
- Other: floor((floor((2 * Base + IV + 2 * SP) * 0.5) + 5) * Nature)
"""

import math
from typing import Optional

from ..models.pokemon import Nature, PokemonBuild, get_nature_modifier


def calculate_hp_sp(
    base: int,
    iv: int = 31,
    sp: int = 0,
    level: int = 50,
) -> int:
    """Calculate HP under the Champions SP system.

    HP = floor((2*Base + IV + 2*SP) * Level/100 + Level + 10)

    Shedinja (base HP 1) always returns 1.
    """
    if base == 1:
        return 1
    return math.floor(
        (2 * base + iv + 2 * sp) * level / 100 + level + 10
    )


def calculate_stat_sp(
    base: int,
    iv: int = 31,
    sp: int = 0,
    level: int = 50,
    nature_mod: float = 1.0,
) -> int:
    """Calculate a non-HP stat under the Champions SP system.

    Stat = floor((floor((2*Base + IV + 2*SP) * Level/100) + 5) * Nature)
    """
    inner = math.floor((2 * base + iv + 2 * sp) * level / 100)
    return math.floor((inner + 5) * nature_mod)


def calculate_speed_sp(
    base_speed: int,
    iv: int = 31,
    sp: int = 0,
    level: int = 50,
    nature: Nature = Nature.SERIOUS,
) -> int:
    """Calculate Speed under the Champions SP system."""
    nature_mod = get_nature_modifier(nature, "speed")
    return calculate_stat_sp(base_speed, iv, sp, level, nature_mod)


def calculate_all_stats_champions(
    pokemon: PokemonBuild,
    level: Optional[int] = None,
) -> dict[str, int]:
    """Calculate all six stats for a Champions Pokemon build.

    Reads from `pokemon.sps` (StatPointSpread). If `pokemon.sps` is None,
    treats all SPs as zero. IVs and nature are read from the build like
    mainline.
    """
    lvl = level if level is not None else pokemon.level
    base = pokemon.base_stats
    sps = pokemon.sps  # may be None for a freshly-imported Pokemon

    def _sp(name: str) -> int:
        return getattr(sps, name, 0) if sps is not None else 0

    return {
        "hp": calculate_hp_sp(base.hp, pokemon.ivs.hp, _sp("hp"), lvl),
        "attack": calculate_stat_sp(
            base.attack,
            pokemon.ivs.attack,
            _sp("attack"),
            lvl,
            pokemon.get_nature_modifier("attack"),
        ),
        "defense": calculate_stat_sp(
            base.defense,
            pokemon.ivs.defense,
            _sp("defense"),
            lvl,
            pokemon.get_nature_modifier("defense"),
        ),
        "special_attack": calculate_stat_sp(
            base.special_attack,
            pokemon.ivs.special_attack,
            _sp("special_attack"),
            lvl,
            pokemon.get_nature_modifier("special_attack"),
        ),
        "special_defense": calculate_stat_sp(
            base.special_defense,
            pokemon.ivs.special_defense,
            _sp("special_defense"),
            lvl,
            pokemon.get_nature_modifier("special_defense"),
        ),
        "speed": calculate_stat_sp(
            base.speed,
            pokemon.ivs.speed,
            _sp("speed"),
            lvl,
            pokemon.get_nature_modifier("speed"),
        ),
    }


# SP breakpoints — every value is a candidate, since SP grain is 1 (vs. EV's 4).
SP_BREAKPOINTS_LV50: list[int] = list(range(0, 33))


def find_speed_sps(
    base_speed: int,
    target_speed: int,
    nature: Nature = Nature.SERIOUS,
    iv: int = 31,
    level: int = 50,
) -> Optional[int]:
    """Find minimum Speed SPs needed to reach a target Speed stat.

    Returns the minimum SP value (0-32) that reaches `target_speed`, or None
    if even 32 SPs with the given nature/IV cannot reach the target.
    """
    for sp in SP_BREAKPOINTS_LV50:
        if calculate_speed_sp(base_speed, iv, sp, level, nature) >= target_speed:
            return sp
    return None
