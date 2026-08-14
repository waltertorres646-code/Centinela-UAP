@echo off
setlocal
cd /d "%~dp0"
title Centinela UAP - Instalacion y prueba

where py >nul 2>nul
if errorlevel 1 (
    echo No encuentro Python. Instala Python 3 y marca "Add Python to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno aislado...
    py -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo Se abrira el archivo .env. Completa solo los tres valores de Reddit,
    echo guarda el archivo y vuelve a ejecutar este boton.
    start "" notepad ".env"
    pause
    exit /b 0
)

echo.
echo Prueba controlada: 10 publicaciones, solo lectura, cero publicaciones.
python centinela_uap.py --limite 10
if errorlevel 1 goto :error
echo.
echo Prueba terminada. Revisa la carpeta datos.
pause
exit /b 0

:error
echo.
echo La maniobra se detuvo sin publicar nada.
pause
exit /b 1
