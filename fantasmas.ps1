# ¿Cuántas identidades de proveedor son fantasmas? SOLO LECTURA.
#
# Un fantasma es una fila de `proveedor` que ningún contrato apunta hoy. La
# tabla se escribe con `ON CONFLICT DO UPDATE` y nunca se borra nada, asi que
# cuando una regla de identidad cambia —como el 2026-09-05, cuando `000000000`
# dejo de ser un documento— la fila vieja se queda, con sus contadores
# congelados, y las paginas que leen `proveedor` la siguen mostrando.
#
# Esto no arregla nada. Cuenta, para decidir con el numero delante.

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

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

Write-Host ""
Write-Host "Contando identidades de proveedor que ya no apunta ningun contrato..." -ForegroundColor Cyan
& $PSQL -h localhost -U vigia -d vigia -tA -f "fantasmas.sql" -o "fantasmas.json" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "FALLO la consulta." -ForegroundColor Red; exit 1 }

$lector = @'
import json, sys
d = json.load(open("fantasmas.json", encoding="utf-8"))

def n(v):
    return "-" if v is None else f"{int(v):,}".replace(",", ".")

f = d["fantasmas"]
print()
print("FANTASMAS  identidades sin un solo contrato que las apunte hoy")
print(f"  {n(f['cuantos'])} filas, que entre todas dicen tener "
      f"{n(f['contratos_que_dicen_tener'])} contratos")

c = d["contadores"]
print()
print("CONTADORES  el `contratos` guardado contra el real")
print(f"  {n(c['identidades_vivas'])} identidades vivas")
print(f"  {n(c['descuadradas'])} descuadradas  "
      f"({n(c['guardado_de_mas'])} de mas, {n(c['guardado_de_menos'])} de menos)")

for titulo, clave, cols in [
    ("LOS MAYORES FANTASMAS", "fantasmas_mayores",
     ["tipo", "numero", "nombre_principal", "contratos", "variantes"]),
    ("DOCUMENTOS DE UN SOLO CARACTER  (`000000000` y companeros)",
     "documentos_de_un_solo_caracter",
     ["tipo", "numero", "nombre_principal", "contratos_guardados",
      "contratos_reales", "variantes"]),
]:
    filas = d.get(clave) or []
    print()
    print(titulo)
    if not filas:
        print("  ninguno.")
        continue
    for r in filas:
        print("  " + " | ".join(str(r.get(k)) for k in cols))
print()
'@
$lector | & $pyExe @pyArgs -
