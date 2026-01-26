# VGC Team Builder - User Guide

Build competitive Pokemon VGC teams with AI assistance in Claude Desktop!

## Quick Setup (5 minutes)

### Step 1: Install Python

Download Python 3.10+ from https://python.org

During installation, check "Add Python to PATH".

### Step 2: Download VGC Tools

Option A - Clone with Git:
```bash
git clone https://github.com/MSS23/vgc-mcp.git
cd vgc-mcp
```

Option B - Download ZIP from GitHub and extract.

### Step 3: Run Setup Script

Open a terminal/command prompt in the vgc-mcp folder:

```bash
python -m vgc_mcp.setup
```

This automatically:
- Installs the package
- Configures Claude Desktop
- Sets everything up

### Step 4: Restart Claude Desktop

Close and reopen Claude Desktop. You're ready!

---

## How to Use

### Just Ask Naturally

The easiest way to use VGC tools is just asking questions naturally:

| What You Want | Example Question |
|---------------|------------------|
| **Damage calc** | "Does Flutter Mane OHKO Incineroar?" |
| **Build team** | "Help me build a Rain team" |
| **Optimize EVs** | "What EVs does Incineroar need to survive Flutter Mane?" |
| **Compare speed** | "Is my Landorus faster than Tornadus?" |
| **Learn** | "Explain what EVs are" |

### Quick Action Buttons

In Claude Desktop, you'll see quick action buttons:
- **Check Damage** - Calculate damage between Pokemon
- **Build Team** - Start building a VGC team
- **Analyze Paste** - Analyze a team you paste
- **Learn VGC** - Learn competitive basics
- **Optimize Spread** - Optimize EV spreads
- **Compare Speeds** - Speed tier analysis

Just click any button to get started!

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

### EV Optimization
- Find efficient EV spreads
- Nature optimization (save EVs)
- Bulk calculator with diminishing returns
- Benchmark-based spreads

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

1. Make sure you ran the setup script: `python -m vgc_mcp.setup`
2. Restart Claude Desktop completely (close and reopen)
3. Check the config file exists:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`

### "I get Python errors"

1. Make sure Python 3.10+ is installed: `python --version`
2. Try reinstalling: `pip install -e .` from the project folder
3. Check all dependencies installed: `pip install httpx pydantic diskcache mcp`

### "Calculations seem wrong"

The tool uses the exact Gen 9 damage formula. If results differ from Showdown:
1. Check both Pokemon have the same EVs/nature/item
2. Check weather, terrain, and other modifiers match
3. Remember: Pokemon uses special rounding (0.5 rounds DOWN)

### "What format is this for?"

VGC Regulation H (current format) by default. The tool uses:
- Level 50
- Doubles format
- 508 max EVs
- Smogon usage data for meta analysis

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
- Say "help damage" for damage calculation help
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
