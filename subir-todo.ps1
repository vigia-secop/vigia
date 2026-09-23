# SUBIR TODO LO NUEVO A GITHUB. Un solo paso, sin preguntas.
#
#     Doble clic en EJECUTAR-SUBIR-TODO.bat
#
# QUE HACE. `git add -A`, un commit con la fecha y `git push`. Nada mas.
#
# POR QUE EXISTE, HABIENDO YA `guardar-en-git.ps1`. Ese guarda en el disco y
# pide el mensaje del commit por teclado; sirve cuando hay alguien sentado al
# frente. Este no pregunta nada, y ademas empuja a GitHub: es el que se puede
# correr solo, o de a un clic, cuando lo unico que se quiere es que lo que hay
# en la carpeta quede tambien en el repositorio.
#
# QUE NO SUBE. Lo que diga `.gitignore`: el `.env` con el token, los JSON de
# trabajo, la bitacora y la carpeta `pliego`. Pliego es el servicio que se
# cobra y Vigia es publico: no se mezclan en el mismo repositorio.
#
# `publicar.ps1` sigue haciendo lo suyo (construir el sitio y subir `docs`)
# todos los dias. Este es para el codigo y las consultas, que cambian a
# saltos y no todos los dias.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "subir-todo-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

# Un comando nativo que escribe en stderr pinta la consola de rojo si su
# salida se canaliza con Out-Host: PowerShell 5.1 la envuelve en un
# NativeCommandError. git escribe en stderr hasta para decir que todo salio
# bien. Write-Host linea por linea lo dice igual, en gris y sin susto.
function Correr-Git([string[]]$Argumentos) {
    & git @Argumentos 2>&1 | ForEach-Object {
        $t = "$_"; if ($t.Trim()) { Write-Host "   $t" -ForegroundColor Gray }
    }
    return $LASTEXITCODE
}

Write-Host ""
Write-Host "  SUBIR TODO LO NUEVO A GITHUB" -ForegroundColor White
Write-Host "  Carpeta: $raiz" -ForegroundColor DarkGray
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "  No encontre git. Instalalo desde git-scm.com y vuelve." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}
if (-not (Test-Path (Join-Path $raiz ".git"))) {
    Write-Host "  Esta carpeta no es un repositorio. Corre antes EJECUTAR-guardar-en-git.bat." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

Write-Host "  Lo que va a entrar:" -ForegroundColor White
Correr-Git @("add", "-A") | Out-Null
Correr-Git @("status", "--short") | Out-Null

# `diff --cached --quiet` devuelve 1 cuando SI hay algo preparado. Sin esta
# comprobacion, un dia sin cambios terminaria en "nothing to commit" con
# codigo de error y pareceria que fallo algo.
& git diff --cached --quiet
$hayCambios = ($LASTEXITCODE -ne 0)

if (-not $hayCambios) {
    Write-Host ""
    Write-Host "  No hay nada nuevo que guardar. El repositorio ya esta al dia." -ForegroundColor Green
} else {
    $mensaje = "Avance del " + (Get-Date -Format "yyyy-MM-dd HH:mm")
    Write-Host ""
    Write-Host "  Commit: $mensaje" -ForegroundColor White
    if ((Correr-Git @("commit", "-m", $mensaje)) -ne 0) {
        Write-Host "  El commit fallo. Mira las lineas de arriba." -ForegroundColor Red
        try { Stop-Transcript | Out-Null } catch { }
        exit 1
    }
}

Write-Host ""
Write-Host "  Subiendo a GitHub..." -ForegroundColor White
if ((Correr-Git @("push")) -ne 0) {
    Write-Host "  El push fallo. Lo mas comun: no hay internet, o GitHub pidio la" -ForegroundColor Red
    Write-Host "  contrasena. El commit ya quedo guardado en el disco; vuelve a" -ForegroundColor Red
    Write-Host "  correr esto cuando se resuelva y sube igual." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

Write-Host ""
Write-Host "  Listo. Lo nuevo ya esta en el repositorio." -ForegroundColor Green
Write-Host "  Ultimos commits:" -ForegroundColor DarkGray
Correr-Git @("log", "--oneline", "-5") | Out-Null
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
