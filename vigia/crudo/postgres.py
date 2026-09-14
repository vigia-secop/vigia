"""Capa cruda sobre PostgreSQL (AD-1: crudo en JSONB, solo inserción)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Sequence

import psycopg
from psycopg.types.json import Jsonb

from vigia.crudo.modelo import RegistroCrudo
from vigia.crudo.repositorio import ErrorAlmacen, ResultadoGuardado

_INSERTAR = """
INSERT INTO crudo_registro
    (dataset, id_fila_fuente, hash_contenido, contenido, consultado_en)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (dataset, id_fila_fuente, hash_contenido) DO NOTHING
RETURNING id_fila_fuente, hash_contenido
"""


class RepositorioPostgres:
    """Almacén de la capa cruda respaldado por PostgreSQL.

    La idempotencia no se comprueba en Python: la produce la llave primaria
    compuesta con ``ON CONFLICT DO NOTHING``. Dos procesos ingiriendo el mismo
    registro a la vez llegan al mismo estado sin coordinarse.
    """

    def __init__(self, conexion: psycopg.Connection) -> None:
        self._conexion = conexion

    def guardar_pagina(self, registros: Sequence[RegistroCrudo]) -> ResultadoGuardado:
        if not registros:
            return ResultadoGuardado(insertados=0, duplicados=0)

        parametros = [
            (
                registro.dataset,
                registro.id_fila_fuente,
                registro.hash_contenido,
                Jsonb(dict(registro.contenido)),
                registro.consultado_en,
            )
            for registro in registros
        ]

        try:
            # Una transacción por página: el lote entra completo o no entra, y
            # queda confirmado por sí solo. Que una página posterior falle no
            # deshace las anteriores.
            with self._conexion.transaction(), self._conexion.cursor() as cursor:
                # `returning=True` deja recorrer el resultado de cada sentencia:
                # el motor dice exactamente cuáles entraron, que es más preciso
                # que `rowcount` y es lo que el Ciclo necesita para su señal de
                # ventana corta.
                cursor.executemany(_INSERTAR, parametros, returning=True)
                insertadas: set[tuple[str, str]] = set()
                while True:
                    insertadas.update((fila[0], fila[1]) for fila in cursor.fetchall())
                    if not cursor.nextset():
                        break
                insertados = len(insertadas)
        except psycopg.Error as error:
            raise ErrorAlmacen(
                f"fallo guardando una página de {len(registros)} registros "
                f"del dataset {registros[0].dataset!r}: {error}"
            ) from error

        if insertados < 0 or insertados > len(registros):
            raise ErrorAlmacen(
                "el controlador reportó un conteo de inserción imposible: "
                f"{insertados} sobre una página de {len(registros)} registros"
            )
        return ResultadoGuardado(
            insertados=insertados,
            duplicados=len(registros) - insertados,
            insertadas=frozenset(insertadas),
        )


@contextmanager
def repositorio_postgres(dsn: str) -> Iterator[RepositorioPostgres]:
    """Abre una conexión y entrega el repositorio; la cierra al salir.

    Cada página se confirma en su propia transacción dentro de
    `guardar_pagina`, así que una excepción que salga de este bloque no
    deshace lo ya ingerido.
    """
    try:
        conexion = psycopg.connect(dsn)
    except psycopg.Error as error:
        raise ErrorAlmacen(f"no se pudo conectar a la base de datos: {error}") from error
    with conexion:
        yield RepositorioPostgres(conexion)
