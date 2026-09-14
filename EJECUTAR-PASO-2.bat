@echo off
REM PASO 2 - deja el repositorio firmando anonimo. NO sube nada.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0paso-2-identidad.ps1"
