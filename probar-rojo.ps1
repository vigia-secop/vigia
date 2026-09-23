# CUAL DE LAS FORMAS DE IMPRIMIR *NO* PINTA DE ROJO LO QUE NO ES UN ERROR.
#
# EL PROBLEMA. Python escribe su registro por el canal de errores -asi funciona
# `logging`, no es un fallo-, y PowerShell pinta de rojo todo lo que sale por
# ahi y ademas le encaja encima un bloque `NativeCommandError`. El 2026-09-19
# la ingesta llego bien hasta el final y la pantalla parecia un incendio: cada
# linea roja era un `HTTP/1.1 200 OK`.
#
# POR QUE IMPORTA MAS DE LO QUE PARECE. En el portatil se aguanta porque hay
# alguien mirando que ya sabe. En el servidor, el ciclo corre solo a las 5:40
# de la manana y deja un registro que nadie lee entero. Un registro que
# siempre parece roto es un registro que no avisa el dia que se rompe de
# verdad.
#
# POR QUE ESTE SCRIPT EXISTE EN VEZ DE ARREGLARLO DE UNA. El 2026-09-16 ya
# arregle esto mismo para git, lo probe en PowerShell 7 y se lo di por bueno.
# En el 5.1 de Windows -que es el que corre aqui- seguia saliendo rojo. No se
# prueba en la version equivocada dos veces.
#
# La forma que funciono para git fue capturar la salida en una variable. Aqui
# no sirve igual: la ingesta tarda trece minutos y capturar significa pantalla
# en blanco todo ese rato. Lo que hace falta es una forma que imprima EN VIVO
# y no pinte de rojo. Este script prueba cuatro candidatas sobre la misma
# orden y deja ver cual gana.
#
# COMO SE LEE: mira la pantalla. La forma buena imprime la linea de prueba en
# gris o blanco y NO muestra ningun bloque que diga NativeCommandError.

$ErrorActionPreference = "Continue"

$py = $null; $pyArgs = @()
foreach ($c in @(@{ exe = "py"; args = @("-3") }, @{ exe = "python"; args = @() })) {
    if (Get-Command $c.exe -ErrorAction SilentlyContinue) { $py = $c.exe; $pyArgs = $c.args; break }
}
if (-not $py) { Write-Host "  No encontre Python." -ForegroundColor Red; exit 1 }

# Una orden que escribe por el canal de errores y termina BIEN (codigo 0).
# Es exactamente lo que hace la ingesta en cada pagina.
$guion = "import sys; sys.stderr.write('LINEA DE PRUEBA: esto es un HTTP 200, no un error\n'); sys.exit(0)"

Write-Host ""
Write-Host "  QUE FORMA NO PINTA DE ROJO" -ForegroundColor White
Write-Host "  PowerShell $($PSVersionTable.PSVersion)" -ForegroundColor DarkGray
Write-Host "  (esta es la version que importa: el arreglo tiene que servir AQUI)" -ForegroundColor DarkGray

Write-Host ""
Write-Host "== A : como esta hoy  ->  2>&1 | Out-Host" -ForegroundColor Cyan
& $py @pyArgs -c $guion 2>&1 | Out-Host
Write-Host "   [fin de A]" -ForegroundColor DarkGray

Write-Host ""
Write-Host "== B : igual, pero bajando ErrorActionPreference" -ForegroundColor Cyan
$antes = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
try { & $py @pyArgs -c $guion 2>&1 | Out-Host } finally { $ErrorActionPreference = $antes }
Write-Host "   [fin de B]" -ForegroundColor DarkGray

Write-Host ""
Write-Host "== C : pasando cada linea por Write-Host" -ForegroundColor Cyan
& $py @pyArgs -c $guion 2>&1 | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
Write-Host "   [fin de C]" -ForegroundColor DarkGray

Write-Host ""
Write-Host "== D : Write-Host Y ErrorActionPreference bajo" -ForegroundColor Cyan
$antes = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
try {
    & $py @pyArgs -c $guion 2>&1 | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
} finally { $ErrorActionPreference = $antes }
Write-Host "   [fin de D]" -ForegroundColor DarkGray

Write-Host ""
Write-Host "== E : capturando (sirve, pero no imprime en vivo)" -ForegroundColor Cyan
$antes = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
try { $salida = & $py @pyArgs -c $guion 2>&1 } finally { $ErrorActionPreference = $antes }
foreach ($l in @($salida)) { Write-Host "   $l" -ForegroundColor Gray }
Write-Host "   [fin de E]" -ForegroundColor DarkGray

# LAS DOS DE ABAJO SON LA MISMA IDEA QUE C, PERO EMPAQUETADA. Si funcionan,
# el arreglo cabe en una palabra en cada sitio en vez de repetir el bloque
# entero veinte veces. Si no funcionan, se repite el bloque: veinte lineas
# feas que sirven valen mas que una linea elegante que no.
filter Sin-Rojo { Write-Host "   $_" -ForegroundColor Gray }

function Sin-Rojo-Funcion {
    process { Write-Host "   $_" -ForegroundColor Gray }
}

Write-Host ""
Write-Host "== F : con un 'filter' propio" -ForegroundColor Cyan
& $py @pyArgs -c $guion 2>&1 | Sin-Rojo
Write-Host "   [fin de F]" -ForegroundColor DarkGray

Write-Host ""
Write-Host "== G : con una funcion con bloque process" -ForegroundColor Cyan
& $py @pyArgs -c $guion 2>&1 | Sin-Rojo-Funcion
Write-Host "   [fin de G]" -ForegroundColor DarkGray

Write-Host ""
Write-Host "  La forma buena es la primera que imprima la LINEA DE PRUEBA" -ForegroundColor Gray
Write-Host "  en gris y sin ningun bloque de NativeCommandError debajo." -ForegroundColor Gray
Write-Host ""
