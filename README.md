# VGC MCP Server

A Model Context Protocol (MCP) server for Pokemon VGC (Video Game Championships) team building and competitive analysis.

## Features

- **157 tools** for damage calculations, stat analysis, team management
- Full Gen 9 damage formula with all modifiers
- Type effectiveness calculations
- Speed tier analysis
- EV optimization
- Team import/export (Showdown paste format)
- Smogon usage statistics integration

## Installation

```bash
pip install -e .
```

## Usage

### Local (stdio)
```bash
vgc-mcp
```

### Remote (HTTP/SSE)
```bash
pip install -e ".[remote]"
vgc-mcp-http
```

## MCP Endpoint

Connect your MCP client to:
- **SSE**: `https://your-server.com/sse`
- **Health**: `https://your-server.com/health`

## License

MIT
