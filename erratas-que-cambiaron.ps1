# QUE PASO CON LA CUARTA ERRATA.
#
# Corre `erratas-que-cambiaron.sql` y deja el resultado en un archivo. Solo
# lectura: no escribe nada en la base.
#
# La explicacion de por que esta pregunta se puede responder -y de por que
# importa que se pueda- esta arriba del .sql.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

function Buscar($n) {
    $p = Get-Command $n -ErrorAction SilentlyContinue
    if ($p) { return $p.Source }
    foreach ($r in @("C:\Program Files\PostgreSQL", "C:\Program Files (x86)\PostgreSQL")) {
        if (-not (Test-Path $r)) { continue }
        foreach ($v in (Get-ChildItem $r -Directory -EA SilentlyContinue |
            Sort-Object { if ($_.Name -match '^(\d+)') { [int]$Matches[1] } else { 0 } } -Descending)) {
            $ruta = Join-Path $v.FullName "bin\$n.exe"
            if (Test-Path $ruta) { return $ruta }
        }
    }
    return $null
}

filter Sin-Rojo { Write-Host "$_" }

$PSQL = Buscar "psql"
if (-not $PSQL) { Write-Host "  No encontre psql." -ForegroundColor Red; exit 1 }
$env:PGPASSWORD = "vigia"
$env:PGCLIENTENCODING = "UTF8"

$salida = Join-Path $raiz "erratas-que-cambiaron.txt"

Write-Host ""
Write-Host "  ERRATAS QUE CAMBIARON DESDE QUE LAS VIMOS" -ForegroundColor White
Write-Host "  Recorre todas las instantaneas guardadas. Tarda un rato." -ForegroundColor DarkGray
Write-Host ""

& $PSQL -h localhost -U vigia -d vigia -f "erratas-que-cambiaron.sql" -o $salida 2>&1 | Sin-Rojo

if (Test-Path $salida) {
    Get-Content -LiteralPath $salida | Sin-Rojo
    Write-Host ""
    Write-Host "  Queda escrito en erratas-que-cambiaron.txt" -ForegroundColor Green
} else {
    Write-Host "  No se escribio el archivo." -ForegroundColor Yellow
}
Write-Host ""
