# VGC Team Builder - User Guide

Damage calcs, spreads, speed checks and team reviews for Pokemon VGC and
Pokemon Champions, inside Claude on your phone or computer.

## Connect (2 minutes)

### Option 1: Claude app or claude.ai (recommended, works on phone)

1. Open **claude.ai → Settings → Connectors → Add custom connector**.
2. Paste `https://vgc-mcp.onrender.com/mcp` and save. This gives you the
   34 core tools, which cover almost every question. Power users can use
   `https://vgc-mcp.onrender.com/mcp/full` for all 206.
3. Start a new chat and say hi. The connector also appears in the Claude
   phone app once it is added on the web.

The hosted server stays awake around the clock, so the first reply should
come back in a second or two. If it ever takes 30-60 seconds, it was asleep;
try again and it will be quick.

### Option 2: Run it on your own computer (Claude Desktop)

You need Python 3.11 or newer (tick "Add Python to PATH" on Windows).

```bash
git clone https://github.com/MSS23/vgc-mcp.git
cd vgc-mcp
python -m vgc_mcp.setup
```

The setup script installs the package and adds the server to Claude
Desktop's config. Close and reopen Claude Desktop and you're ready.

To edit the config by hand instead, add this to
`%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
`~/Library/Application Support/Claude/claude_desktop_config.json` (Mac):

```json
{
  "mcpServers": {
    "vgc": { "command": "vgc-mcp" }
  }
}
```

If Windows can't find `vgc-mcp`, use the full Python path instead:
`"command": "C:\\Path\\To\\python.exe", "args": ["-m", "vgc_mcp"]`.

---

## How to Use

### Just Ask Naturally

The easiest way to use VGC tools is just asking questions naturally:

| What You Want | Example Question |
|---------------|------------------|
| **Damage calc** | "Does Flutter Mane OHKO Incineroar?" |
| **Build team** | "Help me build a Rain team" |
| **Spreads** | "What does Incineroar need to survive Flutter Mane?" |
| **Compare speed** | "Is my Landorus faster than Tornadus?" |
| **Prep a team** | "Get my team ready for a Regional" + paste |

### Starter prompts

Clients that show MCP prompts (Claude Desktop's attachment menu, for
example) list ready-made starting points: Prepare for Tournament, Explain
Replay, Check Damage, Build Team, Analyze Paste, Optimize Spread, Find
Survival Spread, Check Survival, Compare Speeds and Learn VGC. On the phone,
just type the question instead.

---

## Example Conversations

### Damage Calculation

**You:** Does my Landorus OHKO Incineroar with Earthquake?

**Claude:** Shows damage range, survival %, and the full calculation with both Pokemon's spreads visible.

### Team Building

**You:** I want to build a team around Flutter Mane

**Claude:** Suggests partners like Incineroar (Fake Out support), Landorus (Ground coverage), shows synergies, and helps you build the full team.

### EV Optimization

**You:** What spread should my Amoonguss use to survive Flutter Mane?

**Claude:** Calculates survival benchmarks, shows the minimum EVs needed, and suggests if a different nature could save EVs.

### Analyzing Your Team

**You:** Analyze this team:
```
Flutter Mane @ Choice Specs
Ability: Protosynthesis
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Dazzling Gleam
- Mystical Fire

Incineroar @ Assault Vest
...
```

**Claude:** Checks type coverage, speed tiers, EV efficiency, and suggests improvements.

---

## What Can VGC Tools Do?

### Damage & Combat
- Calculate if you KO a Pokemon
- Find survival EVs for specific threats
- Multi-threat bulk analysis (survive multiple hits)
- Chip damage calculations (hazards, weather, items)

### Team Building
- Suggest Pokemon partners
- Analyze team weaknesses
- Check type coverage
- Lead pair recommendations
- Tournament readiness checker

### Speed Analysis
- Compare speed between Pokemon
- Speed tier visualizer
- Tailwind/Trick Room calculations
- Probability of outspeeding (using Smogon data)

### Spreads (EVs or Champions Stat Points)
- Find efficient spreads for either system
- Nature optimization (save points)
- Bulk calculator with diminishing returns
- Benchmark-based spreads (outspeed X and survive Y)

### Learning VGC
- VGC glossary (EVs, STAB, OHKO, etc.)
- Pokemon explainer (what makes a Pokemon good?)
- Type effectiveness charts
- Build mistake checker

---

## Pasting Teams

You can paste teams in Pokemon Showdown format:

```
Flutter Mane @ Choice Specs
Ability: Protosynthesis
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Moonblast
- Shadow Ball
- Dazzling Gleam
- Mystical Fire
```

Or paste a PokePaste URL:
```
https://pokepast.es/abc123
```

Claude will automatically parse and analyze it!

---

## Common Questions

### "Claude doesn't see the VGC tools"

- **Connector:** check it is switched on for the chat (tools menu in the
  message box) and start a new chat after adding it.
- **Claude Desktop:** restart it completely, and check the config file is
  valid JSON (no missing commas or brackets).

### "Python not found" or "Module not found: vgc_mcp"

1. Check the version: `python --version` must be 3.11 or newer.
2. Reinstall from the project folder: `pip install -e .`
3. On Windows, put the full Python path in the config (see above).

### "Calculations seem wrong"

The tool uses the exact Gen 9 damage formula. If results differ from Showdown:
1. Check both Pokemon have the same spread, nature and item.
2. Check weather, terrain, Tera and stat stages match.
3. Remember Pokemon rounding: 0.5 rounds down.

### "What format is this for?"

The default is **Pokemon Champions Regulation MC** (Stat Points: 32 per stat,
66 total, no IVs, Mega Evolution). Mainline VGC Regulations F, G, H and I
(EVs: 252 per stat, 508 total) are supported too. The server picks the format
from the Pokemon you mention, or you can just say "Reg F" or "Champions".

---

## Tips for Best Results

1. **Be specific about spreads**: "252 SpA Timid Flutter Mane" gives more accurate results than just "Flutter Mane"

2. **Mention items and abilities**: "Choice Specs Flutter Mane" or "Assault Vest Incineroar"

3. **Use Tera when relevant**: "Tera Fairy Flutter Mane Moonblast"

4. **Paste full teams**: The more context you provide, the better the analysis

5. **Ask follow-up questions**: "What if I use Modest instead?" or "Show me under Tailwind"

---

## Getting Help

- Say "What can you do?" to see all capabilities
- Say "What can you do for damage?" (or team, spreads, speed, learn) for examples
- Check the VGC glossary: "explain [term]"

For bugs or feature requests: https://github.com/MSS23/vgc-mcp/issues

---

## Quick Reference

| Task | Just Say... |
|------|-------------|
| Damage calc | "Does X OHKO Y?" |
| Speed compare | "Is X faster than Y?" |
| Learn term | "What is STAB?" |
| Show help | "What can you do?" |
| Build team | "Help me build a team" |
| Analyze team | "Analyze this team" + paste |
