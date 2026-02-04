@echo off
REM TLM Manager - Avvio DEBUG con Console Visibile
REM Usa questo per testare il nuovo design

echo ============================================
echo    TLM Manager - DEBUG MODE
echo ============================================
echo.
echo [INFO] Ferma processi esistenti...
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo [INFO] Cambio directory...
cd /d "%~dp0"

echo [INFO] Cancello cache PyWebView...
rmdir /S /Q "%LOCALAPPDATA%\pywebview" 2>nul

echo [INFO] Avvio TLM Manager...
echo [INFO] Premi Ctrl+C per fermare
echo.
python app.py

pause
