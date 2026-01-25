@echo off
echo ============================================
echo Installing New Google Gemini Package
echo ============================================
echo.

echo Uninstalling old package...
pip uninstall google-generativeai -y

echo.
echo Installing new package...
pip install google-genai

echo.
echo ============================================
echo Installation Complete!
echo ============================================
echo.
echo Test it by running: python test_gemini_basic.py
echo.
pause
