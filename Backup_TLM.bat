@echo off
REM ============================================
REM TLM Manager - Backup Database
REM Può essere eseguito manualmente o schedulato
REM ============================================

setlocal

REM === CONFIGURAZIONE ===
set "SOURCE_DB=%~dp0tlm_data.db"
set "BACKUP_DIR=H:\0CellaMikron\0Cella_DMG-Test\Backup Archivi\TLM_service"
set "RETENTION_DAYS=30"

REM === VERIFICA SORGENTE ===
if not exist "%SOURCE_DB%" (
    echo [ERRORE] Database non trovato: %SOURCE_DB%
    exit /b 1
)

REM === CREA CARTELLA BACKUP SE NON ESISTE ===
if not exist "%BACKUP_DIR%" (
    mkdir "%BACKUP_DIR%"
    echo [INFO] Creata cartella: %BACKUP_DIR%
)

REM === GENERA NOME FILE CON DATA ===
for /f "tokens=1-3 delims=/" %%a in ('date /t') do (
    set "TODAY=%%c-%%b-%%a"
)
REM Formato alternativo per sistemi con data diversa
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set "TODAY=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%"

set "BACKUP_FILE=%BACKUP_DIR%\tlm_data_backup_%TODAY%.db"

REM === VERIFICA SE BACKUP OGGI ESISTE GIA' ===
if exist "%BACKUP_FILE%" (
    echo [INFO] Backup di oggi già esistente: %BACKUP_FILE%
    goto :cleanup
)

REM === ESEGUI BACKUP ===
echo [BACKUP] Copio database...
copy /Y "%SOURCE_DB%" "%BACKUP_FILE%" >nul

if %errorlevel% equ 0 (
    echo [OK] Backup completato: %BACKUP_FILE%
) else (
    echo [ERRORE] Backup fallito!
    exit /b 1
)

:cleanup
REM === PULIZIA VECCHI BACKUP ===
echo [INFO] Pulizia backup più vecchi di %RETENTION_DAYS% giorni...
forfiles /p "%BACKUP_DIR%" /m "tlm_data_backup_*.db" /d -%RETENTION_DAYS% /c "cmd /c del @path && echo [RIMOSSO] @file" 2>nul

echo.
echo [COMPLETATO] Backup terminato.
exit /b 0
