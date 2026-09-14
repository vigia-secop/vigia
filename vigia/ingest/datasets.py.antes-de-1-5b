"""Los datasets del SECOP que la v1 ingiere.

Único lugar donde viven los identificadores de Socrata. SECOP I y TVEC quedan
fuera de la v1 por decisión de alcance; añadir un dataset es una decisión que
se consulta, no un cambio de configuración.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetSecop:
    """Descriptor de un dataset de la fuente."""

    #: Nombre de dominio, en los términos del glosario del PRD.
    nombre: str
    #: Identificador del dataset en Socrata.
    id_socrata: str
    #: Campo de fecha sobre el que se acota el rango de una ingesta.
    campo_fecha_rango: str
    #: Campos que identifican una fila **en el negocio**, en orden.
    #:
    #: NO se usa el `:id` de Socrata: es un identificador de la plataforma y la
    #: fuente se lo reasigna a la misma fila entre publicaciones. Medido el
    #: 2026-09-03: tres Ciclos sobre el rango idéntico dejaron 50 434 filas
    #: crudas con 50 434 `:id` distintos para 25 749 contratos. Ver
    #: `sprint-change-proposal-2026-09-04.md`.
    #:
    #: El primero es obligatorio; los demás se añaden si vienen poblados. Así
    #: una fila que aún no tiene el segundo componente —un proceso sin
    #: adjudicar— tiene identidad igualmente, y la gana cuando lo tenga.
    campos_identidad: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.campos_identidad:
            raise ValueError(
                f"el dataset {self.nombre!r} no declara campos de identidad; "
                "sin ellos no hay idempotencia posible"
            )


#: Grano: un contrato firmado. 85 columnas.
CONTRATOS = DatasetSecop(
    nombre="contratos",
    id_socrata="jbjy-vk9h",
    campo_fecha_rango="fecha_de_firma",
    # Un contrato por fila: `id_contrato` basta.
    campos_identidad=("id_contrato",),
)

#: Grano: un proceso de contratación, adjudicado o no.
PROCESOS = DatasetSecop(
    nombre="procesos",
    id_socrata="p6dx-8zbt",
    campo_fecha_rango="fecha_de_publicacion_del",
    # UNA FILA POR ADJUDICACIÓN, no por proceso: un procedimiento de varios
    # lotes con varios adjudicatarios aparece muchas veces (medido en la 1.4:
    # 21 filas para `CO1.REQ.10772032`). Identificar solo por `id_del_proceso`
    # colapsaría adjudicaciones distintas en una sola fila cruda y perdería
    # dato que la fuente sí entregó.
    campos_identidad=("id_del_proceso", "id_adjudicacion"),
)

DATASETS: dict[str, DatasetSecop] = {
    dataset.nombre: dataset for dataset in (CONTRATOS, PROCESOS)
}
