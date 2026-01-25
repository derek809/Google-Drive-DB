@echo off
REM ============================================
REM MCP Learning Sync - One-Click Button
REM Double-click this file to sync your learning data
REM ============================================

title MCP Learning Sync

REM Change to the MCP directory
cd /d "C:\Users\derek\OneDrive\Desktop\Dilligence\Google Drive DB"

REM Clear screen and show header
cls
echo ============================================================
echo          MCP LEARNING SYNC
echo ============================================================
echo.
echo This will sync your learning data to Apps Script
echo.
echo Current directory: %CD%
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python not found
    echo.
    echo Please make sure Python is installed and in your PATH
    echo.
    pause
    exit /b 1
)

REM Check if sync script exists
if not exist "sync_to_apps_script.py" (
    echo.
    echo ERROR: sync_to_apps_script.py not found
    echo.
    echo Please make sure this file is in the same folder as the database
    echo.
    pause
    exit /b 1
)

REM Run the sync script
echo Running sync...
echo.
python sync_to_apps_script.py

REM Keep window open so user can see results
echo.
echo ============================================================
echo.
