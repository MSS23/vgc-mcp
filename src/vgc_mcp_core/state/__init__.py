# -*- coding: utf-8 -*-
"""State management for VGC builds.

Provides BuildStateManager for tracking Pokemon builds across tool calls,
enabling bidirectional sync between UI and chat commands.
"""

from .battle_manager import (
    BattleState,
    BattleStateManager,
    FieldState,
    PokemonBattleState,
    TurnRecord,
)
from .build_manager import BuildStateManager

__all__ = [
    "BuildStateManager",
    "BattleStateManager",
    "BattleState",
    "PokemonBattleState",
    "FieldState",
    "TurnRecord",
]
