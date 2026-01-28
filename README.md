# VGC MCP Server

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

A Model Context Protocol (MCP) server providing 157+ tools for competitive Pokemon VGC (Video Game Championships) team building.

**New to MCP?** Read the [Technical Guide](TECHNICAL_GUIDE.md) for a beginner-friendly explanation.

## Features

- **157+ specialized tools** for competitive VGC team building
- **Full Gen 9 damage formula** with all modifiers verified against Pokemon Showdown
- **Auto-fetch spreads** from Smogon Stats (1760 ELO)
- **Multi-threat optimization** - survive 3-6 attacks simultaneously
- **Complete Tera mechanics** including Stellar type
- **Showdown paste export** for all spreads
- **Works on FREE Claude Desktop** - no premium required!

## Quick Start

**5-Minute Setup for FREE Claude Desktop:**

1. Install Python 3.11+ from https://python.org
2. Install package: `pip install -e .`
3. Add to Claude Desktop config (see [Setup Guide](SETUP_GUIDE.md))
4. Restart Claude Desktop
5. Ask: "Does Flutter Mane OHKO Incineroar?" 🚀

**Windows users:** Double-click `setup.bat` for automatic setup!

**Detailed Instructions:**
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Choose local (free) or remote (premium) setup
- [LOCAL_SETUP.md](LOCAL_SETUP.md) - Step-by-step local installation
- [USER_GUIDE.md](USER_GUIDE.md) - How to use the tools

## Documentation

### For Users
- **[Setup Guide](SETUP_GUIDE.md)** - Get started with FREE Claude Desktop
- **[User Guide](USER_GUIDE.md)** - How to use VGC tools effectively
- **[FAQ](FAQ.md)** - Common questions and troubleshooting
- **[API Reference](API_REFERENCE.md)** - Complete tool catalog

### For Developers
- **[Technical Guide](TECHNICAL_GUIDE.md)** - MCP architecture explained (beginner-friendly!)
- **[Development Guide](DEVELOPMENT.md)** - Contributing code
- **[Deployment Guide](DEPLOYMENT.md)** - Self-hosting options
- **[Contributing](CONTRIBUTING.md)** - How to contribute

## Example Usage

```
You: "Does my Flutter Mane OHKO Incineroar with Moonblast?"

Claude: "Your Timid 252 SpA Flutter Mane with Moonblast deals 96.5-113.6%
to standard Adamant 252 HP / 60 SpD Incineroar @ Assault Vest.

Result: 75% chance to OHKO (12 out of 16 damage rolls will KO)

Here's the Showdown paste for your Flutter Mane:
```
Flutter Mane
Ability: Protosynthesis
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
```
"
```

## Server Variants

| Server | Tools | Best For |
|--------|-------|----------|
| `vgc-mcp` | 157 | Claude, GPT-4 (full feature set) |
| `vgc-mcp-lite` | 49 | Smaller models, essential tools only |
| `vgc-mcp-micro` | 15 | Minimal deployment, core features |

## Deployment Options

| Option | Setup Time | Cost | Best For |
|--------|------------|------|----------|
| **Local** | 5 min | Free | Individual use (recommended) |
| **Docker** | 10 min | Hosting | Reproducible deployments |
| **Fly.io** | 15 min | $5-20/mo | Production, auto-scaling |
| **Render** | 10 min | Free tier | Quick prototyping |

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

## Key Capabilities

### Damage Calculations
- Full Gen 9 damage formula (100% accurate vs Showdown)
- Auto-fetch common spreads from Smogon
- Multi-hit moves (Surging Strikes, Population Bomb)
- Tera mechanics, weather, terrain, abilities

### EV Optimization
- Find minimum EVs to survive specific attacks
- Optimize for 3-6 threats simultaneously
- Nature optimization to save EVs
- Bulk calculations with diminishing returns

### Speed Analysis
- Compare speeds with Tailwind/Trick Room
- Speed tier visualization
- Probability of outspeeding (based on usage data)

### Team Building
- Import/export Showdown paste format
- Team analysis (coverage, weaknesses, threats)
- Teammate recommendations
- VGC legality checking (Reg F/G/H)

## Development

```bash
# Install for development
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Code quality
ruff check src/
ruff format src/
mypy src/vgc_mcp
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development guide.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code style guidelines
- Testing requirements
- Pull request process

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and recent updates.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Questions?** See [FAQ.md](FAQ.md)
- **Bug reports:** [Open an issue](https://github.com/MSS23/vgc-mcp/issues)
- **Discussions:** [GitHub Discussions](https://github.com/MSS23/vgc-mcp/discussions)

---

**Built with MCP** | Learn more at [modelcontextprotocol.io](https://modelcontextprotocol.io/)
