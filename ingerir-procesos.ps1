# Ingerir el dataset `procesos` y volver a normalizar.
#
#   Doble clic en EJECUTAR-ingerir-procesos.bat
#
# POR QUE
# Contratos y Procesos son las dos mitades del cruce de la historia 1.4. Con
# solo Contratos ingeridos, el 100 % de los contratos sale huerfano y ese
# numero no dice nada: no hay contra que cruzar. Este guion trae la otra mitad
# y vuelve a normalizar, para que el porcentaje de huerfanos pase a ser una
# medida de la fuente y no del hueco en la base.
#
# EL RANGO IMPORTA. Un contrato firmado en agosto puede venir de un Proceso
# publicado meses antes. Si la ventana de Procesos es mas corta que esa
# distancia, saldran huerfanos que no lo son. Por eso la ventana de abajo es
# deliberadamente mas ancha que la de Contratos, y el numero que salga hay que
# leerlo como un TECHO del huerfanaje real, no como el dato definitivo.

$DESDE = "2026-07-01"
$HASTA = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "procesos-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

trap {
    Write-Host ""
    Write-Host "   ERROR NO PREVISTO:" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
    Write-Host "   linea $($_.InvocationInfo.ScriptLineNumber)" -ForegroundColor DarkGray
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

$DSN_VIGIA = "postgresql://vigia:vigia@localhost:5432/vigia"

function Paso($n, $titulo) {
    Write-Host ""
    Write-Host "== $n : $titulo" -ForegroundColor Cyan
}
function Bien($m) { Write-Host "   OK  $m" -ForegroundColor Green }
function Aviso($m) { Write-Host "   --  $m" -ForegroundColor Yellow }
function Mal($m) {
    Write-Host ""
    Write-Host "   FALLO: $m" -ForegroundColor Red
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}
function Visible {
    param([string]$exe, [string[]]$argumentos = @())
    try {
        & $exe @argumentos | Out-Host
        if ($null -eq $LASTEXITCODE) { return 0 }
        return $LASTEXITCODE
    } catch { Write-Host "   $_" -ForegroundColor Red; return 1 }
}
function Buscar-Herramienta($nombre) {
    $enPath = Get-Command $nombre -ErrorAction SilentlyContinue
    if ($enPath) { return $enPath.Source }
    foreach ($raizPg in @("C:\Program Files\PostgreSQL", "C:\Program Files (x86)\PostgreSQL")) {
        if (-not (Test-Path $raizPg)) { continue }
        $versiones = Get-ChildItem $raizPg -Directory -ErrorAction SilentlyContinue |
            Sort-Object { if ($_.Name -match '^(\d+)') { [int]$Matches[1] } else { 0 } } -Descending
        foreach ($v in $versiones) {
            $ruta = Join-Path $v.FullName "bin\$nombre.exe"
            if (Test-Path $ruta) { return $ruta }
        }
    }
    return $null
}

Write-Host "Vigia SECOP - ingesta de Procesos y nuevo cruce" -ForegroundColor White
Write-Host "Esto SI escribe en tu base de datos. Correrlo es la confirmacion." -ForegroundColor Yellow

# ---------------------------------------------------------------- 1 de 4
Paso "1 de 4" "Herramientas"
$pyExe = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() }, @{ exe = "python3"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $version = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($version -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; Bien $version.Trim(); break
    }
}
if (-not $pyExe) { Mal "No encuentro Python 3.11 o superior." }
$PSQL = Buscar-Herramienta "psql"
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

# ---------------------------------------------------------------- 2 de 4
Paso "2 de 4" "Configuracion"
if (Test-Path ".env") {
    Get-Content ".env" | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
        $nombreVar, $valorVar = $_ -split '=', 2
        Set-Item -Path ("Env:" + $nombreVar.Trim()) -Value $valorVar.Trim()
    }
    Bien ".env cargado"
}
if ($env:VIGIA_TOKEN_SOCRATA) {
    Remove-Item Env:VIGIA_TOKEN_SOCRATA -ErrorAction SilentlyContinue
    Aviso "token de Socrata ignorado a proposito (esta vencido; sin el la API funciona igual)"
}
$env:VIGIA_DSN = $DSN_VIGIA

# ---------------------------------------------------------------- 3 de 4
Paso "3 de 4" "Ingesta de Procesos"
Write-Host "   rango: $DESDE a $HASTA  (dos meses: mas ancho que el de Contratos, a proposito)"
Write-Host "   el dataset trae una fila por ADJUDICACION, asi que son bastantes paginas." -ForegroundColor DarkGray
Write-Host "   puede tardar varios minutos. No cierres la ventana." -ForegroundColor DarkGray
Write-Host ""
& $pyExe @pyArgs -m vigia --dataset procesos --desde $DESDE --hasta $HASTA
if ($LASTEXITCODE -ne 0) { Mal "La ingesta de Procesos fallo." }
Bien "Procesos en tu base"

# ---------------------------------------------------------------- 4 de 4
Paso "4 de 4" "Cruzar otra vez, ahora con las dos mitades"
Write-Host ""
& $pyExe @pyArgs -m vigia.normalizado --dsn $DSN_VIGIA
if ($LASTEXITCODE -ne 0) { Mal "La normalizacion fallo." }

Write-Host ""
Write-Host "   ESTE es el numero que llevabamos toda la semana buscando:" -ForegroundColor White
Write-Host "   el porcentaje de huerfanos de arriba, ya con Procesos ingeridos." -ForegroundColor White
Write-Host "   Leelo como un TECHO: parte del huerfanaje puede ser solo ventana corta." -ForegroundColor DarkGray

if ($PSQL) {
    Write-Host ""
    Visible $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d","vigia","-q","-v","ON_ERROR_STOP=1","-c",
        "SELECT count(*) AS contratos, count(id_del_proceso) AS enlazados, round(100.0*count(id_del_proceso)/nullif(count(*),0),1) AS pct_enlazados FROM contrato;") | Out-Null
    Visible $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d","vigia","-q","-v","ON_ERROR_STOP=1","-c",
        "SELECT count(*) AS procesos FROM proceso;") | Out-Null
}

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "== TERMINADO ==" -ForegroundColor Green
Write-Host "Quedo escrito en: $REGISTRO" -ForegroundColor DarkGray
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
