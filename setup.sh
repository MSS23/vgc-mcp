#!/bin/bash
# VGC MCP - One-Click Setup Script for Mac/Linux

echo "===================================================="
echo "VGC MCP - One-Click Setup for FREE Claude Desktop!"
echo "===================================================="
echo ""
echo "This setup works with FREE Claude Desktop"
echo "NO premium subscription required!"
echo ""
echo "Installing 157+ VGC tools..."
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "ERROR: Python not found!"
        echo ""
        echo "Please install Python 3.11+ from https://python.org"
        echo "Then run this script again."
        echo ""
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

# Check Python version is 3.11+
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info[1])')

echo "Python found!"
$PYTHON_CMD --version
echo ""

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "ERROR: Python 3.11+ required, but found Python $PYTHON_VERSION"
    echo ""
    echo "Please install Python 3.11+ from https://python.org"
    echo ""
    exit 1
fi

# Install package
echo "[1/3] Installing VGC MCP package..."
$PYTHON_CMD -m pip install -e .
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Installation failed!"
    echo "Try running with sudo: sudo ./setup.sh"
    echo "Or install in user mode: pip install --user -e ."
    echo ""
    exit 1
fi

# Configure Claude Desktop
echo ""
echo "[2/3] Configuring Claude Desktop..."
$PYTHON_CMD -m vgc_mcp.setup
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Configuration failed!"
    echo "Make sure Claude Desktop is installed."
    echo ""
    echo "You can manually configure by adding this to your config file:"
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Config file: ~/Library/Application Support/Claude/claude_desktop_config.json"
    else
        echo "Config file: ~/.config/claude/claude_desktop_config.json"
    fi
    echo ""
    echo '{'
    echo '  "mcpServers": {'
    echo '    "vgc": {'
    echo '      "command": "python3",'
    echo '      "args": ["-m", "vgc_mcp"]'
    echo '    }'
    echo '  }'
    echo '}'
    echo ""
    exit 1
fi

# Success message
echo ""
echo "===================================================="
echo "[3/3] SETUP COMPLETE!"
echo "===================================================="
echo ""
echo "SUCCESS! You now have 157+ VGC tools on FREE Claude Desktop!"
echo "No premium subscription needed."
echo ""
echo "Next steps:"
echo "  1. Close Claude Desktop completely"
echo "  2. Reopen Claude Desktop"
echo "  3. Start a new conversation"
echo "  4. Say: \"What can you help me with?\""
echo ""
echo "Try these commands:"
echo "  - \"Does Flutter Mane OHKO Incineroar?\""
echo "  - \"Help me build a Rain team\""
echo "  - \"What EVs to survive Urshifu?\""
echo ""
echo "Need help? See LOCAL_SETUP.md or https://github.com/MSS23/vgc-mcp/issues"
echo ""
