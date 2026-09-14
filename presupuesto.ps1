# ¿Se puede medir «adjudicación pegada al presupuesto»? SOLO LECTURA.
#
# Antes de escribir la Regla 4.2 hay que saber si el campo del presupuesto
# llega y con que cobertura. Si llega en un cuarto de los casos —como paso con
# `proveedores_invitados`— la historia se para aqui y se dice, en vez de
# construir una Regla sobre un cuarto del pais y presentarla como si midiera
# el pais.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "presupuesto-ultima-corrida.txt") -Force | Out-Null } catch { }

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
Write-Host "Midiendo la razon adjudicado/presupuesto (unos minutos)..." -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -f "medir-presupuesto.sql" 2>&1 | Out-Host

# La segunda pregunta solo tiene sentido despues de la primera: si el 62 % de
# los procesos adjudica pegado al presupuesto, hay que saber si el presupuesto
# es un presupuesto o es el resultado escrito antes de tiempo.
Write-Host ""
# Comillas simples: en una cadena doble de PowerShell el acento grave es el
# caracter de escape, asi que los backticks alrededor del nombre del campo se
# comerian las letras de al lado.
Write-Host 'Comprobando si precio_base se reescribe despues de adjudicar...' -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -f "medir-precio-base.sql" 2>&1 | Out-Host

# La tercera: los que adjudican POR ENCIMA de su presupuesto. Son el 1,1 %, y
# el criterio es categorico —se pasa o no se pasa—, sin umbral que inventar.
Write-Host ""
Write-Host 'Aislando los que adjudican por encima de su presupuesto...' -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -f "medir-sobrecosto.sql" 2>&1 | Out-Host
Write-Host ""
Write-Host "Listo. Todo quedo en presupuesto-ultima-corrida.txt" -ForegroundColor Green
try { Stop-Transcript | Out-Null } catch { }
