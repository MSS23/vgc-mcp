# VGC MCP - Local Setup Guide

Run VGC team building tools **locally** on your computer with Claude Desktop.

## ✅ Works on FREE Claude Desktop!

**No premium subscription required.** This local setup gives you access to all 157+ VGC tools on the free version of Claude Desktop.

**Why local?**
- ✅ **Free** - No premium subscription needed
- ⚡ **Faster** - No network latency
- 🔒 **Private** - Data stays on your machine
- 🌐 **Offline** - Works without internet (except API calls)

---

## Requirements

- **Python 3.11+** - Download from https://python.org
- **Claude Desktop (FREE)** - Download from https://claude.ai/download
- **5 minutes** of setup time

---

## Quick Setup by Platform

### Windows (One-Click)

**Easiest method for Windows users:**

1. Install Python from https://python.org (check "Add to PATH")
2. Download this project:
   - Go to https://github.com/MSS23/vgc-mcp
   - Click "Code" > "Download ZIP"
   - Extract to a folder
3. **Double-click `setup.bat`** in the extracted folder

That's it! The script installs everything and configures Claude Desktop automatically.

### Mac/Linux (One-Click)

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

---

## Manual Setup (All Platforms)

**If the one-click setup doesn't work, follow these steps:**

### Step 1: Verify Python Installation

Check if Python is already installed:
```bash
python --version
# Should show: Python 3.11.x or higher
```

If not installed or version is too old:
1. Go to https://python.org/downloads
2. Download Python 3.11 or higher
3. **Important:** Check "Add Python to PATH" during installation
4. Restart your terminal and verify again

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
4. Open terminal in that folder

### Step 3: Install and Configure

Run these commands:
```bash
# Install the package
pip install -e .

# Run the setup script (configures Claude Desktop automatically)
python -m vgc_mcp.setup
```

You should see:
```
============================================================
VGC MCP Server - Claude Desktop Setup
============================================================

[1/4] Checking package installation...
      Package is installed.

[2/4] Getting Python executable path...
      Using: C:\Python313\python.exe

[3/4] Configuring Claude Desktop...
      Config file: C:\Users\...\Claude\claude_desktop_config.json
      Found existing config, updating...

[4/4] Writing configuration...
      Configuration saved!

============================================================
SETUP COMPLETE!
============================================================
```

### Step 4: Restart Claude Desktop

1. **Close** Claude Desktop completely (check system tray)
2. **Reopen** Claude Desktop
3. Start a new conversation

### Step 5: Verify It Works (Free Claude Desktop!)

Open **FREE Claude Desktop** and start a new conversation.

#### Check 1: Verify MCP Server is Connected

In Claude Desktop, look for an MCP indicator (usually in the bottom or top of the window). You should see:
- **"vgc"** server listed as connected
- Green/active status indicator

#### Check 2: List Available Tools

Say to Claude:
> "What can you help me with?"

You should see a response listing VGC-specific capabilities like:
- Damage calculations
- EV optimization
- Team building
- Speed analysis
- etc.

#### Check 3: Test a Tool

Try a simple command:
> "Does Flutter Mane OHKO Incineroar?"

If Claude responds with damage calculations and Pokemon stats, **it's working!**

#### Check 4: Verify Local Server (Not Remote)

To confirm you're using the **local** server (not remote), check:

1. **Speed**: Local responses should be instant (no network delay)
2. **Privacy**: Your data isn't leaving your machine
3. **Config**: Open your Claude Desktop config file and verify it shows:
   ```json
   {
     "mcpServers": {
       "vgc": {
         "command": "python",  // ← Local setup
         "args": ["-m", "vgc_mcp"]
       }
     }
   }
   ```
   **NOT** this (remote setup):
   ```json
   {
     "mcpServers": {
       "vgc": {
         "url": "https://vgc-mcp.onrender.com/sse"  // ← Remote setup
       }
     }
   }
   ```

#### Check 5: Test Server Directly (Advanced)

Open a terminal/command prompt and run:
```bash
python -m vgc_mcp
```

You should see MCP server startup messages. If it starts without errors, the server is installed correctly. Press `Ctrl+C` to stop.

🎉 **You're now using 157+ VGC tools on FREE Claude Desktop!**

---

## Alternative: Manual Configuration (If Automatic Setup Fails)

If the setup script doesn't work, configure manually:

### Find the Config File

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```
(Press Win+R, paste the path, press Enter)

**Mac:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```
(In Finder: Cmd+Shift+G, paste the path)

**Linux:**
```
~/.config/claude/claude_desktop_config.json
```

### Edit the Config

Open the file in a text editor and add:

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

**If the file already has content**, just add the `"vgc"` section inside `"mcpServers"`:

```json
{
  "mcpServers": {
    "existing-server": { ... },
    "vgc": {
      "command": "python",
      "args": ["-m", "vgc_mcp"]
    }
  }
}
```

### Windows: Use Full Python Path

If `python` command isn't found, use the full path:

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

---

## Troubleshooting

### "Python not found"

1. Reinstall Python with "Add to PATH" checked
2. Or use the full path in the config (see above)
3. Restart your terminal after installing Python

### "Module not found: vgc_mcp"

Run the install command again:
```bash
pip install -e .
```

### "Claude doesn't see the tools"

1. Make sure you saved the config file
2. Make sure you restarted Claude Desktop completely
3. Check the config JSON is valid (no missing commas/brackets)

### "Permission denied"

**Windows:** Run Command Prompt as Administrator
**Mac/Linux:** Use `pip install --user -e .`

### Check if Server Works

Test the server directly:
```bash
python -m vgc_mcp
```

If it starts without errors, the server is working. Press Ctrl+C to stop.

### How to Verify Tools Are Being Called

**Problem:** "I'm not sure if Claude is using my local VGC server or something else"

**Solution - Check These Indicators:**

1. **MCP Server Status in Claude Desktop:**
   - Look for the MCP servers panel in Claude Desktop
   - Should show "vgc" server with a green/connected indicator
   - If red/disconnected, the server isn't running

2. **Check Claude Desktop Logs:**
   - **Windows:** `%APPDATA%\Claude\logs\`
   - **Mac:** `~/Library/Logs/Claude/`
   - **Linux:** `~/.config/Claude/logs/`
   - Look for MCP-related errors or connection messages

3. **Test Tool Response:**
   Ask Claude: "List all your VGC tools" or "What VGC commands do you have?"
   - If it lists 157+ tools → Local server working ✅
   - If it says it doesn't have VGC tools → Server not connected ❌

4. **Verify Speed:**
   - Local server responses are **instant** (no network delay)
   - Remote server has noticeable network latency
   - If responses are slow, you might be using the remote server

5. **Check Process is Running (Advanced):**
   - **Windows:** Open Task Manager → Look for `python.exe` running `vgc_mcp`
   - **Mac/Linux:** Run `ps aux | grep vgc_mcp`
   - If you see the process, the local server is running

**Still not working?** See the troubleshooting sections above or open an issue at:
https://github.com/MSS23/vgc-mcp/issues

---

## Why Choose Local Setup?

| Benefit | Explanation |
|---------|-------------|
| **FREE** | No Claude Desktop premium needed - works on free tier |
| **Fast** | No network latency - instant responses |
| **Private** | Your Pokemon teams stay on your machine |
| **Reliable** | No dependency on remote server uptime |
| **Offline** | Works without internet (except PokeAPI/Smogon calls) |

**Bottom line:** Local setup gives you the best experience at zero cost.

---

## Example Commands

Once set up, try these in **FREE Claude Desktop**:

| Task | Say This |
|------|----------|
| Damage calc | "Does Flutter Mane OHKO Incineroar?" |
| Survival EVs | "What EVs does Incineroar need to survive Flutter Mane?" |
| Build team | "Help me build a Rain team" |
| Speed compare | "Is Landorus faster than Tornadus?" |
| Learn VGC | "Explain what EVs are" |
| Analyze team | "Analyze this team:" + paste Showdown format |

---

## Updating

To get the latest version:

```bash
cd vgc-mcp
git pull
pip install -e .
```

Then restart Claude Desktop.

---

## Need Help?

- Say "What can you do?" in Claude Desktop
- Report issues: https://github.com/MSS23/vgc-mcp/issues
