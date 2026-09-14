"""Bandera de oferente único (historia 2.4).

LO QUE SE MIDIÓ ANTES DE ESCRIBIR UNA LÍNEA DE LA REGLA (base real de
Guillermo, 2026-09-05, 341 549 procesos de los cuales **9 942 adjudicados**):

**1. El embudo SÍ llega poblado.** De los 9 942 adjudicados, 9 934 —el
99,92 %— traen `respuestas_al_procedimiento >= 1`, y 9 731 traen proveedores
únicos. Solo 8 llegan en cero. La bandera se puede construir: el dato existe.

**2. Pero un umbral global sería inservible.** Distribución de respuestas entre
los adjudicados:

| Respuestas | Procesos |
|---|---|
| **1** | **5 415** |
| 2 | 1 495 |
| 3 | 808 |
| 4 | 524 |
| 5 | 335 |

**Más de la mitad de los procesos adjudicados del país tienen exactamente una
respuesta.** Una Regla que marcara «una sola respuesta» encendería 5 415
alertas sobre 9 942 procesos. Eso no es una señal: es el estado normal, y
lanzarlo a la cola la vuelve inservible el primer día.

**3. Lo que convierte el ruido en señal es la MODALIDAD.** De los 9 942
adjudicados, 7 766 —el 78 %— están en modalidades donde una sola oferta es el
desenlace esperado: mínima cuantía (5 390), contratación directa con ofertas
(1 378) y régimen especial (998). Quedan ~2 176 en modalidades competitivas de
verdad. Por eso el tercer criterio de aceptación —«modalidad no competitiva, no
se emite Alerta»— no es una cortesía: es lo único que hace que la bandera
signifique algo.

**4. El caso que la historia describe existe, y no es raro.** 4 137 procesos
adjudicados tienen UNA respuesta habiendo tenido más de un invitado o más de
una visualización, con un promedio de 83,8 invitados y 10 visualizaciones. En
la muestra hay Selección Abreviada de Menor Cuantía con **178 visualizaciones y
una sola respuesta**.

DOS CONTADORES QUE NO SIRVEN, Y HAY QUE DECIRLO:

- `proveedores_que_manifestaron` llega en **cero en todos** los casos mirados.
  Va al Expediente porque el criterio de aceptación lo pide, pero la Regla no
  puede apoyarse en él.
- `proveedores_invitados` solo está poblado en 2 554 de 9 942 (25,7 %). La
  segunda pata del embudo tiene que ser `visualizaciones_del`, que sí llega en
  el 94,6 %.

EL UMBRAL NO SE FIJA AQUÍ. Se fija calibrando, y por eso la Regla nace en
`borrador` y no puede activarse sin haber corrido sobre un recorte. Lo que este
módulo aporta es que el número de partida está medido y no adivinado.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from vigia.reglas.modelo import Alerta, Regla, VersionDeRegla, emitir

CODIGO = "oferente-unico"

#: Campos del embudo en el dataset `procesos`.
CAMPO_MODALIDAD = "modalidad_de_contratacion"
CAMPO_ADJUDICADO = "adjudicado"
CAMPO_ID = "id_del_proceso"
CAMPO_URL = "urlproceso"

EMBUDO = (
    "proveedores_invitados",
    "proveedores_con_invitacion",
    "visualizaciones_del",
    "proveedores_que_manifestaron",
    "respuestas_al_procedimiento",
    "respuestas_externas",
    "conteo_de_respuestas_a_ofertas",
    "proveedores_unicos_con",
    "numero_de_lotes",
)

#: Modalidades competitivas, tal como las escribe la fuente.
#:
#: Es el valor con el que se CREA la primera versión de la Regla; el valor que
#: manda en cada evaluación es el de la versión, no este. La 2.1 exige que los
#: umbrales no vivan en el código, y esto es una semilla, no un umbral.
#:
#: La lista sale de los 9 942 procesos adjudicados medidos: son las modalidades
#: que quedan al quitar mínima cuantía, contratación directa y régimen especial,
#: donde una sola oferta es el desenlace esperado.
MODALIDADES_COMPETITIVAS_POR_DEFECTO = (
    "Licitación pública",
    "Licitación pública Obra Publica",
    "Selección Abreviada de Menor Cuantía",
    "Selección abreviada subasta inversa",
    "Seleccion Abreviada Menor Cuantia Sin Manifestacion Interes",
    "Concurso de méritos abierto",
    "Enajenación de bienes con sobre cerrado",
    "Enajenación de bienes con subasta",
)

#: Con cuántos proveedores únicos o menos se enciende. Semilla, no verdad.
PROVEEDORES_UNICOS_MAXIMOS_POR_DEFECTO = 1


def umbrales_iniciales() -> dict[str, Any]:
    """Los umbrales con los que nace la Regla, todos medidos o declarados."""
    return {
        "proveedores_unicos_maximos": PROVEEDORES_UNICOS_MAXIMOS_POR_DEFECTO,
        "modalidades_competitivas": list(MODALIDADES_COMPETITIVAS_POR_DEFECTO),
        "exige_adjudicado": True,
    }


def crear(momento: datetime) -> Regla:
    """La Regla recién nacida: en borrador, con su primera versión."""
    regla = Regla(
        codigo=CODIGO,
        nombre="Oferente único",
        descripcion=(
            "Procesos de modalidad competitiva que terminan adjudicados con un "
            "solo proponente. Es un indicador estadístico: puede tener "
            "explicaciones normales, y por sí solo no dice nada sobre la "
            "conducta de nadie."
        ),
    )
    regla.nueva_version(
        umbrales_iniciales(),
        momento=momento,
        nota=(
            "Semilla medida sobre 9 942 procesos adjudicados: el 54,5 % tiene "
            "una sola respuesta, así que sin el filtro de modalidad la bandera "
            "marcaría más de la mitad del país."
        ),
    )
    return regla


def _entero(contenido: Mapping[str, Any], campo: str) -> int | None:
    """Un contador del embudo. Llega como texto y puede venir vacío."""
    crudo = contenido.get(campo)
    if crudo is None:
        return None
    try:
        return int(str(crudo).strip())
    except (TypeError, ValueError):
        return None


def _normalizar(texto: object) -> str:
    import unicodedata
    if not isinstance(texto, str):
        return ""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.upper().split())


def es_competitiva(modalidad: object, competitivas) -> bool:
    """Si la modalidad admite competencia.

    Se compara normalizado —sin tildes, sin mayúsculas, sin espacios dobles—
    porque la fuente escribe «Selección Abreviada de Menor Cuantía» y
    «Seleccion Abreviada Menor Cuantia» en el mismo campo.
    """
    objetivo = _normalizar(modalidad)
    return any(objetivo == _normalizar(c) for c in competitivas)


def embudo(contenido: Mapping[str, Any]) -> dict[str, int | None]:
    """Los nueve contadores, tal como los trae la fuente.

    Van completos al Expediente aunque la Regla solo mire dos: el criterio de
    aceptación pide el embudo entero, y quien revise la Alerta meses después
    necesita ver por dónde se estrechó, no solo que se estrechó.
    """
    return {campo: _entero(contenido, campo) for campo in EMBUDO}


def evaluar(
    contenido: Mapping[str, Any], *,
    regla: Regla,
    version: VersionDeRegla,
    consultado_en: datetime,
    momento: datetime,
) -> Alerta | None:
    """Devuelve una Alerta si el proceso enciende la bandera, o `None`.

    `None` NO es un fallo: es el resultado normal. La Regla no se pronuncia
    sobre lo que no cumple sus tres condiciones.
    """
    umbrales = version.umbrales
    if umbrales.get("exige_adjudicado", True):
        if _normalizar(contenido.get(CAMPO_ADJUDICADO)) != "SI":
            return None

    if not es_competitiva(
        contenido.get(CAMPO_MODALIDAD), umbrales.get("modalidades_competitivas", ())
    ):
        return None

    cuenta = embudo(contenido)
    unicos = cuenta["proveedores_unicos_con"]
    if unicos is None:
        # Sin el contador no hay nada que comparar. Emitir igual sería inventar.
        return None
    if unicos > umbrales["proveedores_unicos_maximos"]:
        return None

    identificador = contenido.get(CAMPO_ID)
    if not identificador:
        return None

    url = contenido.get(CAMPO_URL)
    if isinstance(url, Mapping):
        url = url.get("url")

    return emitir(
        regla, version,
        id_registro_fuente=str(identificador),
        dataset="procesos",
        valores_disparadores={
            "modalidad": contenido.get(CAMPO_MODALIDAD),
            **cuenta,
        },
        consultado_en=consultado_en,
        momento=momento,
        url_proceso=url if isinstance(url, str) else None,
    )
