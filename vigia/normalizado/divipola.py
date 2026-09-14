"""Códigos DIVIPOLA de municipio (historia 1.9).

La 1.6 dejó el municipio con nombre y sin código, y dijo por qué: «Argelia»
son tres municipios distintos —Antioquia, Cauca y Valle del Cauca—, con
conteos casi iguales, así que fundirlos por el nombre no se vería raro en
ningún reporte.

LO QUE SE MIDIÓ (dataset oficial del DANE `gdxc-w37w`, 2026-09-05):

| Medición | Resultado |
|---|---|
| Municipios | **1 122** |
| Códigos distintos | 1 122 |
| **Nombres distintos** | **1 037** |

**66 nombres los comparte más de un municipio, y entre todos abarcan 151 de
los 1 122.** Los más repetidos van de a cuatro: «LA UNIÓN», «VILLANUEVA» y
«BUENAVISTA» son cuatro municipios cada uno; «ARGELIA» y «GRANADA», tres.

CUIDADO CON EL 85. La diferencia 1 122 − 1 037 = 85 **no** es el número de
nombres compartidos: es cuántas filas sobran respecto a los nombres, que no es
lo mismo. Un nombre que aparece cuatro veces aporta 3 a esa resta y 1 al conteo
de nombres compartidos. Yo escribí «85 nombres» antes de tener la tabla, y la
prueba contra la tabla real lo tumbó.

**Al normalizar son 67, no 66.** `CHIMÁ` (Córdoba, 23168) y `CHIMA`
(Santander, 68176) son dos municipios reales que se distinguen SOLO por la
tilde; quitarla los junta. Están en departamentos distintos, así que el par
los separa igual — pero es la prueba más limpia de que el nombre por sí solo,
normalizado o no, no identifica a un municipio.

POR QUÉ LA TABLA SE CAPTURA Y NO SE CONSULTA. Misma decisión que la tabla de
esquemas esperados de la 1.3 y la de departamentos de la 1.6: una tabla que
cambia bajo los pies vuelve incomparable cualquier serie histórica. La
división político-administrativa cambia —municipios nuevos, nombres que se
corrigen: la propia fuente trae hoy «GÜICÁN DE LA SIERRA» y «SANTA CRUZ DE
MOMPOX», que no se llamaban así hace unos años—. Se captura con
`capturar-divipola.ps1`, queda en `datos/divipola_municipios.csv`, y cuando
cambie se ve en el diff.

POR QUÉ NO SE INCRUSTA EN EL CÓDIGO. 1 122 filas escritas a mano son 1 122
oportunidades de equivocarse en una, y nadie revisaría el diff entero. El
archivo se baja de la fuente, se comprueba y se versiona.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from vigia.normalizado.proveedor import normalizar_texto
from vigia.normalizado.territorio import DEPARTAMENTOS_DIVIPOLA

#: Dónde vive la tabla capturada, relativo a la raíz del repositorio.
RUTA_TABLA = Path("datos") / "divipola_municipios.csv"

#: Cuántos municipios trae la fuente. Medido el 2026-09-05.
#:
#: No es decoración: si el archivo capturado trae muchos menos, la captura se
#: truncó y hay que enterarse al cargar, no al ver un reporte con huecos.
MUNICIPIOS_ESPERADOS = 1122

#: Margen que se tolera sin protestar. La división político-administrativa se
#: mueve de a pocos municipios por año; una diferencia grande es una captura
#: rota, no un cambio del país.
MARGEN_RAZONABLE = 30


class TablaDeMunicipiosNoDisponible(RuntimeError):
    """No hay tabla capturada, o la que hay no es utilizable.

    Se levanta a propósito en vez de devolver «sin código» en silencio: un
    municipio sin código porque la tabla no está no es lo mismo que un
    municipio que la fuente no supo decir, y confundirlos esconde una avería.
    """


@dataclass(frozen=True)
class Municipio:
    """Un municipio de la tabla oficial."""

    codigo: str
    nombre: str

    @property
    def codigo_departamento(self) -> str:
        return self.codigo[:2]


class TablaDeMunicipios:
    """La tabla cargada, indexada por (departamento, nombre normalizado).

    La llave es el PAR. Nunca el nombre solo: 85 nombres los comparte más de
    un municipio.
    """

    def __init__(self, municipios: list[Municipio]) -> None:
        self._municipios = municipios
        self._por_par: dict[tuple[str, str], str] = {}
        self._colisiones: list[tuple[str, str]] = []
        for municipio in municipios:
            nombre = normalizar_texto(municipio.nombre)
            if nombre is None:
                continue
            llave = (municipio.codigo_departamento, nombre)
            if llave in self._por_par and self._por_par[llave] != municipio.codigo:
                # Dos municipios con el mismo nombre EN EL MISMO departamento.
                # No debería existir; si existe, ni siquiera el par sirve de
                # llave y hay que saberlo antes de codificar nada.
                self._colisiones.append(llave)
            self._por_par[llave] = municipio.codigo

    def __len__(self) -> int:
        return len(self._municipios)

    @property
    def colisiones_dentro_del_mismo_departamento(self) -> list[tuple[str, str]]:
        return list(self._colisiones)

    @property
    def nombres_repetidos_entre_departamentos(self) -> int:
        """Cuántos nombres comparte más de un municipio.

        Medido sobre la tabla real: **67** contando por nombre normalizado
        (66 tal como los escribe el DANE, más `CHIMÁ`/`CHIMA`, que solo chocan
        al quitar la tilde).
        """
        vistos: dict[str, set[str]] = {}
        for municipio in self._municipios:
            nombre = normalizar_texto(municipio.nombre)
            if nombre is None:
                continue
            vistos.setdefault(nombre, set()).add(municipio.codigo)
        return sum(1 for codigos in vistos.values() if len(codigos) > 1)

    def codigo(
        self, *, departamento: str | None, municipio: object
    ) -> str | None:
        """El código DIVIPOLA de cinco dígitos, o `None`.

        Exige el código de departamento. Sin él no se responde —aunque el
        nombre sea único en todo el país— porque la regla tiene que ser una
        sola: el municipio se identifica por el par. Una excepción «solo
        cuando no hay ambigüedad» se convierte en ambigüedad el día que la
        fuente añade un municipio con ese nombre.
        """
        if departamento is None:
            return None
        nombre = normalizar_texto(municipio)
        if nombre is None:
            return None
        return self._por_par.get((departamento, nombre))


def leer_tabla(ruta: Path) -> TablaDeMunicipios:
    """Carga la tabla capturada y comprueba que sirve antes de devolverla."""
    if not ruta.exists():
        raise TablaDeMunicipiosNoDisponible(
            f"no existe {ruta}: hay que capturarla con capturar-divipola.ps1"
        )
    municipios: list[Municipio] = []
    with ruta.open(encoding="utf-8", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            codigo = (fila.get("codigo") or "").strip()
            nombre = (fila.get("nombre") or "").strip()
            if not codigo or not nombre:
                continue
            municipios.append(Municipio(codigo=codigo, nombre=nombre))

    if not municipios:
        raise TablaDeMunicipiosNoDisponible(f"{ruta} está vacía")

    codigos = {m.codigo for m in municipios}
    if len(codigos) != len(municipios):
        raise TablaDeMunicipiosNoDisponible(
            f"{ruta} trae códigos repetidos: {len(municipios)} filas, "
            f"{len(codigos)} códigos"
        )

    malos = [m.codigo for m in municipios if len(m.codigo) != 5 or not m.codigo.isdigit()]
    if malos:
        raise TablaDeMunicipiosNoDisponible(
            f"códigos que no son cinco dígitos: {malos[:5]}"
        )

    huerfanos = sorted(
        {m.codigo_departamento for m in municipios} - set(DEPARTAMENTOS_DIVIPOLA)
    )
    if huerfanos:
        raise TablaDeMunicipiosNoDisponible(
            f"municipios cuyo departamento no está en la tabla de la 1.6: {huerfanos}"
        )

    if abs(len(municipios) - MUNICIPIOS_ESPERADOS) > MARGEN_RAZONABLE:
        raise TablaDeMunicipiosNoDisponible(
            f"{len(municipios)} municipios, se esperaban ~{MUNICIPIOS_ESPERADOS}: "
            "la captura se truncó o la fuente cambió de forma"
        )

    return TablaDeMunicipios(municipios)
