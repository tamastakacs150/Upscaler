@echo off
title AI Upscaler
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [HIBA] Nincs .venv a mappaban.
    echo Hozd letre egyszer ezekkel:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist "static\app\index.html" (
    echo.
    echo [FIGYELEM] Nincs epitett frontend a static\app alatt.
    echo A felulet nem fog betoltodni. Epitsd meg egyszer:
    echo     cd frontend ^&^& npm install ^&^& npm run build
    echo.
)

echo Indul az AI Upscaler...
echo Cim: http://localhost:7860
echo A leallitashoz zard be ezt az ablakot, vagy nyomj Ctrl+C-t.
echo.

rem A bongeszot kesleltetve nyitjuk, hogy a szerver mar alljon
start "" cmd /c "timeout /t 4 /nobreak >nul & start "" http://localhost:7860"

".venv\Scripts\python.exe" app.py

echo.
echo A szerver leallt.
pause
