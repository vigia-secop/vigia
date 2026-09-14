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
