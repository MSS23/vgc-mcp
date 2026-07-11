"""Stat calculator for Pokemon Champions VGC (Reg MA/MB, level 50).

Champions uses Stat Points (SPs) instead of EVs:
- 0-32 per stat, 66 total budget across all six stats
- Natures ("Stat Alignments" in-game) apply the standard +10%/-10%
- IVs do not exist in Champions: every Pokemon behaves as if it has 31 IVs
  in all six stats, and they cannot be lowered (no 0-Spe Trick Room or
  0-Atk confusion tech). The `iv` parameters below default to 31 and should
  stay there for real Champions builds; they exist only for formula parity.
- Damage formula is otherwise identical to mainline Gen 9

Formula
-------
Bulbapedia (https://bulbapedia.bulbagarden.net/wiki/Stat) gives the official
Champions closed form at level 50:

    HP   = Base + SP + 75
    Stat = floor((Base + SP + 20) * Alignment)     Alignment in {0.9, 1.0, 1.1}

This is bit-for-bit identical to substituting `SP*2` into the `floor(EV/4)`
slot of the mainline Gen 3+ formula with IV=31 (2*Base+31 is odd, so
floor((2B+31+2n)*0.5) = B+15+n). Equivalences that follow:
- 1 SP = +1 pre-nature stat point = 8 EVs of effectiveness at level 50
- 32 SP is EXACTLY 252 EVs (252 and 256 EVs floor to the same stat)
- Pokemon HOME transfer conversion: SP = (EVs + 4) / 8
- 66 SP total ~= 528 EV-equivalent, slightly above mainline's 508

Parity check: Flutter Mane (base 135 Spe), Timid, 32 SP ->
floor((135+32+20) * 1.1) = 205, identical to mainline Timid 252 Spe.

Generalized formulas used here (any level, IV kept for parity testing):
- HP: floor((2*Base + IV + 2*SP) * Level/100 + Level + 10)
- Other: floor((floor((2*Base + IV + 2*SP) * Level/100) + 5) * Nature)
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
