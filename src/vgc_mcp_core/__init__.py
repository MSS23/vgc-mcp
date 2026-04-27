# -*- coding: utf-8 -*-
"""VGC MCP Core - Shared library for VGC team-building MCP servers.

Contains the calculation engine, data models, API clients, and helpers used
by the plain-MCP `vgc_mcp` server in this repo (and by any MCP-UI sibling
project that wants to reuse the same logic).
"""

__version__ = "1.0.0"

# Re-export commonly used items for convenience
from .config import logger, settings
from .models.pokemon import PokemonBuild, Nature, EVSpread, IVSpread, BaseStats
from .models.move import Move, MoveCategory
from .models.team import Team
