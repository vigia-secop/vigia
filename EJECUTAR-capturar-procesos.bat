@echo off
rem Lanzador para capturar-procesos.ps1
rem
rem Doble clic aqui. A diferencia de "Ejecutar con PowerShell", esta ventana
rem NO se cierra sola: si PowerShell se niega a correr el script, el motivo
rem queda escrito en pantalla en vez de desaparecer.

cd /d "%~dp0"
echo ============================================
echo  capturar-procesos.ps1
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0capturar-procesos.ps1"

echo.
echo ============================================
echo  PowerShell termino con codigo %ERRORLEVEL%
echo ============================================
echo.
echo Si arriba no salio nada, algo esta bloqueando los scripts
echo (antivirus o directiva de Windows). Copia lo que veas y mandalo.
echo.
pause
