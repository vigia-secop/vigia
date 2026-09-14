# ¿Que trae de verdad la fuente? Censo de cobertura campo por campo.
# SOLO LECTURA.
#
# El 2026-09-11 afirme que cuatro de las seis banderas que faltan no se podian
# medir porque SECOP no publicaba los datos. Las cuatro estaban equivocadas: el
# esquema que este proyecto captura y versiona trae `nombre_ordenador_del_gasto`,
# `dias_adicionados`, `valor_pagado` y `nombre_representante_legal`. Lo dije de
# memoria en vez de abrir el archivo que teniamos delante.
#
# Pero que el campo exista no es que sirva —`proveedores_invitados` existe y
# llega en el 25,7 %— asi que esto no pregunta si esta, sino EN QUE PORCENTAJE
# llega con algo utilizable. Esa es la pregunta que decide si una historia se
# puede escribir.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "campos-ultima-corrida.txt") -Force | Out-Null } catch { }

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
Write-Host 'Censando que campos llegan poblados y cuales no...' -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -f "medir-campos.sql" 2>&1 | Out-Host
Write-Host ""
Write-Host "Listo. Todo quedo en campos-ultima-corrida.txt" -ForegroundColor Green
try { Stop-Transcript | Out-Null } catch { }
