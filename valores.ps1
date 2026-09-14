# ¿Hay valores imposibles en los contratos? SOLO LECTURA.
#
# Buscando la bandera 4.2 aparecieron erratas de la fuente: un mismo numero con
# tres ceros de mas, y un proceso de ocho mil billones de pesos. Si eso tambien
# esta en la capa de contratos, entonces TODO lo que publica el Panel —el total
# de la ventana, el ranking de contratistas, el mayor contrato— puede estar mal
# por una sola errata, y sin fallar: el numero sale, se lee, y esta mal.
#
# Esto no arregla nada. Mide el tamano del problema.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "valores-ultima-corrida.txt") -Force | Out-Null } catch { }

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
Write-Host 'Buscando valores imposibles en la capa de contratos...' -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -f "medir-valores-imposibles.sql" 2>&1 | Out-Host
Write-Host ""
Write-Host "Listo. Todo quedo en valores-ultima-corrida.txt" -ForegroundColor Green
try { Stop-Transcript | Out-Null } catch { }
