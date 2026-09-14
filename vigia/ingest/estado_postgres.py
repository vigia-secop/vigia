"""Estado de la ingesta sobre PostgreSQL."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg

from vigia.crudo.repositorio import ErrorAlmacen
from vigia.ingest.estado import MarcaDeAgua, RegistroDeCiclo

_LEER_MARCA = """
SELECT dataset, fecha_hecho, actualizada_en FROM ingesta_marca WHERE dataset = %s
"""

_INSERTAR_CICLO = """
INSERT INTO ciclo (
    dataset, cursor_entrada, cursor_salida, desde, hasta, estado, inicio, fin,
    paginas, vistos, insertados, duplicados, recuperados_por_solapamiento,
    en_borde_de_ventana, sin_fecha_de_hecho, huerfanos, causa, novedades,
    ventana_dias, desde_derivado
)
VALUES (
    %(dataset)s, %(cursor_entrada)s, %(cursor_salida)s, %(desde)s, %(hasta)s,
    %(estado)s, %(inicio)s, %(fin)s, %(paginas)s, %(vistos)s, %(insertados)s,
    %(duplicados)s, %(recuperados_por_solapamiento)s, %(en_borde_de_ventana)s,
    %(sin_fecha_de_hecho)s, %(huerfanos)s, %(causa)s, %(novedades)s,
    %(ventana_dias)s, %(desde_derivado)s
)
"""

# `GREATEST` impide que la marca retroceda: reprocesar un rango viejo no debe
# obligar a releer todo lo que ya se había leído después. `actualizada_en` sí se
# refresca siempre, incluso cuando la fecha no avanza: responde «¿cuándo se
# confirmó por última vez este dataset?», y congelarla haría creer que la
# ingesta está detenida.
_AVANZAR_MARCA = """
INSERT INTO ingesta_marca (dataset, fecha_hecho, actualizada_en)
VALUES (%s, %s, %s)
ON CONFLICT (dataset) DO UPDATE
SET fecha_hecho = GREATEST(ingesta_marca.fecha_hecho, EXCLUDED.fecha_hecho),
    actualizada_en = EXCLUDED.actualizada_en
"""


class RepositorioEstadoPostgres:
    """Marca de agua y registro de Ciclos, en la misma base que la capa cruda."""

    def __init__(self, conexion: psycopg.Connection) -> None:
        self._conexion = conexion

    def marca(self, dataset: str) -> MarcaDeAgua | None:
        try:
            # La lectura va en su propia transacción y la cierra. Sin esto, el
            # `SELECT` deja la conexión con una transacción implícita abierta
            # durante todo el Ciclo —horas, reteniendo el snapshot— y, peor,
            # el `transaction()` de `cerrar_ciclo` degradaría a SAVEPOINT y no
            # confirmaría nada hasta cerrar la conexión.
            with self._conexion.transaction(), self._conexion.cursor() as cursor:
                cursor.execute(_LEER_MARCA, (dataset,))
                fila = cursor.fetchone()
        except psycopg.Error as error:
            raise ErrorAlmacen(
                f"no se pudo leer la marca de agua de {dataset!r}: {error}"
            ) from error
        if fila is None:
            return None
        return MarcaDeAgua(dataset=fila[0], fecha_hecho=fila[1], actualizada_en=fila[2])

    def cerrar_ciclo(self, registro: RegistroDeCiclo) -> None:
        """Escribe el Ciclo y avanza la marca, o no hace ninguna de las dos.

        Van en la misma transacción a propósito: que la marca avance sin dejar
        registro rompe la trazabilidad que AD-4 exige.
        """
        try:
            with self._conexion.transaction(), self._conexion.cursor() as cursor:
                # Parámetros por nombre y no por posición: dieciocho valores
                # posicionales, casi todos enteros, se intercambian sin que
                # nada proteste y la señal de ventana corta acabaría en la
                # columna equivocada.
                cursor.execute(
                    _INSERTAR_CICLO,
                    {
                        "dataset": registro.dataset,
                        "cursor_entrada": registro.cursor_entrada,
                        "cursor_salida": registro.cursor_salida,
                        "desde": registro.desde,
                        "hasta": registro.hasta,
                        "estado": registro.estado,
                        "inicio": registro.inicio,
                        "fin": registro.fin,
                        "paginas": registro.paginas,
                        "vistos": registro.vistos,
                        "insertados": registro.insertados,
                        "duplicados": registro.duplicados,
                        "recuperados_por_solapamiento": (
                            registro.recuperados_por_solapamiento
                        ),
                        "en_borde_de_ventana": registro.en_borde_de_ventana,
                        "sin_fecha_de_hecho": registro.sin_fecha_de_hecho,
                        "huerfanos": registro.huerfanos,
                        "causa": registro.causa,
                        "novedades": list(registro.novedades),
                        "ventana_dias": registro.ventana_dias,
                        "desde_derivado": registro.desde_derivado,
                    },
                )
                if registro.completo and registro.cursor_salida is not None:
                    cursor.execute(
                        _AVANZAR_MARCA,
                        (registro.dataset, registro.cursor_salida, registro.fin),
                    )
        except psycopg.Error as error:
            raise ErrorAlmacen(
                f"no se pudo cerrar el Ciclo de {registro.dataset!r}: {error}"
            ) from error


@contextmanager
def repositorio_estado_postgres(dsn: str) -> Iterator[RepositorioEstadoPostgres]:
    try:
        conexion = psycopg.connect(dsn)
    except psycopg.Error as error:
        raise ErrorAlmacen(f"no se pudo conectar a la base de datos: {error}") from error
    with conexion:
        yield RepositorioEstadoPostgres(conexion)
