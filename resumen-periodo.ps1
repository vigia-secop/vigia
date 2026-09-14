# Resumen de un periodo contra el anterior. Lo corre el Programador de tareas.
#
#   .\resumen-periodo.ps1 -Desde 2026-08-31 -Hasta 2026-09-06 -Titulo "Resumen semanal"
#
# Si no se le dan fechas, toma la SEMANA PASADA completa (lunes a domingo).

param(
    [string]$Desde = "",
    [string]$Hasta = "",
    [string]$Titulo = "Resumen semanal",
    [string]$Salida = "",
    [switch]$Mensual
)

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

# La mensual se dispara semanal (PowerShell 5.1 no trae un disparador «dia 1»),
# asi que aqui se decide: solo actua en el primer lunes del mes. Sin esto,
# reescribiria el resumen del mes pasado cuatro veces.
if ($Mensual -and -not $Desde -and (Get-Date).Day -gt 7) {
    Write-Host "No es el primer lunes del mes: no hay resumen mensual que sacar." -ForegroundColor DarkGray
    exit 0
}

if (-not $Desde -or -not $Hasta) {
    $hoy = Get-Date
    if ($Mensual) {
        # El mes pasado, completo.
        $primeroDeEste = Get-Date -Year $hoy.Year -Month $hoy.Month -Day 1
        $fin = $primeroDeEste.AddDays(-1)
        $ini = Get-Date -Year $fin.Year -Month $fin.Month -Day 1
    } else {
        # La semana pasada, de lunes a domingo. `DayOfWeek` cuenta el domingo
        # como 0, asi que se corrige para que la semana empiece en lunes.
        $diasDesdeLunes = ([int]$hoy.DayOfWeek + 6) % 7
        $lunesDeEsta = $hoy.Date.AddDays(-$diasDesdeLunes)
        $ini = $lunesDeEsta.AddDays(-7)
        $fin = $lunesDeEsta.AddDays(-1)
    }
    $Desde = $ini.ToString("yyyy-MM-dd")
    $Hasta = $fin.ToString("yyyy-MM-dd")
}
if (-not $Salida) {
    $Salida = if ($Mensual) { "resumen-mensual-$Desde.html" } else { "resumen-semanal-$Desde.html" }
}

$bitacora = Join-Path $raiz "bitacora"
if (-not (Test-Path $bitacora)) { New-Item -ItemType Directory -Path $bitacora -Force | Out-Null }
try { Start-Transcript -Path (Join-Path $bitacora "resumen-$Desde.txt") -Force | Out-Null } catch { }

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
$pyExe = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $v = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($v -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; break
    }
}
$PSQL = Buscar "psql"
if (-not $PSQL -or -not $pyExe) { Write-Host "Faltan psql o Python." -ForegroundColor Red; exit 1 }
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

Write-Host "$Titulo : $Desde a $Hasta" -ForegroundColor White
$json = "resumen-$Desde.json"
& $PSQL -h localhost -U vigia -d vigia -tA -v desde="'$Desde'" -v hasta="'$Hasta'" -f "resumen.sql" -o $json 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "FALLO la consulta." -ForegroundColor Red; exit 1 }

& $pyExe @pyArgs -m vigia.resumen --json $json --salida $Salida --titulo $Titulo 2>&1 | Out-Host
Write-Host "Listo: $Salida" -ForegroundColor Green
try { Stop-Transcript | Out-Null } catch { }
