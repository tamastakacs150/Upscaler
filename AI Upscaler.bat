@echo off
title AI Upscaler
cd /d "%~dp0"

set "VPY=.venv\Scripts\python.exe"

rem --- mukodik-e a venv, es megvannak-e a csomagok? ---
if not exist "%VPY%" goto rebuild
"%VPY%" -c "import flask, waitress" >nul 2>&1
if errorlevel 1 goto rebuild
goto run


:rebuild
echo.
echo A virtualis kornyezet hianyzik vagy el van torve (pl. frissult a Python).
echo Ujraepitem. Ez egyszer fut le, kb. egy percig tart.
echo.

set "SYSPY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "SYSPY=py -3"
if defined SYSPY goto havepy

python --version >nul 2>&1
if not errorlevel 1 set "SYSPY=python"
if defined SYSPY goto havepy

echo [HIBA] Nem talalok Python-t a gepen.
echo Telepitsd innen: https://www.python.org/downloads/
echo Telepiteskor pipald be az "Add python.exe to PATH" opciot.
echo.
pause
exit /b 1

:havepy
echo Talalt Python: %SYSPY%
if exist ".venv" (
    echo Regi .venv torlese...
    rmdir /s /q ".venv"
)
echo Uj .venv keszitese...
%SYSPY% -m venv .venv
if not exist "%VPY%" goto venvfail

echo Csomagok telepitese a requirements.txt alapjan...
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto pipfail
echo.
echo A kornyezet kesz.
echo.
goto run

:venvfail
echo.
echo [HIBA] A .venv letrehozasa nem sikerult.
pause
exit /b 1

:pipfail
echo.
echo [HIBA] A csomagok telepitese nem sikerult. Van internet?
pause
exit /b 1


:run
if not exist "static\app\index.html" (
    echo [FIGYELEM] Nincs epitett frontend a static\app alatt.
    echo Epitsd meg egyszer:  cd frontend ^&^& npm install ^&^& npm run build
    echo.
)

echo Indul az AI Upscaler...
echo Cim: http://localhost:7860
echo A leallitashoz zard be ezt az ablakot, vagy nyomj Ctrl+C-t.
echo.

rem A bongeszot kesleltetve nyitjuk, hogy a szerver mar alljon
start "" cmd /c "timeout /t 4 /nobreak >nul & start "" http://localhost:7860"

"%VPY%" app.py

echo.
echo A szerver leallt.
pause
