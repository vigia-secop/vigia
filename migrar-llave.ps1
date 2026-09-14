# Migracion 005: la capa cruda pasa a llave de negocio.
#
#   Doble clic en EJECUTAR-migrar-llave.bat
#
# ESTE GUION NO TOCA `crudo_registro`. Aplica la migracion 005 -que solo CREA
# una tabla nueva y vacia- y la rellena desde la vieja, contando cuantas filas
# resultan ser la misma. Al terminar, `crudo_registro` sigue siendo exactamente
# la de antes.
#
# El intercambio -poner la tabla nueva en su sitio- es una decision aparte y
# hay que pedirla a proposito. La tabla anterior tampoco se borra entonces:
# queda como `crudo_registro_antes_de_005`.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$REGISTRO = Join-Path $raiz "migracion-ultima-corrida.txt"
try { Start-Transcript -Path $REGISTRO -Force | Out-Null } catch { }

trap {
    Write-Host ""
    Write-Host "   ERROR NO PREVISTO:" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Red
    Write-Host "   linea $($_.InvocationInfo.ScriptLineNumber)" -ForegroundColor DarkGray
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"
    exit 1
}

$DSN = "postgresql://vigia:vigia@localhost:5432/vigia"

function Bien($m) { Write-Host "   OK  $m" -ForegroundColor Green }
function Aviso($m) { Write-Host "   --  $m" -ForegroundColor Yellow }
function Mal($m) {
    Write-Host ""; Write-Host "   FALLO: $m" -ForegroundColor Red
    Write-Host "   Quedo escrito en: $REGISTRO" -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host "   Enter para cerrar"; exit 1
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

Write-Host "Vigia SECOP - migracion 005, llave de negocio" -ForegroundColor White
Write-Host "Esto NO toca crudo_registro. Solo llena una tabla nueva y cuenta." -ForegroundColor Yellow
Write-Host ""

$pyExe = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() }, @{ exe = "python3"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $v = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($v -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; Bien $v.Trim(); break
    }
}
if (-not $pyExe) { Mal "No encuentro Python 3.11 o superior." }

$PSQL = Buscar-Herramienta "psql"
if (-not $PSQL) { Mal "No encuentro psql." }
$env:PGPASSWORD = "vigia"
$env:PGOPTIONS = "-c client_min_messages=warning"

Write-Host ""
Write-Host "== 1 de 3 : Aplicar la migracion 005" -ForegroundColor Cyan
& $PSQL @("-w","-h","localhost","-p","5432","-U","vigia","-d","vigia","-q","-v","ON_ERROR_STOP=1","-f",(Join-Path $raiz "migraciones\005_llave_de_negocio.sql")) | Out-Host
if ($LASTEXITCODE -ne 0) { Mal "La migracion 005 fallo." }
Bien "tabla de destino creada (vacia)"

Write-Host ""
Write-Host "== 2 de 3 : Instalar el paquete actualizado" -ForegroundColor Cyan
& $pyExe @pyArgs -m pip install --quiet -e "." 2>&1 | Out-Host
Bien "paquete al dia"

Write-Host ""
Write-Host "== 3 de 3 : Trasladar (sin intercambiar)" -ForegroundColor Cyan
Write-Host "   son 407 mil filas; puede tardar varios minutos. No cierres la ventana." -ForegroundColor DarkGray
Write-Host ""
& $pyExe @pyArgs -m vigia.crudo.rellave --dsn $DSN
if ($LASTEXITCODE -ne 0) { Mal "El traslado fallo." }

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "== TERMINADO ==" -ForegroundColor Green
Write-Host "crudo_registro sigue intacta. Manda los numeros de arriba y decidimos." -ForegroundColor White
Write-Host "Quedo escrito en: $REGISTRO" -ForegroundColor DarkGray
try { Stop-Transcript | Out-Null } catch { }
Read-Host "Enter para cerrar"
