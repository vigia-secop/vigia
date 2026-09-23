"""Contrato de almacenamiento de la capa cruda."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from vigia.crudo.modelo import RegistroCrudo


class ErrorAlmacen(RuntimeError):
    """El almacén no pudo guardar lo que se le pidió.

    Envuelve los fallos del controlador de base de datos para que el Ciclo y
    la línea de comandos traten un problema de almacenamiento como un error de
    dominio con mensaje, y no como una traza del controlador.
    """


@dataclass(frozen=True)
class ResultadoGuardado:
    """Cuántos registros de la página entraron y cuántos ya estaban."""

    insertados: int
    duplicados: int
    #: Llaves `(id_fila_fuente, hash_contenido)` de lo que de verdad entró.
    #: El Ciclo las necesita para saber CUÁLES eran nuevos y calcular sobre
    #: ellos la señal de ventana corta; un conteo no alcanza para eso.
    insertadas: frozenset[tuple[str, str]] = frozenset()
    #: De esas llaves, los `id_fila_fuente` que la capa cruda NO tenía en
    #: ninguna versión antes de esta página: contratos o procesos que nunca
    #: se habían visto.
    #:
    #: POR QUÉ HACE FALTA ADEMÁS DE `insertadas`. Una fila entra a la capa
    #: cruda por dos razones muy distintas: porque el registro es nuevo, o
    #: porque ya lo teníamos y la fuente lo modificó —otro hash, misma
    #: identidad—. La señal de ventana corta contaba las dos como «registros
    #: nuevos» y el 2026-09-20 dijo 1.506 en el borde. Medido después: de esos,
    #: nuevos de verdad, cero; los 1.506 eran contratos que ya estaban y
    #: cambiaron. Esa confusión llevó a creer que la ventana perdía contratos
    #: y a ensancharla con una razón equivocada.
    ids_nuevos: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.insertados < 0 or self.duplicados < 0:
            raise ValueError(
                f"conteos negativos en ResultadoGuardado: "
                f"insertados={self.insertados}, duplicados={self.duplicados}"
            )
        # `self.insertados` y no `self.insertadas`: el caso peligroso es
        # insertados=5 con el conjunto vacío, que dejaría las señales del Ciclo
        # en cero sin que nada proteste.
        if self.insertados and len(self.insertadas) != self.insertados:
            raise ValueError(
                f"ResultadoGuardado incoherente: {self.insertados} insertados "
                f"pero {len(self.insertadas)} llaves"
            )
        # Un id no puede ser «nuevo» sin haber entrado: si esto falla, la
        # señal de ventana corta contaría algo que no está en la base.
        sobrantes = self.ids_nuevos - {id_fila for id_fila, _ in self.insertadas}
        if sobrantes:
            raise ValueError(
                f"ResultadoGuardado incoherente: {len(sobrantes)} id(s) nuevo(s) "
                "que no están entre las llaves insertadas"
            )

    @property
    def vistos(self) -> int:
        return self.insertados + self.duplicados


class RepositorioCrudo(Protocol):
    """Almacén de solo inserción para la capa cruda.

    Una página entra completa o no entra: la implementación guarda el lote en
    una sola transacción. Un registro cuya identidad ya existe se cuenta como
    duplicado y no altera lo almacenado — incluida la repetición dentro de la
    misma página.
    """

    def guardar_pagina(self, registros: Sequence[RegistroCrudo]) -> ResultadoGuardado:
        ...
