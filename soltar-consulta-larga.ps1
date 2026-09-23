# MATAR UNA CONSULTA QUE YA NO LE SIRVE A NADIE.
#
# POR QUE HACE FALTA. Cerrar la ventana mata a `psql`, pero no mata la
# consulta: PostgreSQL sigue trabajando en ella hasta terminarla, porque un
# SELECT largo no se entera de que el cliente se fue hasta que intenta
# devolverle algo. Queda una consulta huerfana comiendose el disco y la
# memoria para un resultado que nadie va a leer.
#
# EN QUE SE DIFERENCIA DE `desatascar.ps1`. Aquel solo mata a quien esta
# frenando a otro, y no mata nada si nadie esta bloqueado. Este es mas
# bruto a proposito: mata por TIEMPO. Por eso es un script aparte y por eso
# el umbral es alto.
#
# EL UMBRAL ES 20 MINUTOS, y no es un numero al azar: la consulta mas pesada
# del sitio -la lista de revision- se armaba en 3 minutos el 2026-09-16 y en
# 17 el 2026-09-20. Veinte minutos ya no es "va lenta": es que quedo suelta.
#
# NO mata la ingesta ni la normalizacion: esas escriben desde Python por otra
# conexion y no duran tanto en una sola sentencia. Aun asi, no lo corras
# mientras el ciclo diario este trabajando.

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

$PSQL = Buscar "psql"
if (-not $PSQL) {
    Write-Host "  No encontre psql." -ForegroundColor Red
    exit 1
}
$env:PGPASSWORD = "vigia"

function Consultar($sql) {
    & $PSQL -h localhost -U vigia -d vigia -c $sql 2>&1 | Out-Host
}

Write-Host ""
Write-Host "  SOLTAR LA CONSULTA LARGA" -ForegroundColor White
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray

Write-Host ""
Write-Host "== 1 de 2 : Lo que se va a matar (y lo que no)" -ForegroundColor Cyan
Consultar @"
SELECT pid,
       date_trunc('second', now() - query_start)        AS lleva,
       CASE WHEN query_start < now() - interval '20 minutes'
            THEN 'SE MATA' ELSE 'se deja' END           AS destino,
       left(regexp_replace(query, '\s+', ' ', 'g'), 45) AS consulta
  FROM pg_stat_activity
 WHERE datname = 'vigia' AND pid <> pg_backend_pid() AND state = 'active'
 ORDER BY query_start;
"@

Write-Host ""
Write-Host "== 2 de 2 : Soltar" -ForegroundColor Cyan
Consultar @"
SELECT pid,
       date_trunc('second', now() - query_start) AS llevaba,
       pg_terminate_backend(pid)                 AS soltado
  FROM pg_stat_activity
 WHERE datname = 'vigia' AND pid <> pg_backend_pid() AND state = 'active'
   AND query_start < now() - interval '20 minutes';
"@

Write-Host ""
Write-Host "  Si salio vacio, no habia ninguna consulta de mas de 20 minutos" -ForegroundColor Gray
Write-Host "  y la base ya estaba libre." -ForegroundColor Gray
Write-Host ""
