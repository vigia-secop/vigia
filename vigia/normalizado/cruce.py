"""Deduplicar Procesos, enlazar Contratos y contar lo que no cuadró.

Las tres señales que produce este módulo responden preguntas distintas que es
fácil confundir, y confundirlas es cómo un indicador de calidad de datos deja
de servir:

- **huérfanos** — el contrato trae llave y no encontró Proceso. Puede ser que
  el Proceso no se haya ingerido todavía, o que la fuente no lo publique.
- **sin llave de cruce** — el contrato ni siquiera trae `proceso_de_compra`.
  No es un problema del cruce: es un campo que llega vacío.
- **procesos colapsados** — filas crudas de Procesos descartadas al
  deduplicar. El dataset trae una fila por adjudicación, no por Proceso.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator, Protocol

from vigia.crudo.modelo import RegistroCrudo
from vigia.normalizado.modelo import (
    ContratoNormalizado,
    ProcesoNormalizado,
    RegistroSinIdentidadNormalizada,
)

registro_log = logging.getLogger(__name__)


class FuenteCruda(Protocol):
    """De dónde salen los registros a normalizar.

    Emite la versión **más reciente** de cada fila: la capa cruda es de solo
    inserción y guarda todas las versiones, pero normalizar la vieja sobre la
    nueva dejaría la capa normalizada mostrando el pasado.
    """

    def ultimos_registros(self, dataset: str) -> Iterator[RegistroCrudo]:
        ...


@dataclass(frozen=True)
class ResumenNormalizacion:
    """Lo que hizo una normalización. Todos los conteos son verificables."""

    procesos_leidos: int
    procesos_normalizados: int
    contratos_leidos: int
    contratos_normalizados: int
    huerfanos: int
    sin_llave_de_cruce: int
    sin_identidad: int

    def __post_init__(self) -> None:
        for nombre, valor in vars(self).items():
            if valor < 0:
                raise ValueError(f"{nombre} no puede ser negativo: {valor}")
        if self.contratos_normalizados + self.sin_identidad != self.contratos_leidos:
            raise ValueError(
                "conteos de contratos incoherentes: "
                f"{self.contratos_normalizados} normalizados + {self.sin_identidad} "
                f"sin identidad != {self.contratos_leidos} leídos"
            )
        if self.huerfanos + self.sin_llave_de_cruce > self.contratos_normalizados:
            raise ValueError(
                f"{self.huerfanos} huérfanos + {self.sin_llave_de_cruce} sin llave "
                f"superan los {self.contratos_normalizados} contratos normalizados"
            )

    @property
    def procesos_colapsados(self) -> int:
        """Filas de Procesos descartadas por deduplicación.

        Se expone siempre, incluso en cero: una deduplicación silenciosa es
        indistinguible de una pérdida de datos.
        """
        return self.procesos_leidos - self.procesos_normalizados

    @property
    def enlazados(self) -> int:
        return self.contratos_normalizados - self.huerfanos - self.sin_llave_de_cruce

    @property
    def proporcion_huerfanos(self) -> float | None:
        """Sobre los contratos que **sí traen llave**, que es la población de
        la que habla FR-2. Incluir los que no la traen mezcla dos fallos y
        mueve el indicador por la razón equivocada.
        """
        con_llave = self.contratos_normalizados - self.sin_llave_de_cruce
        if con_llave == 0:
            return None
        return self.huerfanos / con_llave


def deduplicar_procesos(
    registros: Iterable[RegistroCrudo], *, momento: datetime
) -> tuple[dict[str, ProcesoNormalizado], int, int]:
    """Convierte y deduplica por `id_del_proceso`.

    Devuelve `(procesos, leídos, sin_identidad)`. Gana la última versión vista:
    los campos procedimentales son idénticos entre las filas de un mismo
    Proceso —lo que varía es el adjudicatario, que esta historia no
    normaliza—, así que cuál gane no cambia el resultado.
    """
    procesos: dict[str, ProcesoNormalizado] = {}
    leidos = 0
    sin_identidad = 0
    for registro in registros:
        leidos += 1
        try:
            proceso = ProcesoNormalizado.desde_crudo(registro, momento=momento)
        except RegistroSinIdentidadNormalizada as error:
            sin_identidad += 1
            registro_log.warning("proceso descartado · %s", error)
            continue
        procesos[proceso.id_del_proceso] = proceso
    return procesos, leidos, sin_identidad


def indexar_por_portafolio(
    procesos: Iterable[ProcesoNormalizado],
) -> dict[str, str]:
    """`id_del_portafolio` -> `id_del_proceso`.

    No está medido si un portafolio puede corresponder a más de un Proceso. Si
    ocurre, gana el último y **se registra**: un cruce ambiguo resuelto en
    silencio es una afirmación sin respaldo, y aquí todo tiene que poder
    sustentarse.
    """
    indice: dict[str, str] = {}
    for proceso in procesos:
        portafolio = proceso.id_del_portafolio
        if portafolio is None:
            continue
        anterior = indice.get(portafolio)
        if anterior is not None and anterior != proceso.id_del_proceso:
            registro_log.warning(
                "portafolio %s apunta a más de un proceso (%s y %s); gana el último",
                portafolio,
                anterior,
                proceso.id_del_proceso,
            )
        indice[portafolio] = proceso.id_del_proceso
    return indice


def cruzar_contratos(
    registros: Iterable[RegistroCrudo],
    *,
    indice_portafolio: dict[str, str],
    momento: datetime,
) -> tuple[list[ContratoNormalizado], int, int]:
    """Convierte cada contrato y le resuelve su Proceso si lo encuentra.

    Devuelve `(contratos, leídos, sin_identidad)`. Un contrato que no cruza
    entra igual, marcado como huérfano: FR-2 exige que sea consultable y que
    no se descarte en silencio.
    """
    contratos: list[ContratoNormalizado] = []
    leidos = 0
    sin_identidad = 0
    for registro in registros:
        leidos += 1
        try:
            contrato = ContratoNormalizado.desde_crudo(registro, momento=momento)
        except RegistroSinIdentidadNormalizada as error:
            sin_identidad += 1
            registro_log.warning("contrato descartado · %s", error)
            continue
        if contrato.proceso_de_compra is not None:
            enlace = indice_portafolio.get(contrato.proceso_de_compra)
            if enlace is not None:
                contrato = contrato.enlazado_a(enlace)
        contratos.append(contrato)
    return contratos, leidos, sin_identidad


def resumir(
    contratos: list[ContratoNormalizado],
    *,
    procesos_leidos: int,
    procesos_normalizados: int,
    contratos_leidos: int,
    contratos_sin_identidad: int,
) -> ResumenNormalizacion:
    return ResumenNormalizacion(
        procesos_leidos=procesos_leidos,
        procesos_normalizados=procesos_normalizados,
        contratos_leidos=contratos_leidos,
        contratos_normalizados=len(contratos),
        huerfanos=sum(1 for c in contratos if c.huerfano),
        sin_llave_de_cruce=sum(1 for c in contratos if c.sin_llave_de_cruce),
        sin_identidad=contratos_sin_identidad,
    )
