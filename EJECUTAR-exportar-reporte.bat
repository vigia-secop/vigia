@echo off
rem Lanzador para exportar-reporte.ps1 -- SOLO LECTURA.

cd /d "%~dp0"
echo ============================================
echo  Exportar reporte.json (solo lectura)
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0exportar-reporte.ps1"

echo.
echo ============================================
echo  PowerShell termino con codigo %ERRORLEVEL%
echo ============================================
echo.
pause
