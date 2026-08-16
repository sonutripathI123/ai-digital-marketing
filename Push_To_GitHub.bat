@echo off
title Push AI Digital Marketing to GitHub
echo ========================================================
echo Pushing AI Digital Marketing Command Center to GitHub...
echo ========================================================
echo.
cd /d "%~dp0"

echo [1/3] Setting branch to main...
git branch -M main

echo [2/3] Adding changes...
git add .
git commit -m "feat: AI Digital Marketing Command Center" >nul 2>&1

echo [3/3] Uploading to GitHub...
git push -u origin main

echo.
if %errorlevel% equ 0 (
    echo ========================================================
    echo [SUCCESS] Code uploaded to GitHub successfully!
    echo ========================================================
) else (
    echo ========================================================
    echo [NOTICE] If a browser login popup appeared, please click 'Authorize'
    echo ========================================================
)
echo.
pause
