@echo off
REM TLM Manager - Riavvio con Cache Pulita

echo ============================================
echo    TLM Manager - RIAVVIO PULITO
echo ============================================
echo.

REM Ferma tutti i processi Python
echo [1/4] Ferma processi esistenti...
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

REM Cancella cache PyWebView
echo [2/4] Cancello cache PyWebView...
rmdir /S /Q "%LOCALAPPDATA%\pywebview" 2>nul
rmdir /S /Q "%APPDATA%\pywebview" 2>nul

REM Cancella cache browser (Edge WebView2)
echo [3/4] Cancello cache WebView2...
rmdir /S /Q "%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache" 2>nul
rmdir /S /Q "%LOCALAPPDATA%\Microsoft\EdgeWebView\User Data\Default\Cache" 2>nul

REM Avvia app
echo [4/4] Avvio TLM Manager...
cd /d "%~dp0"
start "" pythonw app.py

echo.
echo [OK] TLM Manager avviato!
timeout /t 3 /nobreak >nul
