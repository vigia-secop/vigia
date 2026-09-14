"""Territorio y orden administrativo (historia 1.6).

Sin territorio no se puede comparar a una alcaldía con otra alcaldía, ni mirar
un departamento por separado, ni distinguir lo nacional de lo territorial. Y
esa última distinción dejó de ser un adorno el 7 de agosto de 2026: el cambio
de gobierno movió lo NACIONAL y no movió lo territorial —alcaldes y
gobernadores siguen en su periodo 2024-2027—, así que cualquier serie que
mezcle los dos órdenes atribuye al cambio de gobierno lo que es otra cosa.

LO QUE SE MIDIÓ ANTES DE DISEÑAR (fuente `jbjy-vk9h`, 2026-09-05).

**1. `orden` no es binario: son TRES valores.**

| `orden` | agosto 2026 | año 2019 |
|---|---|---|
| Territorial | 90 101 | 73 932 |
| Nacional | 19 967 | 66 860 |
| **Corporación Autónoma** | **2 224** | **1 800** |

Las Corporaciones Autónomas Regionales —las CAR— no son ni nacionales ni
territoriales: son entidades con autonomía propia. Aparecen en los dos cortes
medidos, con siete años de distancia, así que no son ruido de un mes. Una
clasificación de dos cajones las habría metido en el que no es, y son quienes
manejan la plata ambiental.

**2. Los nombres de departamento vienen limpios.** 33 valores distintos en un
mes: los 32 departamentos más Bogotá, sin variantes ni erratas. Más 1 593
contratos (1,4 %) con «No Definido». No hace falta limpiar nombres; hace falta
traducirlos.

**3. Pero NO coinciden con DIVIPOLA, y fallan justo donde más duele.** El DANE
escribe `BOGOTÁ, D.C.` y el SECOP `Distrito Capital de Bogotá`; el DANE
`ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA` y el SECOP
`San Andrés, Providencia y Santa Catalina`. Los otros 31 cuadran al pasar a
mayúsculas y quitar tildes. Es decir: **un cruce por nombre deja sin código a
Bogotá, que es el 16 % de los contratos del país, y lo deja en silencio.**

**4. El municipio no se identifica por su nombre.** `Argelia` son tres
municipios distintos —Antioquia (16 contratos), Cauca (16) y Valle del Cauca
(15)—. Los conteos son casi iguales, así que fundirlos no se vería raro en
ningún reporte. La llave del municipio es el PAR (departamento, municipio),
nunca el nombre solo.

ALCANCE DE ESTA ENTREGA. Se codifica el DEPARTAMENTO, que son 33 filas
verificables una por una contra el dataset oficial del DANE. El municipio se
conserva con su nombre y su departamento, **pero sin código**: son ~1 100
entradas y hasta no tener la tabla oficial cargada y comprobada, poner un
código adivinado sería peor que no ponerlo. La medición 4 ya dice por qué.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from vigia.normalizado.proveedor import normalizar_texto

#: Campos de Contratos que traen territorio y orden.
CAMPO_ORDEN = "orden"
CAMPO_DEPARTAMENTO = "departamento"
CAMPO_MUNICIPIO = "ciudad"

#: Los tres valores de `orden` medidos en la fuente, ya normalizados.
ORDEN_NACIONAL = "NACIONAL"
ORDEN_TERRITORIAL = "TERRITORIAL"
ORDEN_CORPORACION_AUTONOMA = "CORPORACION AUTONOMA"

#: Los que la fuente sí sabe clasificar. Cualquier otra cosa —incluido
#: «No Definido»— se queda en `None`, que NO es lo mismo que territorial.
ORDENES_CONOCIDOS = frozenset(
    {ORDEN_NACIONAL, ORDEN_TERRITORIAL, ORDEN_CORPORACION_AUTONOMA}
)

#: Departamentos según DIVIPOLA, del dataset oficial del DANE `vcjz-niiq`
#: (Datos Abiertos Colombia), consultado el 2026-09-05. Son 33: los 32
#: departamentos más Bogotá D.C.
#:
#: Se guarda aquí, versionado en el repositorio, en vez de consultarse en cada
#: corrida. Es la misma decisión que la tabla de esquemas esperados de la 1.3 y
#: por la misma razón: una tabla que cambia bajo los pies convierte cualquier
#: serie histórica en algo incomparable, y la división político-administrativa
#: cambia —municipios nuevos, departamentos que se reorganizan— aunque
#: despacio. Cuando cambie, se cambia aquí y se ve en el diff.
DEPARTAMENTOS_DIVIPOLA: dict[str, str] = {
    "05": "ANTIOQUIA",
    "08": "ATLANTICO",
    "11": "BOGOTA, D.C.",
    "13": "BOLIVAR",
    "15": "BOYACA",
    "17": "CALDAS",
    "18": "CAQUETA",
    "19": "CAUCA",
    "20": "CESAR",
    "23": "CORDOBA",
    "25": "CUNDINAMARCA",
    "27": "CHOCO",
    "41": "HUILA",
    "44": "LA GUAJIRA",
    "47": "MAGDALENA",
    "50": "META",
    "52": "NARINO",
    "54": "NORTE DE SANTANDER",
    "63": "QUINDIO",
    "66": "RISARALDA",
    "68": "SANTANDER",
    "70": "SUCRE",
    "73": "TOLIMA",
    "76": "VALLE DEL CAUCA",
    "81": "ARAUCA",
    "85": "CASANARE",
    "86": "PUTUMAYO",
    "88": "ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA",
    "91": "AMAZONAS",
    "94": "GUAINIA",
    "95": "GUAVIARE",
    "97": "VAUPES",
    "99": "VICHADA",
}

#: Los DOS nombres que el SECOP escribe distinto al DANE.
#:
#: No son una lista defensiva «por si acaso»: son exactamente los dos que
#: fallaron al comparar los 33 nombres de la fuente contra los 33 del DANE el
#: 2026-09-05. Los otros 31 cuadran al normalizar. Se declaran explícitos, con
#: su código, para que el fallo de Bogotá —el 16 % de los contratos del país—
#: no pueda volver a pasar en silencio.
ALIAS_SECOP: dict[str, str] = {
    "DISTRITO CAPITAL DE BOGOTA": "11",
    "SAN ANDRES, PROVIDENCIA Y SANTA CATALINA": "88",
}


def _indice_por_nombre() -> dict[str, str]:
    indice = {nombre: codigo for codigo, nombre in DEPARTAMENTOS_DIVIPOLA.items()}
    indice.update(ALIAS_SECOP)
    return indice


_POR_NOMBRE = _indice_por_nombre()


def clasificar_orden(valor: object) -> str | None:
    """El orden administrativo declarado, o `None` si la fuente no lo dice.

    `None` es un tercer estado con significado propio y no se debe rellenar
    con «Territorial» por ser el más común: un contrato sin orden declarado no
    es territorial, es desconocido, y una serie que los mezcle atribuiría al
    cambio de gobierno movimientos que no puede explicar.
    """
    normalizado = normalizar_texto(valor)
    if normalizado is None:
        return None
    return normalizado if normalizado in ORDENES_CONOCIDOS else None


def codigo_departamento(nombre: object) -> str | None:
    """El código DIVIPOLA del departamento, o `None`.

    `None` cubre los dos casos honestos: que la fuente traiga «No Definido»
    —1,4 % de los contratos— y que traiga un nombre que esta tabla no conoce.
    Los dos merecen quedarse sin código antes que recibir uno inventado.
    """
    normalizado = normalizar_texto(nombre)
    if normalizado is None:
        return None
    return _POR_NOMBRE.get(normalizado)


def nombre_oficial(codigo: str | None) -> str | None:
    """El nombre DIVIPOLA que corresponde a un código."""
    if codigo is None:
        return None
    return DEPARTAMENTOS_DIVIPOLA.get(codigo)


@dataclass(frozen=True)
class Territorio:
    """Dónde ocurre un contrato y bajo qué orden administrativo.

    El municipio viaja con su nombre y SIN código a propósito. Ver el alcance
    declarado en el docstring del módulo: `Argelia` son tres municipios en tres
    departamentos, así que el nombre solo no identifica a ninguno, y un código
    adivinado es peor que ninguno.
    """

    orden: str | None
    departamento_codigo: str | None
    departamento_nombre: str | None
    municipio_nombre: str | None

    @property
    def sin_departamento(self) -> bool:
        """No se le pudo poner código de departamento.

        Es la población que ninguna Regla con corte territorial puede mirar,
        así que tiene que ser medible y no quedar escondida.
        """
        return self.departamento_codigo is None

    @property
    def sin_orden(self) -> bool:
        return self.orden is None

    @property
    def es_nacional(self) -> bool:
        """Solo lo declarado Nacional. Una CAR no lo es, y una alcaldía tampoco.

        Importa para el corte del 7 de agosto de 2026: el cambio de gobierno
        movió lo nacional y no movió lo territorial.
        """
        return self.orden == ORDEN_NACIONAL


def desde_contenido(contenido: Mapping[str, object]) -> Territorio:
    """Lee territorio y orden de una fila cruda de Contratos."""
    codigo = codigo_departamento(contenido.get(CAMPO_DEPARTAMENTO))
    return Territorio(
        orden=clasificar_orden(contenido.get(CAMPO_ORDEN)),
        departamento_codigo=codigo,
        # El nombre que se guarda es el OFICIAL cuando se pudo resolver, no el
        # que escribió la entidad: así dos contratos del mismo departamento se
        # muestran igual aunque la fuente los llame distinto.
        departamento_nombre=nombre_oficial(codigo)
        or normalizar_texto(contenido.get(CAMPO_DEPARTAMENTO)),
        municipio_nombre=normalizar_texto(contenido.get(CAMPO_MUNICIPIO)),
    )
