@echo off
title TLM Telegram Bot - Vetimec
color 0A

echo.
echo ========================================
echo    TLM TELEGRAM BOT - VETIMEC
echo ========================================
echo.

REM Vai nella directory del batch
cd /d "%~dp0"

REM Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato!
    echo Installa Python 3.8+ da python.org
    pause
    exit /b 1
)

echo [INFO] Python trovato: 
python --version

REM Verifica dipendenze
python -c "import telegram" 2>nul
if errorlevel 1 (
    echo.
    echo [SETUP] Dipendenze non trovate, installazione in corso...
    python -m pip install python-telegram-bot==20.7 requests
)

echo.
echo [INFO] Avvio bot in corso...
echo [INFO] Premi Ctrl+C per fermare il bot
echo.
echo ========================================
echo.

REM Avvia bot
python bot.py

echo.
echo [INFO] Bot terminato
pause
