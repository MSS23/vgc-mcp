"""
One-click setup for Claude Desktop integration.

Run with:
    python -m vgc_mcp.setup

This script:
1. Verifies Python and package installation
2. Locates or creates Claude Desktop config file
3. Adds the VGC MCP server configuration
4. Provides next steps for the user
"""

import json
import os
import sys
import subprocess
from pathlib import Path


def get_claude_config_path() -> Path:
    """Get the Claude Desktop configuration file path for the current OS."""
    if sys.platform == "win32":
        # Windows: %APPDATA%\Claude\claude_desktop_config.json
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            raise RuntimeError("APPDATA environment variable not found")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        # Linux: ~/.config/claude/claude_desktop_config.json
        return Path.home() / ".config" / "claude" / "claude_desktop_config.json"


def get_python_executable() -> str:
    """Get the path to the current Python executable."""
    return sys.executable


def check_package_installed() -> bool:
    """Check if vgc_mcp package is properly installed."""
    try:
        import vgc_mcp
        return True
    except ImportError:
        return False


def install_package():
    """Install the vgc_mcp package in editable mode."""
    # Find the project root (where pyproject.toml is)
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            break
        current = current.parent
    else:
        raise RuntimeError("Could not find project root (pyproject.toml)")

    print(f"Installing vgc-mcp from {current}...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(current)], check=True)


def setup_claude_desktop():
    """Configure Claude Desktop to use the VGC MCP server."""
    print("=" * 60)
    print("VGC MCP Server - Claude Desktop Setup")
    print("=" * 60)
    print()

    # Step 1: Check/install package
    print("[1/4] Checking package installation...")
    if not check_package_installed():
        print("      Package not installed. Installing now...")
        try:
            install_package()
            print("      Package installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"      ERROR: Failed to install package: {e}")
            print("      Please run: pip install -e . from the project directory")
            sys.exit(1)
    else:
        print("      Package is installed.")

    # Step 2: Get Python path
    print("\n[2/4] Getting Python executable path...")
    python_path = get_python_executable()
    print(f"      Using: {python_path}")

    # Step 3: Read or create Claude Desktop config
    print("\n[3/4] Configuring Claude Desktop...")
    config_path = get_claude_config_path()
    print(f"      Config file: {config_path}")

    # Create directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing config or create new
    if config_path.exists():
        print("      Found existing config, updating...")
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                print("      WARNING: Existing config was invalid, creating new one")
                config = {}
    else:
        print("      Creating new config file...")
        config = {}

    # Ensure mcpServers section exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Add VGC server configuration
    config["mcpServers"]["vgc"] = {
        "command": python_path,
        "args": ["-m", "vgc_mcp"]
    }

    # Step 4: Write config
    print("\n[4/4] Writing configuration...")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print("      Configuration saved!")

    # Success message
    print()
    print("=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Restart Claude Desktop (close and reopen)")
    print("2. Start a new conversation")
    print("3. Try saying: 'What can you help me with?'")
    print()
    print("Quick action buttons should appear in Claude Desktop!")
    print("You can also try:")
    print("  - 'Does Flutter Mane OHKO Incineroar?'")
    print("  - 'Help me build a Rain team'")
    print("  - '/help' to see all commands")
    print()
    print("For more help, see USER_GUIDE.md in the project folder.")
    print()


def main():
    """Entry point for setup script."""
    try:
        setup_claude_desktop()
    except Exception as e:
        print(f"\nERROR: Setup failed - {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Claude Desktop is installed")
        print("2. Make sure Python 3.10+ is installed")
        print("3. Run: pip install -e . from the project directory")
        sys.exit(1)


if __name__ == "__main__":
    main()
