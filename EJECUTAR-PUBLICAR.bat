@echo off
REM Construye el sitio publico y lo sube a GitHub Pages.
REM Aborta si algo que git subiria trae un documento de identidad.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publicar.ps1"
echo.
pause
