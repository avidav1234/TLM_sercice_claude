@echo off
echo ========================================
echo TLM Manager V6 - Avvio con Debug
echo ========================================
echo.

cd /d "%~dp0"

echo Cartella corrente: %cd%
echo.

echo Verifico file...
if exist app.py (
    echo [OK] app.py trovato
) else (
    echo [ERRORE] app.py NON trovato!
    pause
    exit /b 1
)

if exist templates\index.html (
    echo [OK] templates\index.html trovato
) else (
    echo [ERRORE] templates\index.html NON trovato!
    pause
    exit /b 1
)

echo.
echo Avvio applicazione...
echo (La finestra si aprira' tra pochi secondi)
echo.

python app.py

echo.
echo ========================================
echo L'applicazione si e' chiusa.
echo Se ci sono stati errori, sono mostrati sopra.
echo ========================================
pause
