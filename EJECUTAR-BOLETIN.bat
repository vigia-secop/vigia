@echo off
REM Arma el hilo de la semana pasada, listo para leer y publicar a mano.
REM No publica nada: eso lo hace una persona.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0boletin.ps1"
echo.
pause
