@echo off
REM Corre la bandera de fraccionamiento en modo CALIBRACION.
REM
REM No publica nada, no manda nada a ninguna cola y NO activa la bandera.
REM Deja un informe -calibracion-fraccionamiento.txt- para leer con los ojos.
REM Empieza por la cobertura: dice cuantas entidades NO se pudieron mirar.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0calibrar-fraccionamiento.ps1"
echo.
pause
