@echo off
rem Panel de Vigia. Consulta tu base (solo lectura), dibuja la pagina y la abre.

cd /d "%~dp0"
echo ============================================
echo  Panel de Vigia
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0panel.ps1"
echo.
pause
