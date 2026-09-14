@echo off
REM Mide si se puede construir la bandera 4.2 (adjudicacion pegada al
REM presupuesto). SOLO LECTURA: no cambia nada en la base.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0presupuesto.ps1"
echo.
pause
