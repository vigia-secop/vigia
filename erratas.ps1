# ¿Cuantas de las cifras grandes son erratas de tecleo? SOLO LECTURA.
#
# El 2026-09-11 aparecio en la lista de revision la ALCALDIA DE TIPACOQUE
# —municipio de unos 3.000 habitantes— firmando $431.340.000.000 con una
# fundacion. El proceso del que sale ese contrato tiene un presupuesto de
# $431.340.000: el mismo numero con TRES CEROS DE MAS.
#
# El techo de valores imposibles (1e14) no ataja esto y nunca pudo: 431 mil
# millones es un contrato perfectamente posible. La errata x1000 no se detecta
# por tamano, se detecta por proporcion. Eso es lo que mide esta consulta.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "erratas-ultima-corrida.txt") -Force | Out-Null } catch { }

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
Write-Host 'Contando el fondo antes de llamar errata a nada...' -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -f "medir-erratas.sql" 2>&1 | Out-Host
Write-Host ""
Write-Host "Listo. Todo quedo en erratas-ultima-corrida.txt" -ForegroundColor Green
Write-Host "Lo que caiga en las listas NO es un hallazgo: es un filtro de" -ForegroundColor Yellow
Write-Host "calidad. No se puede usar en ningun ranking por valor hasta" -ForegroundColor Yellow
Write-Host "abrirlo en SECOP y mirarlo uno por uno." -ForegroundColor Yellow
try { Stop-Transcript | Out-Null } catch { }
