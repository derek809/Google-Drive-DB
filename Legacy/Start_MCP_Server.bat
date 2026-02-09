@echo off
echo ============================================
echo   MCP Email Processor Server
echo ============================================
echo.

cd /d "%~dp0"

echo Checking MCP SDK installation...
pip show mcp >nul 2>&1
if errorlevel 1 (
    echo.
    echo MCP SDK not found. Installing...
    pip install mcp
    echo.
)

echo Starting MCP Server...
echo Database: %~dp0mcp_learning.db
echo.
echo The server will run in the background.
echo Claude Desktop will connect automatically.
echo.
echo Press Ctrl+C to stop the server.
echo ============================================
echo.

python mcp_server.py
pause
