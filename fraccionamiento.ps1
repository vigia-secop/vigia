# ¿Se puede medir el fraccionamiento? SOLO LECTURA.
#
# Partir una compra en varios contratos pequenos para no pasar del tope que
# obligaria a competir. La bandera 4.6.
#
# POR QUE ESTA Y NO OTRA. Las tres banderas muertas cayeron porque su umbral
# habia que inventarlo. Esta tiene un tope que existe en el mundo —el de la
# minima cuantia— y que ademas no hace falta que yo lo sepa: el tope de cada
# entidad se lee en su propia conducta, es la minima cuantia mas cara que esa
# entidad firma. Sale de los datos, se recalcula solo cada ano, y es distinto
# para cada entidad, como lo es de verdad.
#
# Y como siempre: primero el fondo. Si contratar dos veces al mismo proveedor
# en un mes es lo normal, la bandera describe el pais y se descarta.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "fraccionamiento-ultima-corrida.txt") -Force | Out-Null } catch { }

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
$PSQL = Buscar "psql"
if (-not $PSQL) { Write-Host "No encuentro psql." -ForegroundColor Red; exit 1 }
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

Write-Host ""
Write-Host 'Contando el fondo antes de mirar el fraccionamiento...' -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -f "medir-fraccionamiento.sql" 2>&1 | Out-Host
Write-Host ""
Write-Host "Listo. Todo quedo en fraccionamiento-ultima-corrida.txt" -ForegroundColor Green
try { Stop-Transcript | Out-Null } catch { }
