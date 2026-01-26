# VGC MCP - Local Setup Guide

Run VGC team building tools **locally** on your computer with Claude Desktop.

**Why local?** Faster responses, works offline, free to use with any Claude model.

---

## Requirements

- **Python 3.10+** - Download from https://python.org
- **Claude Desktop** - Download from https://claude.ai/download
- **5 minutes** of setup time

---

## Quick Setup (Recommended)

### Step 1: Install Python

1. Go to https://python.org/downloads
2. Download Python 3.10 or higher
3. **Important:** Check "Add Python to PATH" during installation

Verify it works:
```bash
python --version
# Should show: Python 3.10.x or higher
```

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

### Step 5: Verify It Works

Say to Claude:
> "What can you help me with?"

You should see VGC tools listed! Try:
> "Does Flutter Mane OHKO Incineroar?"

---

## Manual Setup (If Automatic Fails)

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

---

## Example Commands

Once set up, try these in Claude Desktop:

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
