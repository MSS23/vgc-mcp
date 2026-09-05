# VGC MCP — Pokémon damage calc, spreads, and team coaching for any AI assistant

> **Showdown-accurate damage calcs, EV optimization, and a live battle copilot — over MCP. Plug into Claude Desktop, ChatGPT, or any MCP-compatible client and ask in plain English.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![Live](https://img.shields.io/badge/live-vgc--mcp.onrender.com-brightgreen)](https://vgc-mcp.onrender.com/health)
[![Tests](https://img.shields.io/badge/tests-1493%20passing-success)](#)
[![Tools](https://img.shields.io/badge/MCP%20tools-208-blueviolet)](docs/tools-catalog.md)

A **Model Context Protocol** server that turns any LLM into a competitive Pokémon VGC coach. **208 tools** spanning the full Gen 9 damage formula, Smogon usage data, multi-threat EV optimization, replay analysis, and a turn-by-turn live battle copilot.

```
You:    Does Tera-Normal Entei live a Sheer-Force Life-Orb Earth Power
        from Timid 252 SpA Landorus, after one chip of Life Orb damage?

Claude: [calls calculate_damage_output once]

        | Side     | Pokémon  | Nature  | EVs            | Item        | Tera   |
        |----------|----------|---------|----------------|-------------|--------|
        | Attacker | Landorus | Timid   | 0/0/0/252/4/252| Life Orb    | —      |
        | Defender | Entei    | Adamant | 4/252/0/0/0/252| Choice Band | Normal |

        | Move        | Damage  | % HP        | Verdict @ 90% HP             |
        |-------------|---------|-------------|------------------------------|
        | Earth Power | 149-177 | 78.4-93.1%  | 75% survival (12/16 rolls)   |
```

---

## Why this exists

Every VGC team-builder is a wall of UI: type into a calculator, copy-paste a paste, click through tabs, run again. **VGC MCP collapses that loop into a conversation.** Claude does the calc, picks the right tool from 208 (damage, speed, survival, replay, breakpoints, archetype, live battle), and renders results as scannable tables — not prose.

**Built for:**
- 🏆 **Competitive players** — pre-tournament prep, live in-game coaching, post-game replay analysis
- 🛠 **Team builders** — multi-threat survival optimization, breakpoint finding, build deltas
- 📚 **Newcomers** — explain VGC terms, show legal sets, suggest archetypes

---

## What you get

**🧮 Damage calculations** — Full Gen 9 formula, [verified against Pokémon Showdown's calc](#correctness). Tera, Life Orb, Sheer Force stacking, Ruin abilities, screens, weather, terrain, multi-hit moves, always-crit moves, item-ability synergies, prior chip damage. *One tool call answers questions other calculators need three for.*

**📊 EV optimization** — Find minimum EVs to outspeed / OHKO / survive. Optimize against **3–6 threats simultaneously**. Auto-pick the optimal nature. Showdown paste in every output, ready to copy.

**⚡ Live battle copilot** — `start_battle` → `record_turn` → `suggest_next_move`. Persistent state (HP%, status, stat stages, revealed items/abilities, Tera usage, weather/screen timers) across turns so the agent coaches you between turns.

**📼 Replay analyzer** — Paste a `replay.pokemonshowdown.com` URL. Get turn-by-turn breakdown, key moments (KOs, Tera timing, weather wars), and concrete coaching takeaways.

**🎯 Smart routing** — `what_tool_should_i_use(question)` cuts through 208 tools when the agent is unsure. Spread iteration deltas, archetype classification, breakpoint Pareto-optimal options.

**🌐 Live and free** — Hosted at `https://vgc-mcp.onrender.com/mcp` (Streamable HTTP; legacy SSE at `/sse`) ready for any MCP-compatible client.

[**→ Browse the full 208-tool catalog**](docs/tools-catalog.md)

---

## Install in 30 seconds

### Option A — Hosted (zero install)

In **Claude.ai → Settings → Connectors → Add custom connector**, paste:

```
https://vgc-mcp.onrender.com/mcp
```

Start a new chat. Done. (Older clients that only speak the legacy HTTP+SSE
transport can use `https://vgc-mcp.onrender.com/sse` instead.)

> **Note:** the free hosting tier sleeps after ~15 min idle — the first
> request after a quiet period can take 30-60 s to wake the server. Retry
> once if the initial connection stalls.

### Option B — Local (Claude Desktop, free)

```bash
git clone https://github.com/MSS23/vgc-mcp.git
cd vgc-mcp
pip install -e .
```

Add to your Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "vgc": { "command": "vgc-mcp" }
  }
}
```

Restart Claude Desktop. Done. **[Full setup guide →](docs/setup.md)**

### Option C — Self-host

```bash
docker run -p 8000:8000 ghcr.io/mss23/vgc-mcp:latest
# or: render / fly.io / heroku — see docs/deploy.md
```

---

## Try these prompts

```
"Does my Flutter Mane OHKO Incineroar with Moonblast?"

"What EVs does Ogerpon-Hearthflame need to survive
 Choice Scarf Adamant Urshifu's Surging Strikes 93.75% of the time?"

"What's the cheapest spread for Entei to outspeed Choice Scarf Incineroar?
 Show me the +Speed and neutral options."

"Compare Tera Fairy vs Tera Fire on Ogerpon-Hearthflame against
 Urshifu-Rapid-Strike, Flutter Mane, and Rillaboom."

"I'm starting a VGC match. My team is [paste]. Their preview shows
 [4 Pokémon]. I'm leading [X, Y]. They're leading [A, B]. What now?"

"Analyze this replay and tell me what the loser could have done
 differently: https://replay.pokemonshowdown.com/<id>"
```

---

## Correctness

Damage calc is verified against **Pokémon Showdown** — the source of truth used by every major calculator (`@pkmn/calc`). Live test on the very first prompt above:

| Source            | Damage    | Percent       | Verdict           |
|-------------------|-----------|---------------|-------------------|
| Pokémon Showdown  | 149-177   | 78.4 - 93.1%  | guaranteed 2HKO   |
| **VGC MCP**       | **149-177** | **78.4-93.1%** | **guaranteed 2HKO** |

The test suite covers Gen 9 damage, stats, items, abilities, Tera, weather, multi-hit probabilities, and MCP tool registration. An additional independent oracle suite pins exact rolls from `@smogon/calc`; an integer-formula grid checks mainline EVs and Champions Stat Points. See the [September 2026 audit](docs/audit-2026-09-05.md) for results and remaining calculation limits.

Meta sets come directly from Smogon's monthly `chaos/*.json` datasets. The
active MCP regulation selects the matching Reg I / Champions MA / Champions MB
format, with 1630 as the default competitive weighting. Every usage response
reports its resolved format, month, rating, and source URL; callers may request
0 (unweighted), 1500 (average ladder), 1630 (competitive), or 1760 (elite).

Common-set components are independent usage rankings: chaos data does not
identify which complete item/ability/moves/spread combination was used together.
Move and teammate percentages measure inclusion among that Pokemon's weighted
occurrences. Trend comparisons use the actual resolved month and the same ladder
and rating for the preceding month.

---

## Tool catalog (highlights)

Full list: [`docs/tools-catalog.md`](docs/tools-catalog.md). The headline tools:

| Category | Key tools |
|---|---|
| **Damage** | `calculate_damage_output`, `calculate_bulk_offensive_calcs`, `find_ko_evs`, `find_breakpoint` |
| **Survival** | `find_survival_evs`, `optimize_multi_survival_spread` (3-6 threats), `find_breakpoint` (Pareto-optimal cheapest spread) |
| **Speed** | `find_speed_evs_to_outspeed`, `find_breakpoint`, `outspeed_probability`, `visualize_speed_tiers` |
| **Live battle** | `start_battle`, `record_turn`, `suggest_next_move`, `get_battle_state`, `end_battle` |
| **Replay** | `analyze_replay` (any Showdown replay URL or ID) |
| **Iteration** | `compare_build_changes` (delta table for any spread/item/Tera change) |
| **Team** | `analyze_team`, `classify_team_archetype`, `generate_game_plan`, `analyze_team_matchup` |
| **Discovery** | `what_tool_should_i_use(question)` — when 208 is too many |

---

## Architecture

```
src/
├── vgc_mcp_core/         # Shared library (calc, models, API clients, data, state)
│   ├── calc/             # Pure functions — Gen 9 damage formula, stats, speed
│   ├── api/              # PokeAPI + Smogon Stats clients (cached)
│   ├── state/            # BuildStateManager, BattleStateManager
│   └── ...
└── vgc_mcp/              # MCP server — auto-discovers tool modules
    └── tools/            # 51 modules × ~208 tools
```

Auto-discovery means **adding a tool requires zero edits** to `server.py` — drop a `<area>_tools.py` in `vgc_mcp/tools/` exposing `register_<area>_tools(mcp, ...)` and it's picked up.

**Stack:** Python 3.11+, `mcp`, `httpx`, `pydantic`, `diskcache`, `openpyxl`, `fpdf2`. No MCP-UI dependency — works with every Claude / ChatGPT MCP transport today.

Interactive VGC views are a strong fit, but they will be delivered as an
optional sibling MCP Apps server so this endpoint stays universal. See the
[MCP-UI / MCP Apps architecture decision](docs/mcp-ui-decision.md).

[**Full architecture writeup →**](docs/technical-guide.md)

---

## Documentation

| Audience | Doc |
|---|---|
| **Just want to use it** | [Setup](docs/setup.md) · [User guide](docs/user-guide.md) · [FAQ](docs/faq.md) |
| **Want to deploy your own** | [Deploy](docs/deploy.md) · [Render steps](docs/deploy-render.md) · [Local setup](docs/local-setup.md) |
| **Want to contribute** | [Contributing](CONTRIBUTING.md) · [Development](docs/development.md) · [Architecture](docs/technical-guide.md) |
| **Building MCP clients** | [API reference](docs/api-reference.md) · [Tool catalog](docs/tools-catalog.md) |

---

## Contributing

PRs welcome. The fastest way to ship value is to add a new tool module:

1. Drop `vgc_mcp/tools/<area>_tools.py` exposing `register_<area>_tools(mcp, ...)`
2. Auto-discovery picks it up — no `server.py` edit
3. Add tests in `tests/tools/test_<area>_tools.py`

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/development.md](docs/development.md) for the full pattern (handlers in `vgc_mcp_core/tools/`, error contracts, presentation rules).

---

## Status

- ✅ Live at `https://vgc-mcp.onrender.com/mcp` (legacy SSE at `/sse`)
- ✅ 208 tools registered, 1,493 tests passing
- ✅ CI-gated deploys from `main`, followed by exact-revision production MCP verification
- ✅ MIT licensed — fork it, ship it, no strings

---

## License

MIT — see [LICENSE](LICENSE).

---

**Built with [Model Context Protocol](https://modelcontextprotocol.io/).** Questions? Open an [issue](https://github.com/MSS23/vgc-mcp/issues) or join [Discussions](https://github.com/MSS23/vgc-mcp/discussions).
