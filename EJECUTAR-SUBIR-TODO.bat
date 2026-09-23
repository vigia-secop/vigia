@echo off
REM ============================================================
REM   VIGIA SECOP - SUBIR TODO LO NUEVO A GITHUB
REM   Sin preguntas: add, commit con la fecha y push.
REM ============================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0subir-todo.ps1"
echo.
pause
