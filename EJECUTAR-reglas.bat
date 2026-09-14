@echo off
rem Motor de Reglas (epica 2: historias 2.1, 2.2, 2.3 y 2.6).
rem Instala el codigo y corre sus pruebas. No toca la base de datos.

cd /d "%~dp0"
echo ============================================
echo  Epica 2 -- motor de Reglas
echo ============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0aplicar-epica-2.ps1"
echo.
pause
