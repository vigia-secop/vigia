# Sube el proyecto a GitHub, para que no viva solo en este disco.
#
#   Clic derecho sobre este archivo -> "Ejecutar con PowerShell"
#
# ANTES hay que haber corrido guardar-en-git.ps1 al menos una vez.
#
# La primera vez pide la direccion del repositorio, que se crea en github.com
# (el script te dice como). Las siguientes veces solo sube lo nuevo.
#
# La contrasena de GitHub NO se escribe aqui. Git abre tu navegador y te
# autenticas ahi, en la pagina de GitHub. Este script nunca la ve.

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "github-ultima-corrida.txt"
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
function Git-Callado([string[]]$a) {
    try { & git @a *> $null; if ($null -eq $LASTEXITCODE) { return 0 }; return $LASTEXITCODE } catch { return 1 }
}
function Git-Visible([string[]]$a) {
    try { & git @a 2>&1 | Out-Host; if ($null -eq $LASTEXITCODE) { return 0 }; return $LASTEXITCODE }
    catch { Write-Host "   $_" -ForegroundColor Red; return 1 }
}

Write-Host "Subir Vigia SECOP a GitHub" -ForegroundColor White
Write-Host "Carpeta: $raiz"
Write-Host ""

# ---- git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    foreach ($r in @("C:\Program Files\Git\cmd\git.exe", "C:\Program Files (x86)\Git\cmd\git.exe", "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe")) {
        if (Test-Path $r) { $env:PATH = (Split-Path $r) + ";" + $env:PATH; break }
    }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Mal "No encuentro git. Instalalo desde https://git-scm.com/download/win"
}
if (-not (Test-Path (Join-Path $raiz ".git"))) {
    Mal "Aqui no hay repositorio todavia. Corre primero guardar-en-git.ps1."
}
if ((Git-Callado @("rev-parse", "HEAD")) -ne 0) {
    Mal "El repositorio existe pero no tiene ni un commit. Corre primero guardar-en-git.ps1."
}
Bien "repositorio local listo"

# ---- Lo que se va a subir, a la vista ANTES de subirlo.
#      Una vez en GitHub, quitar un archivo del historial es dificil.
$archivos = (& git ls-files) | Where-Object { $_ }
Write-Host ""
Write-Host "Se van a subir $($archivos.Count) archivos:" -ForegroundColor Cyan
$archivos | ForEach-Object { Split-Path $_ -Parent } |
    ForEach-Object { if ($_) { $_.Split('\')[0] } else { "(raiz)" } } |
    Group-Object | Sort-Object Count -Descending |
    ForEach-Object { Write-Host ("   {0,3}  {1}" -f $_.Count, $_.Name) -ForegroundColor DarkGray }

Write-Host ""
if ((Git-Callado @("check-ignore", "-q", ".env")) -eq 0) {
    Bien ".env queda FUERA: tu token de Socrata no se sube"
} else {
    Mal "El .env NO esta excluido. Detente: subirlo publicaria tu token. Revisa el .gitignore."
}

# ---- remoto
$remoto = (& git remote get-url origin 2>$null)
if ($LASTEXITCODE -ne 0) { $remoto = $null }

if (-not $remoto) {
    Write-Host ""
    Write-Host "PRIMERA VEZ. Hay que crear el repositorio vacio en GitHub:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   1. Entra a  https://github.com/new" -ForegroundColor White
    Write-Host "   2. Repository name:  vigia-secop" -ForegroundColor White
    Write-Host "   3. Marca  >> Private <<  (recomendado; se puede abrir despues)" -ForegroundColor White
    Write-Host "   4. NO marques 'Add a README', ni .gitignore, ni licencia." -ForegroundColor White
    Write-Host "      Tiene que quedar completamente vacio o el primer envio choca." -ForegroundColor DarkGray
    Write-Host "   5. Create repository" -ForegroundColor White
    Write-Host "   6. Copia la direccion que te muestra, la que termina en .git" -ForegroundColor White
    Write-Host ""
    $remoto = (Read-Host "   Pega aqui la direccion").Trim()
    if (-not $remoto) { Mal "sin direccion no hay a donde subir" }
    if ($remoto -notmatch '^(https://github\.com/|git@github\.com:)') {
        Mal "Eso no parece una direccion de GitHub. Debe empezar por https://github.com/"
    }
    if ((Git-Callado @("remote", "add", "origin", $remoto)) -ne 0) { Mal "no pude registrar el remoto" }
    Bien "remoto registrado: $remoto"
} else {
    Bien "remoto ya configurado: $remoto"
}

# ---- confirmacion explicita
Write-Host ""
Write-Host "   Lo siguiente COPIA tu proyecto a los servidores de GitHub." -ForegroundColor Yellow
Write-Host "   Si el repositorio quedo publico, cualquiera podra leerlo." -ForegroundColor Yellow
$ok = Read-Host "   Escribe SUBIR para continuar (cualquier otra cosa cancela)"
if ($ok -ne "SUBIR") {
    Write-Host ""
    Aviso "Cancelado. No se subio nada."
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "Enter para cerrar"
    exit 0
}

# ---- rama y envio
Git-Callado @("branch", "-M", "main") | Out-Null

Write-Host ""
Write-Host "Subiendo. Si se abre una ventana del navegador, autenticate ahi:" -ForegroundColor Cyan
Write-Host "es GitHub pidiendote permiso, no este script." -ForegroundColor DarkGray
Write-Host ""

if ((Git-Visible @("push", "-u", "origin", "main")) -ne 0) {
    Mal "El envio fallo. Causas comunes: el repositorio de GitHub no estaba vacio, la direccion tiene una errata, o cancelaste la autenticacion. Mira el mensaje de arriba."
}

Write-Host ""
Bien "subido"
$web = $remoto -replace '\.git$', '' -replace '^git@github\.com:', 'https://github.com/'
Write-Host ""
Write-Host "Tu proyecto vive ahora en:" -ForegroundColor White
Write-Host "   $web" -ForegroundColor Cyan
Write-Host ""
Write-Host "De aqui en adelante: primero guardar-en-git.ps1, luego este." -ForegroundColor White
Write-Host "Ya existe copia fuera de este disco." -ForegroundColor White
Write-Host ""
Write-Host "Todo lo anterior quedo escrito en: $REGISTRO" -ForegroundColor DarkGray
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
