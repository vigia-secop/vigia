# CALIBRAR LA BANDERA DE FRACCIONAMIENTO. SOLO LECTURA.
#
# Corre la Regla sobre todas las minimas cuantias ingeridas y deja un informe
# para leer con los ojos.
#
# LO QUE ESTE SCRIPT NO HACE, Y NO ES UN OLVIDO:
#
#   NO publica nada.
#   NO manda nada a ninguna cola.
#   NO activa la Regla.
#
# Calibrar es probar. Activar es un acto aparte, de una persona, con este
# informe delante. La Regla queda en "calibracion" cuando esto termina, y el
# codigo no la deja saltar a "activa" sin que alguien lo decida.
#
# LAS TRES CUENTAS. Encendio / no encendio / NO SE PUDO MIRAR. La tercera es
# la que decide si el resultado vale: una entidad con un techo imposible nunca
# encendera, y eso no quiere decir que este limpia. Va arriba del informe.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz
try { Start-Transcript -Path (Join-Path $raiz "calibracion-ultima-corrida.txt") -Force | Out-Null } catch { }

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
if (-not $PSQL -or -not $pyExe) {
    Write-Host "Faltan psql o Python 3.11+." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

Write-Host ""
Write-Host "== 1 de 2 : Armar los grupos" -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -tA `
    -f "calibrar-fraccionamiento.sql" -o "calibracion-fraccionamiento.json" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "FALLO la consulta." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

Write-Host ""
Write-Host "== 2 de 2 : Correr la Regla en calibracion" -ForegroundColor Cyan
& $pyExe @pyArgs -m vigia.reglas.calibrar_fraccionamiento `
    --json "calibracion-fraccionamiento.json" `
    --salida "calibracion-fraccionamiento.txt" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "La calibracion no se pudo correr." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    exit 1
}

Write-Host ""
Write-Host "  Informe en calibracion-fraccionamiento.txt" -ForegroundColor Green
Write-Host "  LEELO ENTERO antes de decidir nada. Empieza por la cobertura." -ForegroundColor Gray
Write-Host "  La Regla NO quedo activa: eso lo decides tu, no el script." -ForegroundColor Gray
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
