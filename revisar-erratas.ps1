# REVISAR LAS ERRATAS PENDIENTES. Una por una, con su enlace al SECOP.
#
#     .\revisar-erratas.ps1
#
# POR QUE EXISTE. La puerta 3 del semaforo detiene la publicacion cuando
# aparece un contrato cuyo valor es exactamente mil o diez mil veces el
# presupuesto de su propio proceso. Eso es la firma de una tecla de mas, no la
# de un sobrecosto — y publicarlo como hallazgo acabaria con Vigia en un dia.
#
# La puerta NO tiene umbral. No pregunta «¿las erratas mueven mas del X % del
# valor?», porque ese X habria que inventarselo y asi murieron tres banderas de
# este proyecto. Pregunta: ¿alguien la miro?
#
# Este script es el «alguien la miro». Te ensena cada una con su enlace, y lo
# que respondas queda escrito en erratas-revisadas.txt con la fecha.
#
# NO CORRIGE NADA. La capa cruda no se toca y la normalizada guarda lo que la
# fuente publico. Esto es un registro de que una persona lo abrio y lo vio.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$pyExe = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() })) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    $v = & $c.exe @($c.args) --version 2>&1 | Out-String
    if ($v -match "Python (\d+)\.(\d+)" -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11) {
        $pyExe = $c.exe; $pyArgs = $c.args; break
    }
}
if (-not $pyExe) { Write-Host "No hay Python 3.11+" -ForegroundColor Red; exit 1 }

if (-not (Test-Path "revision.json")) {
    Write-Host ""
    Write-Host "  No encuentro revision.json." -ForegroundColor Yellow
    Write-Host "  Corre primero EJECUTAR-DIA.bat." -ForegroundColor Yellow
    exit 1
}

$guion = @'
import json, sys, webbrowser
from pathlib import Path
sys.path.insert(0, ".")
from vigia.puertas import anotar_revisada, leer_revisadas

datos = json.loads(Path("revision.json").read_text(encoding="utf-8"))
filas = datos.get("erratas_x1000") or []
registro = Path("erratas-revisadas.txt")
vistas = leer_revisadas(registro)
faltan = [f for f in filas if f.get("id_contrato") not in vistas]

if not faltan:
    print("\n  No hay erratas pendientes. La puerta 3 esta en verde.\n")
    raise SystemExit(0)

print(f"\n  {len(faltan)} errata(s) sin revisar.\n")
print("  Para cada una: se abre la ficha del SECOP en el navegador.")
print("  Mira el valor del contrato contra el presupuesto del proceso.\n")

for i, f in enumerate(faltan, 1):
    print("  " + "-" * 66)
    print(f"  {i} de {len(faltan)}   {f.get('id_contrato')}")
    print(f"  Entidad     : {f.get('entidad')}")
    print(f"  Proveedor   : {f.get('proveedor') or '—'}")
    print(f"  Valor       : {f.get('valor'):,}".replace(",", "."))
    print(f"  El proceso  : {f.get('valor_probable'):,}".replace(",", "."))
    print(f"  Ceros de mas: {f.get('ceros_de_mas')}")
    if f.get("enlace"):
        print(f"  SECOP       : {f['enlace']}")
    print()
    r = input("  [e] es errata   [r] es real   [s] saltar por ahora : ").strip().lower()
    if r == "e":
        anotar_revisada(registro, f["id_contrato"],
                        "revisado: errata de tecleo, x10^n contra precio_base")
        print("  anotada como errata.\n")
    elif r == "r":
        # Que se pueda decir «es real» importa: si algun dia un contrato de
        # verdad cuesta mil veces su presupuesto, la puerta no puede obligar a
        # llamarlo errata para poder publicar.
        anotar_revisada(registro, f["id_contrato"],
                        "revisado: parece REAL, no errata; mirar con calma")
        print("  anotada como real. Conviene mirarla con calma aparte.\n")
    else:
        print("  saltada: la puerta 3 seguira deteniendo por esta.\n")

print("  Listo. Vuelve a correr EJECUTAR-PUBLICAR.bat.\n")
'@

$guion | & $pyExe @pyArgs -
