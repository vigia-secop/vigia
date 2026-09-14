# ¿Hay nominas paralelas? Una misma persona con varios contratos A LA VEZ.
# SOLO LECTURA.
#
# Yo argumente que las cedulas aportaban poco: dos NIT movian el 99,7 % del
# dinero y veintiuna cedulas el 0,3 %. El argumento era correcto y estaba
# mirando la variable equivocada. En una nomina paralela el valor de cada
# contrato es pequeno a proposito; lo que no es pequeno es el patron.
#
# Tener dos contratos a la vez NO es ilegal ni irregular. Esta medicion cuenta
# traslapes; no concluye nada sobre incompatibilidades, porque la dedicacion
# pactada no la publica SECOP.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "nominas-paralelas-ultima-corrida.txt") -Force | Out-Null } catch { }

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
Write-Host 'Contando cuantas personas tienen contratos traslapados...' -ForegroundColor Cyan
Write-Host 'Puede tardar: cruza cada contrato de persona contra los suyos.' -ForegroundColor DarkGray
& $PSQL -h localhost -U vigia -d vigia -f "medir-nominas-paralelas.sql" 2>&1 | Out-Host
Write-Host ""
Write-Host "Listo. Todo quedo en nominas-paralelas-ultima-corrida.txt" -ForegroundColor Green
Write-Host "Los documentos salen enmascarados a proposito: tres digitos" -ForegroundColor Yellow
Write-Host "bastan para distinguir filas, y el enlace al SECOP lleva a la" -ForegroundColor Yellow
Write-Host "ficha oficial, que es donde ese dato se puede defender." -ForegroundColor Yellow
try { Stop-Transcript | Out-Null } catch { }
