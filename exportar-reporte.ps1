# Exporta a reporte.json todo lo que el reporte visual necesita.
#
#   Doble clic en EJECUTAR-exportar-reporte.bat
#
# SOLO LECTURA: corre reporte.sql, que no modifica nada. Tarda unos segundos.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "reporte-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

trap {
    Write-Host ""
    Write-Host "   ERROR NO PREVISTO:" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
    Write-Host "   linea $($_.InvocationInfo.ScriptLineNumber)" -ForegroundColor DarkGray
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

function Buscar-Herramienta($nombre) {
    $enPath = Get-Command $nombre -ErrorAction SilentlyContinue
    if ($enPath) { return $enPath.Source }
    foreach ($raizPg in @("C:\Program Files\PostgreSQL", "C:\Program Files (x86)\PostgreSQL")) {
        if (-not (Test-Path $raizPg)) { continue }
        $versiones = Get-ChildItem $raizPg -Directory -ErrorAction SilentlyContinue |
            Sort-Object { if ($_.Name -match '^(\d+)') { [int]$Matches[1] } else { 0 } } -Descending
        foreach ($v in $versiones) {
            $ruta = Join-Path $v.FullName "bin\$nombre.exe"
            if (Test-Path $ruta) { return $ruta }
        }
    }
    return $null
}

$PSQL = Buscar-Herramienta "psql"
if (-not $PSQL) {
    Write-Host "No encuentro psql." -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "Enter para cerrar"; exit 1
}

$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"
Write-Host "Vigia SECOP - exportando el reporte (solo lectura)" -ForegroundColor White
Write-Host "   son consultas de agregacion sobre 25 mil contratos y 340 mil procesos;" -ForegroundColor DarkGray
Write-Host "   puede tardar un minuto." -ForegroundColor DarkGray

# Cada consulta responde una pregunta distinta y va a su propio archivo. Si una
# falla, las demas siguen: un reporte incompleto es util, uno que no existe no.
$consultas = @(
    @{ sql = "reporte.sql"; json = "reporte.json"; que = "la forma de la base" },
    @{ sql = "regimen.sql"; json = "regimen.json"; que = "el corte del 7 de agosto" },
    @{ sql = "plazos.sql";  json = "plazos.json";  que = "plazo proceso -> contrato" },
    @{ sql = "llave-rapido.sql"; json = "llave.json"; que = "que hay que cambiar en la llave del crudo" }
)

$fallos = 0
foreach ($c in $consultas) {
    $rutaSql = Join-Path $raiz $c.sql
    if (-not (Test-Path $rutaSql)) {
        Write-Host "   --  falta $($c.sql), la salto" -ForegroundColor Yellow
        continue
    }
    $rutaJson = Join-Path $raiz $c.json
    Write-Host ""
    Write-Host "   $($c.sql) -- $($c.que)" -ForegroundColor Cyan
    & $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d","vigia","-tA","-v","ON_ERROR_STOP=1","-f",$rutaSql,"-o",$rutaJson) | Out-Host
    if ($LASTEXITCODE -eq 0 -and (Test-Path $rutaJson) -and (Get-Item $rutaJson).Length -gt 2) {
        Write-Host "   OK  $($c.json) ($((Get-Item $rutaJson).Length) bytes)" -ForegroundColor Green
    } else {
        Write-Host "   FALLO en $($c.sql)" -ForegroundColor Red
        $fallos++
    }
}

Write-Host ""
if ($fallos -eq 0) {
    Write-Host "   Las $($consultas.Count) consultas pasaron. Ya lo puedo leer desde aqui." -ForegroundColor Green
} else {
    Write-Host "   $fallos de $($consultas.Count) fallaron; lo demas sirve igual." -ForegroundColor Yellow
}

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
