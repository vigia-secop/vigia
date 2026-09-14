# ¿Se puede medir concentracion por proveedor? SOLO LECTURA.
#
# Tres banderas murieron el 2026-09-06 por describir la mayoria. Aqui el fondo
# se cuenta PRIMERO, porque en concentracion la trampa es evidente: una entidad
# con dos contratos tiene concentracion altisima por tener dos contratos, no
# porque pase nada. Sin separar eso, el ranking de «entidades mas concentradas»
# es un ranking de entidades pequenas disfrazado de hallazgo.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "concentracion-ultima-corrida.txt") -Force | Out-Null } catch { }

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
Write-Host 'Contando el fondo antes de mirar la concentracion...' -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -f "medir-concentracion.sql" 2>&1 | Out-Host
Write-Host ""
Write-Host "Listo. Todo quedo en concentracion-ultima-corrida.txt" -ForegroundColor Green
try { Stop-Transcript | Out-Null } catch { }
