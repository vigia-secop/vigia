@echo off
rem Aplica la 1.5b y enseguida corre las uniones temporales.
rem Un solo doble clic. Lo lanza Claude.

cd /d "%~dp0"
echo ============================================
echo  1.5b -- aplicar archivos
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0aplicar-1-5b.ps1"
if errorlevel 1 goto :fin

echo.
echo ============================================
echo  Uniones temporales y consorcios
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uniones.ps1"

:fin
echo.
pause
