# Ingerir de verdad y normalizar. Los pasos 9 y 10 de probar.ps1, sueltos.
#
#   Doble clic en EJECUTAR-ingerir-y-normalizar.bat
#
# POR QUE EXISTE ESTE ARCHIVO
# El 2026-09-03 la corrida de probar.ps1 llego intacta hasta el paso 9 y la
# ventana se cerro EXACTAMENTE en el `Read-Host` que pedia escribir SI. Los
# ocho pasos anteriores habian pasado; lo unico que quedaba era escribir en la
# base. Repetir los 26 paginas de consulta en seco para volver a llegar al
# mismo sitio es dos minutos tirados y otra oportunidad de que se cierre.
#
# Asi que aqui NO se pregunta nada antes de trabajar. Correr este archivo ES
# el consentimiento. La unica pausa esta al final, cuando ya no queda nada
# que perder.

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "ingesta-ultima-corrida.txt"
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

$DSN_VIGIA = "postgresql://vigia:vigia@localhost:5432/vigia"

function Paso($numero, $titulo) {
    Write-Host ""
    Write-Host "== $numero : $titulo" -ForegroundColor Cyan
}
function Bien($mensaje) { Write-Host "   OK  $mensaje" -ForegroundColor Green }
function Aviso($mensaje) { Write-Host "   --  $mensaje" -ForegroundColor Yellow }
function Mal($mensaje) {
    Write-Host ""
    Write-Host "   FALLO: $mensaje" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    Write-Host "   Manda ese archivo y se arregla." -ForegroundColor Yellow
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
    } catch {
        Write-Host "   $_" -ForegroundColor Red
        return 1
    }
}

# EnterpriseDB no mete bin\ en el PATH. Se busca en las rutas habituales,
# ordenando por el numero de version de verdad: "9.6" no puede ganarle a "17".
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

Write-Host "Vigia SECOP - ingesta real y normalizacion" -ForegroundColor White
Write-Host "Carpeta: $raiz"
Write-Host ""
Write-Host "Esto SI escribe en tu base de datos. Correrlo es la confirmacion." -ForegroundColor Yellow

# ---------------------------------------------------------------- 1 de 5
Paso "1 de 5" "Herramientas"

$pyExe = $null
$pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() }, @{ exe = "python3"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $version = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($version -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe
        $pyArgs = $c.args
        Bien $version.Trim()
        break
    }
}
if (-not $pyExe) { Mal "No encuentro Python 3.11 o superior." }

$PSQL = Buscar-Herramienta "psql"
if ($PSQL) { Bien "psql en $PSQL" } else { Aviso "sin psql: no podre ensenarte las tablas al final, pero el trabajo se hace igual" }

$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

# ---------------------------------------------------------------- 2 de 5
Paso "2 de 5" "Configuracion"

if (Test-Path ".env") {
    Get-Content ".env" | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
        $nombreVar, $valorVar = $_ -split '=', 2
        Set-Item -Path ("Env:" + $nombreVar.Trim()) -Value $valorVar.Trim()
    }
    Bien ".env cargado"
} else {
    Aviso "sin .env: van los valores por defecto"
}

# El token de Socrata de este equipo esta vencido: la fuente respondio 403
# "Invalid app_token specified" el 2026-09-03, y la misma consulta paso las 26
# paginas sin el. Una credencial OPCIONAL no puede bloquear nada, asi que se
# quita antes de empezar en vez de descubrirlo a mitad del recorrido.
if ($env:VIGIA_TOKEN_SOCRATA) {
    Remove-Item Env:VIGIA_TOKEN_SOCRATA -ErrorAction SilentlyContinue
    Aviso "token de Socrata ignorado a proposito (esta vencido; sin el la API funciona igual)"
}

$env:VIGIA_DSN = $DSN_VIGIA

# ---------------------------------------------------------------- 3 de 5
Paso "3 de 5" "Ingesta real de Contratos"

$hasta = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
$desde = (Get-Date).AddDays(-8).ToString("yyyy-MM-dd")
Write-Host "   rango: $desde a $hasta"
Write-Host "   son unas 26 paginas: minuto y medio, mas o menos. No cierres la ventana." -ForegroundColor DarkGray
Write-Host ""

& $pyExe @pyArgs -m vigia --dataset contratos --desde $desde --hasta $hasta
if ($LASTEXITCODE -ne 0) { Mal "La ingesta fallo. Si dice 503 o 429 es la cuota de la API: espera unos minutos y vuelve a correr esto." }
Bien "datos del SECOP en tu base"

# ---------------------------------------------------------------- 4 de 5
Paso "4 de 5" "Normalizar y cruzar Contratos con Procesos"

Write-Host "   No sale a la red: lee lo que acabas de ingerir." -ForegroundColor DarkGray
Write-Host ""
& $pyExe @pyArgs -m vigia.normalizado --dsn $DSN_VIGIA
if ($LASTEXITCODE -ne 0) { Mal "La normalizacion fallo." }
Bien "capa normalizada al dia"
Aviso "Si casi todo sale huerfano, es lo esperado: todavia no hemos ingerido el dataset 'procesos'."

# ---------------------------------------------------------------- 5 de 5
Paso "5 de 5" "Lo que quedo guardado"

if ($PSQL) {
    foreach ($consulta in @(
        "SELECT dataset, count(*) AS filas_crudas FROM crudo_registro GROUP BY dataset;",
        "SELECT count(*) AS contratos_normalizados, count(id_del_proceso) AS enlazados, count(*) FILTER (WHERE proceso_de_compra IS NULL) AS sin_llave FROM contrato;",
        "SELECT count(*) AS procesos_normalizados FROM proceso;",
        "SELECT estado, desde, hasta, vistos, insertados, duplicados FROM ciclo ORDER BY id DESC LIMIT 3;"
    )) {
        Visible $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d","vigia","-q","-v","ON_ERROR_STOP=1","-c",$consulta) | Out-Null
    }
} else {
    Aviso "sin psql no puedo ensenarte las tablas, pero los numeros del paso 4 son los mismos"
}

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "== TERMINADO ==" -ForegroundColor Green
Write-Host ""
Write-Host "Lo siguiente es ingerir el dataset 'procesos', que es la otra mitad del cruce:" -ForegroundColor White
Write-Host "   python -m vigia --dataset procesos --desde 2026-08-01 --hasta $hasta"
Write-Host ""
Write-Host "Todo lo anterior quedo escrito en: $REGISTRO" -ForegroundColor DarkGray
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
