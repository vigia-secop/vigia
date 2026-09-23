# CUANTOS DIAS TARDA EL SECOP EN PUBLICAR UN CONTRATO.
#
# Corre `medir-retraso.sql` y deja el resultado en `medicion-retraso.txt`.
# Solo lectura. La explicacion de que se mide y por que esta arriba del .sql.
#
# Sirve para decidir la ventana de solapamiento con un numero de la fuente,
# no con uno sacado de la cabeza. El 45 salio de la cabeza y quedo corto.

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

$salida = Join-Path $raiz "medicion-retraso.txt"

Write-Host ""
Write-Host "  CUANTOS DIAS TARDA EL SECOP EN PUBLICAR UN CONTRATO" -ForegroundColor White
Write-Host "  Recorre las instantaneas de contratos. Unos minutos." -ForegroundColor DarkGray

& $PSQL -h localhost -U vigia -d vigia -f "medir-retraso.sql" -o $salida 2>&1 | Sin-Rojo

if (Test-Path $salida) {
    Get-Content -LiteralPath $salida | Sin-Rojo
    Write-Host ""
    Write-Host "  Queda escrito en medicion-retraso.txt" -ForegroundColor Green
}
Write-Host ""
