@echo off
title Launching Streamlit App

echo ----------------------------------------
echo Initializing Anaconda Environment...
echo ----------------------------------------

:: 1. Initialize Conda for Windows Command Prompt
call "%USERPROFILE%\anaconda3\Scripts\activate.bat"
if errorlevel 1 call "%USERPROFILE%\miniconda3\Scripts\activate.bat"
if errorlevel 1 call "%ProgramData%\anaconda3\Scripts\activate.bat"

echo Launching Streamlit App...
echo Share your Local IP with people on your Wi-Fi!
echo ----------------------------------------

:: 2. Run Streamlit directly inside the custom environment
conda run -n JFC-Embodied-Carbon-App --no-capture-output streamlit run app.py --server.address=0.0.0.0 --server.port=8501

:: 3. Keep window open if it fails so users can see errors
if errorlevel 1 (
    echo.
    echo Streamlit failed to start or crashed.
    pause
)
