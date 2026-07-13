@echo off
setlocal enabledelayedexpansion

set ENV_NAME=JFC-Embodied-Carbon-App

REM Move to this script's own folder so relative paths (data\, utils\) resolve correctly
cd /d "%~dp0"

REM ==========================================================
REM Check the environment exists
REM ==========================================================

conda env list | findstr /C:"%ENV_NAME%" >nul
if errorlevel 1 (
    echo ERROR: Conda environment "%ENV_NAME%" was not found.
    echo.
    echo Create it first with:
    echo   conda create -n %ENV_NAME% python=3.11
    echo   conda activate %ENV_NAME%
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

call conda activate %ENV_NAME%

REM ==========================================================
REM Sync requirements.txt against what's installed
REM ==========================================================

set HASH_FILE=.requirements_hash
set CURRENT_HASH=

for /f "skip=1 delims=" %%H in ('certutil -hashfile requirements.txt SHA256') do (
    if not defined CURRENT_HASH set CURRENT_HASH=%%H
)

if exist "%HASH_FILE%" (
    set /p STORED_HASH=<"%HASH_FILE%"
) else (
    set STORED_HASH=
)

if not "%CURRENT_HASH%"=="%STORED_HASH%" (
    echo requirements.txt has changed since last run — syncing packages...

    python -m pip install --upgrade pip-tools --quiet

    pip-sync requirements.txt

    if errorlevel 1 (
        echo ERROR: Failed to sync requirements. Check your internet connection
        echo or the requirements.txt file for errors.
        pause
        exit /b 1
    )

    echo %CURRENT_HASH%>"%HASH_FILE%"
    echo Packages synced successfully ^(unused packages removed^).
) else (
    echo Requirements already up to date — skipping install.
)

REM ==========================================================
REM Final sanity check
REM ==========================================================

python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo ERROR: Streamlit still not found after sync. Something went wrong.
    pause
    exit /b 1
)

echo Environment "%ENV_NAME%" verified. Launching app...

REM ==========================================================
REM Launch
REM ==========================================================

streamlit run Home.py --server.address=0.0.0.0 --server.port=8501

pause
