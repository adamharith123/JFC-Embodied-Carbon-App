@echo off
setlocal enabledelayedexpansion

set PORT=8501
set FOUND=0

for /f "tokens=5" %%P in ('netstat -ano ^| findstr :%PORT% ^| findstr LISTENING') do (
    echo Stopping app running on port %PORT% ^(PID: %%P^)...
    taskkill /PID %%P /F
    set FOUND=1
)

if "%FOUND%"=="0" (
    echo No app is currently running on port %PORT%.
)

pause