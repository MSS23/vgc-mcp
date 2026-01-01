# -*- coding: utf-8 -*-
"""VGC MCP Core - Shared modules for VGC team building tools.

This package contains the shared functionality used by both vgc_mcp (full)
and vgc_mcp_lite servers.
"""

__version__ = "1.0.0"

# Re-export commonly used items for convenience
from .config import logger, settings
from .models.pokemon import PokemonBuild, Nature, EVSpread, IVSpread, BaseStats
from .models.move import Move, MoveCategory
from .models.team import Team
