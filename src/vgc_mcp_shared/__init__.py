"""VGC MCP Shared - Shared MCP tool implementations for VGC servers.

This package contains shared MCP tool implementations that can be used by
both the full vgc_mcp server and the lite vgc_mcp_lite server.

Package Architecture:
- vgc_mcp_core: Pure business logic (calc, models, API clients) - no MCP dependency
- vgc_mcp_shared: Shared MCP tool implementations (no UI) - depends on mcp + core
- vgc_mcp: Full server (imports from shared + adds exclusive tools)
- vgc_mcp_lite: Lite server (imports from shared + adds UI wrappers)

This package provides:
- Base tool implementations that can be shared
- Tools are UI-agnostic; UI decorators are added by vgc_mcp_lite

Usage:
    # In vgc_mcp or vgc_mcp_lite:
    from vgc_mcp_shared.tools.stats_tools import register_stats_tools
"""

__version__ = "0.1.0"
