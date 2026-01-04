"""VGC MCP Micro - Minimal 5-tool server for rate-limited environments."""

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient

from .tools.core_tools import register_core_tools

# Create MCP server with minimal description
mcp = FastMCP(
    "VGC Micro",
    instructions="5 essential VGC tools: damage calc, spreads, speed, usage data"
)

# Initialize API clients
pokeapi = PokeAPIClient()
smogon = SmogonStatsClient()

# Register the 5 core tools
register_core_tools(mcp, pokeapi, smogon)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
