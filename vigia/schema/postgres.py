"""Registro de novedades de esquema sobre PostgreSQL."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Sequence

import psycopg

from vigia.crudo.repositorio import ErrorAlmacen
from vigia.schema.novedades import Novedad

# `LEAST` y `GREATEST` hacen que el registro no dependa del orden en que
# lleguen los Ciclos: la primera detección solo puede retroceder en el tiempo
# y la última solo puede avanzar. Un reproceso de un rango viejo corrige la
# primera; un Ciclo que llega tarde no pisa la última.
_REGISTRAR = """
INSERT INTO esquema_novedad (dataset, campo, primera_deteccion, ultima_deteccion)
VALUES (%s, %s, %s, %s)
ON CONFLICT (dataset, campo) DO UPDATE
SET primera_deteccion = LEAST(
        esquema_novedad.primera_deteccion,
        EXCLUDED.primera_deteccion
    ),
    ultima_deteccion = GREATEST(
        esquema_novedad.ultima_deteccion,
        EXCLUDED.ultima_deteccion
    )
"""


class RepositorioNovedadesPostgres:
    """Conserva la primera detección de cada campo y actualiza la última."""

    def __init__(self, conexion: psycopg.Connection) -> None:
        self._conexion = conexion

    def registrar(self, novedades: Sequence[Novedad]) -> None:
        if not novedades:
            return

        parametros = [
            (novedad.dataset, novedad.campo, novedad.detectado_en, novedad.detectado_en)
            for novedad in novedades
        ]
        try:
            with self._conexion.transaction(), self._conexion.cursor() as cursor:
                cursor.executemany(_REGISTRAR, parametros)
        except psycopg.Error as error:
            datasets = ", ".join(sorted({novedad.dataset for novedad in novedades}))
            raise ErrorAlmacen(
                f"fallo registrando {len(novedades)} novedad(es) de esquema "
                f"de {datasets}: {error}"
            ) from error


@contextmanager
def repositorio_novedades_postgres(dsn: str) -> Iterator[RepositorioNovedadesPostgres]:
    try:
        conexion = psycopg.connect(dsn)
    except psycopg.Error as error:
        raise ErrorAlmacen(f"no se pudo conectar a la base de datos: {error}") from error
    with conexion:
        yield RepositorioNovedadesPostgres(conexion)
