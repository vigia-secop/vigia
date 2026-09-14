@echo off
rem Aplica la 1.6 y ensena el territorio. Un solo doble clic.

cd /d "%~dp0"
echo ============================================
echo  1.6 -- territorio y orden administrativo
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0aplicar-1-6.ps1"
if errorlevel 1 goto :fin
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0territorio.ps1"
:fin
echo.
pause
