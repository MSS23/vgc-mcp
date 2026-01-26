# VGC Team Builder - Quick Setup Guide

Build competitive Pokemon VGC teams with AI assistance!

**No coding required. Setup takes 2 minutes.**

---

## What You Need

1. **Claude Desktop** (free) - Download from https://claude.ai/download
2. That's it!

---

## Setup Steps

### Step 1: Download Claude Desktop

Go to https://claude.ai/download and install Claude Desktop for your computer.

### Step 2: Open the Config File

**On Windows:**
1. Press `Win + R` to open Run
2. Type `%APPDATA%\Claude` and press Enter
3. Open `claude_desktop_config.json` in Notepad

**On Mac:**
1. Open Finder
2. Press `Cmd + Shift + G`
3. Type `~/Library/Application Support/Claude`
4. Open `claude_desktop_config.json` in TextEdit

### Step 3: Add VGC Server

Copy and paste this into the config file:

```json
{
  "mcpServers": {
    "vgc": {
      "url": "https://vgc-mcp.onrender.com/sse"
    }
  }
}
```

**If the file already has content**, add the "vgc" part inside the existing "mcpServers" section.

### Step 4: Save and Restart

1. Save the file
2. Close Claude Desktop completely
3. Reopen Claude Desktop

---

## You're Ready!

Try saying one of these:

| What You Want | Say This |
|---------------|----------|
| Check damage | "Does Flutter Mane OHKO Incineroar?" |
| Build a team | "Help me build a Rain team" |
| Optimize EVs | "What EVs does Incineroar need to survive Flutter Mane?" |
| Learn VGC | "Explain what EVs are" |
| See all features | "What can you help me with?" |

---

## Example Conversation

**You:** Does my Flutter Mane OHKO Incineroar?

**Claude:** Shows the damage calculation with:
- Both Pokemon's stats and EVs
- The damage range (e.g., 72-85%)
- Whether it's a guaranteed KO

---

## Troubleshooting

### "Claude doesn't see the VGC tools"

1. Make sure you saved the config file
2. Make sure you restarted Claude Desktop completely
3. Check the config file has the correct format (no typos)

### "The config file doesn't exist"

Create a new file called `claude_desktop_config.json` with the content from Step 3.

### "I get connection errors"

The server may be starting up (takes ~30 seconds on first request). Try again in a minute.

---

## Features

- **Damage Calculations** - Check if you OHKO, survive hits, find damage ranges
- **EV Optimization** - Find the perfect spread to survive specific threats
- **Team Building** - Get suggestions for teammates and team synergy
- **Speed Analysis** - Compare speeds, check Tailwind/Trick Room scenarios
- **Learn VGC** - Glossary of terms, Pokemon guides, type matchups

---

## Need Help?

Just ask Claude: "What can you help me with?"

For bugs or feature requests: https://github.com/MSS23/vgc-mcp/issues
