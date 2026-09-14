"""Comparar el esquema que la fuente declara contra el que se espera.

Se compara contra el **esquema declarado del dataset**, no contra las claves de
un registro. En Socrata un campo nulo no llega como `null`: la clave
simplemente no aparece. Validar fila a fila reportaría campos «faltantes» en
casi todos los Ciclos, y una alarma que suena siempre deja de existir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from vigia.crudo.repositorio import ErrorAlmacen
from vigia.ingest.datasets import DatasetSecop
from vigia.schema.definiciones import EsquemaEsperado
from vigia.schema.novedades import Novedad, RepositorioNovedades

registro_log = logging.getLogger(__name__)


class EsquemaCambiado(RuntimeError):
    """La fuente dejó de declarar un campo que se esperaba.

    Detiene el Ciclo antes de traer nada. Es la traducción de «falla
    ruidosamente»: la alternativa es un mes de datos incompletos descubierto
    semanas después.

    Lleva `dataset` y `faltantes` como atributos para que quien la atrape no
    tenga que buscar dentro del mensaje.
    """

    def __init__(self, mensaje: str, *, dataset: str, faltantes: tuple[str, ...]) -> None:
        super().__init__(mensaje)
        self.dataset = dataset
        self.faltantes = faltantes


class LectorDeColumnas(Protocol):
    """Lo mínimo que la validación necesita de la fuente."""

    def columnas(self, dataset: DatasetSecop) -> frozenset[str]:
        ...


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ResultadoValidacion:
    """Qué se cayó y qué apareció."""

    dataset: str
    faltantes: tuple[str, ...]
    novedades: tuple[str, ...]

    @property
    def intacto(self) -> bool:
        return not self.faltantes and not self.novedades


class ValidadorDeEsquema:
    """Corre la comparación antes de que el Ciclo pida el primer registro."""

    def __init__(
        self,
        lector: LectorDeColumnas,
        esperado: EsquemaEsperado,
        repositorio: RepositorioNovedades,
        *,
        reloj: Callable[[], datetime] = _ahora_utc,
    ) -> None:
        self._lector = lector
        self._esperado = esperado
        self._repositorio = repositorio
        self._reloj = reloj

    def validar(self, dataset: DatasetSecop) -> ResultadoValidacion:
        if dataset.nombre != self._esperado.dataset:
            raise ValueError(
                f"el esquema esperado es de {self._esperado.dataset!r} "
                f"y se está validando {dataset.nombre!r}"
            )

        declaradas = self._lector.columnas(dataset)
        faltantes = tuple(sorted(self._esperado.campos - declaradas))
        novedades = tuple(sorted(declaradas - self._esperado.campos))

        if novedades:
            # Se registran incluso cuando hay faltantes: si la fuente renombró
            # un campo, el faltante y la novedad son las dos mitades del mismo
            # hecho y hacen falta ambas para entenderlo.
            registro_log.warning(
                "campos nuevos en %s (%d): %s",
                dataset.nombre,
                len(novedades),
                ", ".join(novedades),
            )
            self._registrar(dataset.nombre, novedades)

        if faltantes:
            raise EsquemaCambiado(
                f"el dataset {dataset.nombre!r} ({dataset.id_socrata}) dejó de declarar "
                f"{len(faltantes)} campo(s) esperado(s): {', '.join(faltantes)}. "
                f"El esquema esperado se capturó el {self._esperado.capturado_en.isoformat()}. "
                f"Revisa el cambio en la fuente antes de volver a ingerir; si el cambio es "
                f"legítimo, recaptura el esquema.",
                dataset=dataset.nombre,
                faltantes=faltantes,
            )

        return ResultadoValidacion(
            dataset=dataset.nombre, faltantes=faltantes, novedades=novedades
        )

    def _registrar(self, dataset: str, novedades: tuple[str, ...]) -> None:
        """Persiste las novedades sin que su fallo detenga el Ciclo.

        Un campo nuevo no debe detener nada — así lo pide la historia. Si el
        registro falla (la tabla no existe todavía, la base no responde), eso
        queda en el log como problema de operación, no convertido en un Ciclo
        muerto por una novedad que ni siquiera era un problema.
        """
        momento = self._reloj()
        try:
            self._repositorio.registrar(
                [
                    Novedad(dataset=dataset, campo=campo, detectado_en=momento)
                    for campo in novedades
                ]
            )
        except ErrorAlmacen as error:
            registro_log.error(
                "no se pudieron registrar las novedades de %s; el Ciclo continúa: %s",
                dataset,
                error,
            )
