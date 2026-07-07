@echo off
setlocal

set ENV_NAME=JFC-Embodied-Carbon-App

REM Move to this script's own folder so relative paths (data\, utils\) resolve correctly
cd /d "%~dp0"

REM Check the environment exists
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

REM Verify Streamlit is actually installed in this environment
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo ERROR: Streamlit is not installed in "%ENV_NAME%".
    echo Run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo Environment "%ENV_NAME%" verified. Launching app...

streamlit run app.py --server.address=0.0.0.0 --server.port=8501

pause