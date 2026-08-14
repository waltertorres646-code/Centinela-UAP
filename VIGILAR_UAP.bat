@echo off
setlocal
cd /d "%~dp0"
title Centinela UAP - Solo lectura

if not exist ".venv\Scripts\python.exe" (
    echo Primero ejecuta INSTALAR_Y_PROBAR.bat.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
echo Vigilando r/UFOs cada 5 minutos. Para detener: Ctrl+C.
python centinela_uap.py --subreddit UFOs --limite 50 --vigilar --cada 300
pause
