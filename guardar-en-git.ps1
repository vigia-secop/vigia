# Guarda el proyecto en git: la red de seguridad.
#
#   Clic derecho sobre este archivo -> "Ejecutar con PowerShell"
#
# Requiere git instalado (https://git-scm.com/download/win).
#
# Se puede correr las veces que quieras. La primera vez crea el repositorio;
# las siguientes guardan lo que haya cambiado desde la vez anterior. Nunca
# borra nada ni sube nada a internet: todo queda en esta misma carpeta.

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "git-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

trap {
    Write-Host ""
    Write-Host "   ERROR NO PREVISTO -- esto es un fallo del script, no tuyo:" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
    Write-Host "   linea $($_.InvocationInfo.ScriptLineNumber): $($_.InvocationInfo.Line.Trim())" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

function Bien($m)  { Write-Host "   OK  $m" -ForegroundColor Green }
function Aviso($m) { Write-Host "   --  $m" -ForegroundColor Yellow }
function Mal($m) {
    Write-Host ""
    Write-Host "   FALLO: $m" -ForegroundColor Red
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

# Un comando nativo que escribe en stderr termina el script cuando
# ErrorActionPreference vale Stop. git escribe en stderr constantemente, y
# casi siempre son avisos, no errores. Sin este envoltorio el script se
# muere en el primer `git init`.
function Git-Callado([string[]]$argumentos) {
    try { & git @argumentos *> $null; if ($null -eq $LASTEXITCODE) { return 0 }; return $LASTEXITCODE }
    catch { return 1 }
}
function Git-Visible([string[]]$argumentos) {
    try { & git @argumentos 2>&1 | Out-Host; if ($null -eq $LASTEXITCODE) { return 0 }; return $LASTEXITCODE }
    catch { Write-Host "   $_" -ForegroundColor Red; return 1 }
}

Write-Host "Guardar Vigia SECOP en git" -ForegroundColor White
Write-Host "Carpeta: $raiz"
Write-Host ""

# ---- git instalado?
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    foreach ($ruta in @(
        "C:\Program Files\Git\cmd\git.exe",
        "C:\Program Files (x86)\Git\cmd\git.exe",
        "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
    )) {
        if (Test-Path $ruta) { $env:PATH = (Split-Path $ruta) + ";" + $env:PATH; $git = $true; break }
    }
}
if (-not $git) {
    Mal "No encuentro git. Instalalo desde https://git-scm.com/download/win y vuelve a correr esto. Si acabas de instalarlo, cierra esta ventana y abrela de nuevo: el PATH solo se actualiza en ventanas nuevas."
}
Bien ((& git --version) -join " ")

# ---- repositorio
$primeraVez = -not (Test-Path (Join-Path $raiz ".git"))
if ($primeraVez) {
    if ((Git-Visible @("init", "-b", "main")) -ne 0) { Mal "git init fallo" }
    Bien "repositorio creado"
} else {
    Bien "el repositorio ya existia"
}

# ---- identidad: git se niega a hacer commit sin ella
function Config-Git($clave) {
    try { $v = & git config $clave 2>$null; if ($LASTEXITCODE -ne 0) { return $null }; return $v }
    catch { return $null }
}
$nombre = Config-Git "user.name"
$correo = Config-Git "user.email"
if (-not $nombre -or -not $correo) {
    Write-Host ""
    Write-Host "   git necesita saber quien hace los cambios. Se guarda solo en ESTA" -ForegroundColor Yellow
    Write-Host "   carpeta, no se manda a ninguna parte." -ForegroundColor Yellow
    if (-not $nombre) {
        $nombre = Read-Host "   Tu nombre"
        if (-not $nombre) { Mal "sin nombre no se puede firmar el commit" }
        Git-Callado @("config", "user.name", $nombre) | Out-Null
    }
    if (-not $correo) {
        $correo = Read-Host "   Tu correo"
        if (-not $correo) { Mal "sin correo no se puede firmar el commit" }
        Git-Callado @("config", "user.email", $correo) | Out-Null
    }
}
Bien "firma: $nombre <$correo>"

# ---- limpieza: archivos ya versionados que el .gitignore excluye
#
# Anadir una regla al .gitignore NO saca lo que ya estaba guardado: git sigue
# siguiendo esos archivos hasta que se le dice explicitamente que pare. Sin
# este paso, una regla nueva parece funcionar y no funciona.
#
# `git rm --cached` los saca del control de versiones y DEJA EL ARCHIVO en el
# disco. No borra nada tuyo.
$fantasmas = (& git ls-files -i -c --exclude-standard) | Where-Object { $_ }
if ($fantasmas) {
    Write-Host ""
    Write-Host "   Quitando del control de versiones $($fantasmas.Count) archivos que el .gitignore ya excluye." -ForegroundColor Yellow
    Write-Host "   (siguen en tu disco; solo dejan de guardarse)" -ForegroundColor DarkGray
    # De a 200 por vez: una linea de comando con miles de rutas no cabe en Windows.
    for ($i = 0; $i -lt $fantasmas.Count; $i += 200) {
        $lote = $fantasmas[$i..([Math]::Min($i + 199, $fantasmas.Count - 1))]
        Git-Callado (@("rm", "-r", "--cached", "--quiet", "--") + $lote) | Out-Null
    }
}

# ---- que se va a guardar
Write-Host ""
Write-Host "Lo que cambio desde la ultima vez:" -ForegroundColor Cyan
Git-Visible @("add", "-A") | Out-Null
Git-Visible @("status", "--short") | Out-Null

$pendientes = (& git status --porcelain) | Where-Object { $_ }
if (-not $pendientes) {
    Write-Host ""
    Bien "no hay nada nuevo que guardar: ya esta todo a salvo"
    Write-Host ""
    Write-Host "Todo lo anterior quedo escrito en: $REGISTRO" -ForegroundColor DarkGray
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "Enter para cerrar"
    exit 0
}

Write-Host ""
Write-Host ("   " + $pendientes.Count + " archivos") -ForegroundColor DarkGray
Write-Host ""

$sugerido = if ($primeraVez) {
    "Epica 1: historias 1.1, 1.2 y 1.3, verificadas contra la fuente y PostgreSQL reales"
} else {
    "Avance del " + (Get-Date -Format "yyyy-MM-dd HH:mm")
}

Write-Host "   Mensaje sugerido:" -ForegroundColor Yellow
Write-Host "   $sugerido" -ForegroundColor White
$mensaje = Read-Host "   Enter para usarlo, o escribe otro"
if (-not $mensaje) { $mensaje = $sugerido }

if ((Git-Visible @("commit", "-m", $mensaje)) -ne 0) { Mal "el commit fallo (mira el mensaje de arriba)" }

Write-Host ""
Bien "guardado"
Write-Host ""
Write-Host "Historial:" -ForegroundColor Cyan
Git-Visible @("log", "--oneline", "-5") | Out-Null

Write-Host ""
Write-Host "A partir de ahora, cada vez que cambies algo importante, vuelve a" -ForegroundColor White
Write-Host "correr este archivo. Si algo se rompe, se puede volver atras." -ForegroundColor White
Write-Host ""
Write-Host "Ojo: esto guarda en TU disco, no en internet. Si se dana el disco, se" -ForegroundColor Yellow
Write-Host "pierde igual. Subirlo a GitHub es otro paso, para cuando quieras." -ForegroundColor Yellow
Write-Host ""
Write-Host "Todo lo anterior quedo escrito en: $REGISTRO" -ForegroundColor DarkGray
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
