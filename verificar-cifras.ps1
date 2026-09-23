# VERIFICAR EL CAMBIO DE FORMATO. Solo lectura: deja verificar-cifras.txt.
# La explicacion esta arriba del .sql.

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

Write-Host ""
Write-Host "  QUE CIFRAS CAMBIARON DE VERDAD" -ForegroundColor White
Write-Host "  Unos minutos." -ForegroundColor DarkGray
& $PSQL -h localhost -U vigia -d vigia -q -f "verificar-cifras.sql" -o "verificar-cifras.txt" 2>&1 | Sin-Rojo
if (Test-Path "verificar-cifras.txt") {
    $b = (Get-Item "verificar-cifras.txt").Length
    Write-Host "  Listo: verificar-cifras.txt ($b bytes)" -ForegroundColor Green
}
Write-Host ""
