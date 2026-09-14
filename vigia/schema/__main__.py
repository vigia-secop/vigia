"""Captura el esquema declarado de un dataset a su archivo versionado.

    python -m vigia.schema --capturar --dataset contratos

Lo que escribe se revisa y se versiona. No hay captura automática dentro del
Ciclo: autoactualizar el esperado con lo que la fuente devuelva convertiría la
alarma en un sello de goma.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from vigia.ingest.datasets import DATASETS
from vigia.ingest.socrata import (
    DOMINIO_POR_DEFECTO,
    ClienteSocrata,
    ErrorFuente,
    crear_cliente_http,
)
from vigia.schema.definiciones import (
    DIRECTORIO_ESPERADO,
    EsquemaEsperado,
    EsquemaEsperadoAusente,
)
from vigia.tiempo import hoy_en_colombia

CODIGO_USO = 2
CODIGO_FALLO = 1


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        prog="vigia.schema",
        description="Captura el esquema declarado de un dataset del SECOP.",
    )
    analizador.add_argument(
        "--capturar",
        action="store_true",
        required=True,
        help="Escribe el esquema declarado al archivo versionado del dataset.",
    )
    analizador.add_argument(
        "--dataset",
        required=True,
        choices=sorted(DATASETS),
        help="Dataset cuyo esquema se captura.",
    )
    analizador.add_argument(
        "--directorio",
        type=Path,
        default=DIRECTORIO_ESPERADO,
        help="Dónde escribir el archivo. Por defecto, el del paquete.",
    )
    opciones = analizador.parse_args(argv)
    dataset = DATASETS[opciones.dataset]

    dominio = os.environ.get("VIGIA_DOMINIO_SOCRATA", DOMINIO_POR_DEFECTO).rstrip("/")
    try:
        with crear_cliente_http(token=os.environ.get("VIGIA_TOKEN_SOCRATA")) as http:
            cliente = ClienteSocrata(http, dominio=dominio)
            campos = cliente.columnas(dataset)
    except ErrorFuente as error:
        print(f"no se pudo capturar el esquema: {error}", file=sys.stderr)
        return CODIGO_FALLO
    except ValueError as error:
        print(f"configuración inválida: {error}", file=sys.stderr)
        return CODIGO_USO

    esquema = EsquemaEsperado(
        dataset=dataset.nombre,
        id_socrata=dataset.id_socrata,
        # Hora de Colombia, no UTC. `capturado_en` es una FECHA que una persona
        # lee en un `diff`, no un instante: sellarla en UTC hace que una captura
        # hecha a las 8 de la noche aparezca fechada al día siguiente.
        capturado_en=hoy_en_colombia(),
        procedencia=f"{dominio}/api/views/{dataset.id_socrata}.json",
        campos=campos,
    )

    anterior: EsquemaEsperado | None
    try:
        anterior = EsquemaEsperado.para(dataset.nombre, opciones.directorio)
    except EsquemaEsperadoAusente:
        anterior = None

    try:
        ruta = esquema.escribir(opciones.directorio)
    except OSError as error:
        print(f"no se pudo escribir el esquema: {error}", file=sys.stderr)
        return CODIGO_FALLO

    print(f"esquema de {dataset.nombre} capturado: {len(campos)} campos en {ruta}.")
    if anterior is None:
        print("Es la primera captura de este dataset.")
    else:
        entran, salen = anterior.diferencia(esquema)
        if not entran and not salen:
            print("Sin cambios frente a la captura anterior.")
        else:
            if entran:
                print(f"  entran ({len(entran)}): {', '.join(entran)}")
            if salen:
                # Recapturar un campo que desapareció es exactamente cómo se
                # apaga esta alarma sin querer.
                print(f"  SALEN ({len(salen)}): {', '.join(salen)}")
                print(
                    "  Un campo que sale es un cambio de la fuente, no un detalle: "
                    "entiende qué se rompe aguas abajo antes de versionar esto."
                )
    print("Revisa el `diff` y versiónalo antes de confiar en él.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
