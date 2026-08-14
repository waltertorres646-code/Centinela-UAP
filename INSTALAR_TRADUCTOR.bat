@echo off
setlocal
cd /d "%~dp0"
title Centinela UAP - Traductor local

if not exist ".venv\Scripts\python.exe" (
    echo Primero ejecuta INSTALAR_Y_PROBAR.bat.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
echo Instalando el motor de traduccion local...
python -m pip install -r requirements-traductor.txt
if errorlevel 1 goto :error
python instalar_traductor.py
if errorlevel 1 goto :error
echo.
echo Listo. Las nuevas publicaciones en ingles tendran titulo y texto en espanol.
pause
exit /b 0

:error
echo.
echo No se instalo el traductor. El Centinela puede seguir trabajando sin el.
pause
exit /b 1
