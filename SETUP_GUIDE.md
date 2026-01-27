# VGC Team Builder - Setup Guide

Build competitive Pokemon VGC teams with AI assistance!

**Setup takes 2-5 minutes. Choose your preferred method below.**

---

## Choose Your Setup Method

### Option 1: Local Setup (Recommended)

**Works on FREE Claude Desktop!**

- ✅ Works with free Claude Desktop
- ✅ Faster (no network latency)
- ✅ More private (data stays local)
- ✅ Works offline (except API calls)
- ❌ Requires Python 3.11+ installation

**Best for:** Most users who want the best performance and don't mind a quick install.

[Jump to Local Setup Instructions](#local-setup-instructions)

### Option 2: Remote Setup

**Requires Claude Desktop Premium**

- ✅ No local installation needed
- ✅ Always up-to-date
- ❌ Requires Claude Desktop premium subscription
- ❌ Slower (network dependent)
- ❌ Requires internet connection

**Best for:** Users who want zero installation or are trying out the tool.

[Jump to Remote Setup Instructions](#remote-setup-instructions)

---

## Comparison Table

| Feature | Local Setup | Remote Setup |
|---------|-------------|--------------|
| **Claude Desktop Tier** | Free ✅ | Premium 💎 |
| **Speed** | Fast ⚡ | Network dependent 🌐 |
| **Privacy** | Local 🔒 | Server logs 📊 |
| **Installation** | Python required 🐍 | Zero install ☁️ |
| **Updates** | Manual (git pull) | Automatic |
| **Internet Required** | Only for APIs | Always |
| **Best For** | Most users | Trial/testing |

---

# Local Setup Instructions

## What You Need

1. **Python 3.11+** - Download from https://python.org
2. **Claude Desktop (free)** - Download from https://claude.ai/download
3. **5 minutes** of setup time

## Windows Setup (One-Click)

**Easiest method for Windows users:**

1. Install Python from https://python.org (check "Add to PATH")
2. Download this project:
   - Go to https://github.com/MSS23/vgc-mcp
   - Click "Code" > "Download ZIP"
   - Extract to a folder
3. **Double-click `setup.bat`** in the extracted folder

That's it! The script installs everything and configures Claude Desktop automatically.

## Mac/Linux Setup (One-Click)

1. Install Python from https://python.org
2. Download/clone this project:
   ```bash
   git clone https://github.com/MSS23/vgc-mcp.git
   cd vgc-mcp
   ```
3. Run the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

## Manual Setup (All Platforms)

### Step 1: Verify Python

Check Python is installed:
```bash
python --version
# Should show: Python 3.11.x or higher
```

If not installed, download from https://python.org

### Step 2: Download VGC MCP

**Option A - Git Clone (recommended):**
```bash
git clone https://github.com/MSS23/vgc-mcp.git
cd vgc-mcp
```

**Option B - Download ZIP:**
1. Go to https://github.com/MSS23/vgc-mcp
2. Click "Code" > "Download ZIP"
3. Extract to a folder
4. Open terminal/command prompt in that folder

### Step 3: Install Package

```bash
pip install -e .
```

You should see output ending with:
```
Successfully installed vgc-mcp
```

### Step 4: Configure Claude Desktop

Find and edit your Claude Desktop config file:

**Windows:**
1. Press `Win + R`
2. Type `%APPDATA%\Claude` and press Enter
3. Open `claude_desktop_config.json` in Notepad

**Mac:**
1. Open Finder
2. Press `Cmd + Shift + G`
3. Type `~/Library/Application Support/Claude`
4. Open `claude_desktop_config.json` in TextEdit

**Linux:**
- Location: `~/.config/claude/claude_desktop_config.json`

**Add this configuration:**

```json
{
  "mcpServers": {
    "vgc": {
      "command": "python",
      "args": ["-m", "vgc_mcp"]
    }
  }
}
```

**If the file already has content**, add the `"vgc"` part inside the existing `"mcpServers"` section:

```json
{
  "mcpServers": {
    "existing-server": { "...": "..." },
    "vgc": {
      "command": "python",
      "args": ["-m", "vgc_mcp"]
    }
  }
}
```

**Windows troubleshooting:** If `python` command isn't found, use the full path:

```json
{
  "mcpServers": {
    "vgc": {
      "command": "C:\\Python313\\python.exe",
      "args": ["-m", "vgc_mcp"]
    }
  }
}
```

Find your Python path with: `where python` (Windows) or `which python` (Mac/Linux)

### Step 5: Restart Claude Desktop

1. **Close** Claude Desktop completely (check system tray/menu bar)
2. **Reopen** Claude Desktop
3. Start a new conversation

### Step 6: Verify It Works

**How to confirm you're using the LOCAL server:**

1. **Check MCP Status:**
   - Look for MCP indicator in Claude Desktop
   - Should show "vgc" server as connected/green

2. **List Tools:**
   Say to Claude:
   > "What can you help me with?"

   You should see VGC tools listed (157+ tools if using local server)

3. **Test a Command:**
   > "Does Flutter Mane OHKO Incineroar?"

   If you get damage calculations, it's working!

4. **Verify Speed:**
   - Local server = instant responses (no network delay)
   - Remote server = noticeable latency
   - If instant → You're using local ✅

5. **Check Config File:**
   Your config should have `"command": "python"` (not `"url": "..."`)

**Test server directly (optional):**
```bash
python -m vgc_mcp
```
If it starts without errors, server is installed. Press Ctrl+C to stop.

---

# Remote Setup Instructions

**Note:** This setup requires **Claude Desktop Premium**. For free Claude Desktop, use [Local Setup](#local-setup-instructions) instead.

## What You Need

1. **Claude Desktop Premium** - Upgrade at https://claude.ai
2. **2 minutes** of setup time

## Setup Steps

### Step 1: Download Claude Desktop

Go to https://claude.ai/download and install Claude Desktop.

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

### Local Setup Issues

**"Python not found"**
1. Reinstall Python with "Add to PATH" checked
2. Or use the full path in the config (see Step 4 above)
3. Restart your terminal after installing Python

**"Module not found: vgc_mcp"**
Run the install command again:
```bash
pip install -e .
```

**"Claude doesn't see the VGC tools"**
1. Make sure you saved the config file
2. Make sure you restarted Claude Desktop completely
3. Check the config JSON is valid (no missing commas/brackets)

**"Permission denied"**
- **Windows:** Run Command Prompt as Administrator
- **Mac/Linux:** Use `pip install --user -e .`

### Remote Setup Issues

**"The config file doesn't exist"**
Create a new file called `claude_desktop_config.json` with the content from Step 3.

**"I get connection errors"**
The server may be starting up (takes ~30 seconds on first request). Try again in a minute.

---

## Features

- **Damage Calculations** - Check if you OHKO, survive hits, find damage ranges
- **EV Optimization** - Find the perfect spread to survive specific threats
- **Team Building** - Get suggestions for teammates and team synergy
- **Speed Analysis** - Compare speeds, check Tailwind/Trick Room scenarios
- **Learn VGC** - Glossary of terms, Pokemon guides, type matchups

---

## Updating

**Local Setup:**
```bash
cd vgc-mcp
git pull
pip install -e .
```
Then restart Claude Desktop.

**Remote Setup:**
Updates happen automatically on the server.

---

## How to Verify Which Setup You're Using

Not sure if you're using local or remote? Check your config file:

**Local Setup (Free):**
```json
{
  "mcpServers": {
    "vgc": {
      "command": "python",          // ← Has "command" field
      "args": ["-m", "vgc_mcp"]
    }
  }
}
```

**Remote Setup (Premium):**
```json
{
  "mcpServers": {
    "vgc": {
      "url": "https://vgc-mcp.onrender.com/sse"  // ← Has "url" field
    }
  }
}
```

**Additional Verification:**
- **Local**: Instant responses, no network delay, data stays on your machine
- **Remote**: Slight network latency, requires internet connection
- **Local**: Works on FREE Claude Desktop ✅
- **Remote**: Requires Claude Desktop Premium 💎

---

## Quick Reference: Config File Locations

Copy and paste into your terminal/run dialog:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/claude/claude_desktop_config.json`

---

## Need Help?

- Ask Claude: "What can you help me with?"
- Detailed local setup guide: [LOCAL_SETUP.md](LOCAL_SETUP.md)
- Report issues: https://github.com/MSS23/vgc-mcp/issues
