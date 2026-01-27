@echo off
echo ====================================================
echo VGC MCP - One-Click Setup for FREE Claude Desktop!
echo ====================================================
echo.
echo This setup works with FREE Claude Desktop
echo NO premium subscription required!
echo.
echo Installing 157+ VGC tools...
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo.
    echo Please install Python from https://python.org
    echo IMPORTANT: Check "Add Python to PATH" during installation
    echo.
    echo After installing Python, run this script again.
    echo.
    pause
    exit /b 1
)

echo Python found!
python --version
echo.

echo [1/3] Installing VGC MCP package...
pip install -e .
if errorlevel 1 (
    echo.
    echo ERROR: Installation failed!
    echo Try running this script as Administrator.
    echo.
    pause
    exit /b 1
)

echo.
echo [2/3] Configuring Claude Desktop...
python -m vgc_mcp.setup
if errorlevel 1 (
    echo.
    echo ERROR: Configuration failed!
    echo Make sure Claude Desktop is installed.
    echo.
    pause
    exit /b 1
)

echo.
echo ====================================================
echo [3/3] SETUP COMPLETE!
echo ====================================================
echo.
echo SUCCESS! You now have 157+ VGC tools on FREE Claude Desktop!
echo No premium subscription needed.
echo.
echo Next steps:
echo   1. Close Claude Desktop completely (check system tray)
echo   2. Reopen Claude Desktop
echo   3. Start a new conversation
echo   4. Say: "What can you help me with?"
echo.
echo Try these commands:
echo   - "Does Flutter Mane OHKO Incineroar?"
echo   - "Help me build a Rain team"
echo   - "What EVs to survive Urshifu?"
echo.
echo Need help? See LOCAL_SETUP.md or https://github.com/MSS23/vgc-mcp/issues
echo.
pause
