# EL BOLETIN: el hilo listo para publicar, de la semana pasada o del mes pasado.
#
#     .\boletin.ps1                 # la semana pasada
#     .\boletin.ps1 -Mensual        # el mes pasado
#
# Escribe un .txt con los posts numerados y el conteo de caracteres de cada
# uno. NO publica nada: publicar lo hace una persona, a mano, despues de leerlo.
# Esa frontera es a proposito y no es pereza — ver `vigia/publicacion.py`.
#
# Si algo del hilo no se puede publicar —un documento de identidad, una palabra
# que impute, un post que se pasa de 280— el generador LEVANTA y no escribe
# nada. No hay modo «sacalo igual».

param([switch]$Mensual, [string]$Desde = "", [string]$Hasta = "", [string]$Enlace = "")

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

if (-not $Desde -or -not $Hasta) {
    $hoy = (Get-Date).Date
    if ($Mensual) {
        $primeroDeEste = Get-Date -Year $hoy.Year -Month $hoy.Month -Day 1
        $fin = $primeroDeEste.AddDays(-1)
        $ini = Get-Date -Year $fin.Year -Month $fin.Month -Day 1
    } else {
        # DayOfWeek cuenta el domingo como 0; aqui la semana empieza en lunes.
        $diasDesdeLunes = ([int]$hoy.DayOfWeek + 6) % 7
        $lunes = $hoy.AddDays(-$diasDesdeLunes)
        $ini = $lunes.AddDays(-7); $fin = $lunes.AddDays(-1)
    }
    $Desde = $ini.ToString("yyyy-MM-dd"); $Hasta = $fin.ToString("yyyy-MM-dd")
}
$periodo = if ($Mensual) { "mes" } else { "semana" }
$salida = "boletin-$periodo-$Desde.txt"

function Buscar($n) {
    $p = Get-Command $n -ErrorAction SilentlyContinue
    if ($p) { return $p.Source }
    foreach ($r in @("C:\Program Files\PostgreSQL","C:\Program Files (x86)\PostgreSQL")) {
        if (-not (Test-Path $r)) { continue }
        foreach ($v in (Get-ChildItem $r -Directory -EA SilentlyContinue |
            Sort-Object { if ($_.Name -match '^(\d+)') { [int]$Matches[1] } else { 0 } } -Descending)) {
            $ruta = Join-Path $v.FullName "bin\$n.exe"
            if (Test-Path $ruta) { return $ruta }
        }
    }
    return $null
}
$pyExe = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $v = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($v -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; break
    }
}
$PSQL = Buscar "psql"
if (-not $PSQL -or -not $pyExe) { Write-Host "Faltan psql o Python." -ForegroundColor Red; exit 1 }
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

Write-Host ""
Write-Host "Boletin $periodo : $Desde a $Hasta" -ForegroundColor White
$json = "boletin-$Desde.json"
& $PSQL -h localhost -U vigia -d vigia -tA -v desde="'$Desde'" -v hasta="'$Hasta'" `
    -f "boletin.sql" -o $json 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "FALLO la consulta." -ForegroundColor Red; exit 1 }

& $pyExe @pyArgs -m vigia.boletin --json $json --salida $salida --periodo $periodo --enlace $Enlace 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  EL BOLETIN NO SE ESCRIBIO. Arriba dice por que." -ForegroundColor Yellow
    Write-Host "  Eso es la barrera haciendo su trabajo, no un error." -ForegroundColor Yellow
    exit 1
}
Write-Host ""
Write-Host "  Listo: $salida" -ForegroundColor Green
Write-Host "  LEELO ANTES DE PUBLICAR. Vigia no publica solo, y no va a hacerlo." -ForegroundColor Gray
Write-Host ""
if (Test-Path (Join-Path $raiz $salida)) { Start-Process notepad.exe (Join-Path $raiz $salida) }
