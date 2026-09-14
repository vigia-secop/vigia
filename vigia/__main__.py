"""Invocación por línea de comandos de un Ciclo de ingesta.

    # Primer Ciclo de un dataset: el rango se acota a mano.
    python -m vigia --dataset contratos --desde 2026-08-01 --hasta 2026-08-02

    # Ciclos siguientes: arranca de la marca de agua, menos la ventana.
    python -m vigia --dataset contratos
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from contextlib import ExitStack
from datetime import date

from vigia.crudo.memoria import RepositorioNulo
from vigia.tiempo import hoy_en_colombia
from vigia.crudo.modelo import ContenidoNoSerializable, RegistroSinIdentidad
from vigia.crudo.postgres import repositorio_postgres
from vigia.crudo.repositorio import ErrorAlmacen, RepositorioCrudo
from vigia.ingest.ciclo import RangoInvalido, ejecutar_ciclo
from vigia.ingest.estado import (
    RegistroDeCiclo,
    RepositorioEstado,
    RepositorioEstadoEnMemoria,
)
from vigia.ingest.estado_postgres import repositorio_estado_postgres
from vigia.ingest.datasets import DATASETS
from vigia.ingest.socrata import (
    DOMINIO_POR_DEFECTO,
    LIMITE_PAGINA_POR_DEFECTO,
    ClienteSocrata,
    ErrorFuente,
    crear_cliente_http,
)
from vigia.schema.definiciones import EsquemaEsperado, EsquemaEsperadoAusente
from vigia.schema.novedades import RepositorioNovedades, RepositorioNovedadesEnMemoria
from vigia.schema.postgres import repositorio_novedades_postgres
from vigia.schema.validacion import EsquemaCambiado, ValidadorDeEsquema

CODIGO_USO = 2
CODIGO_FALLO = 1

#: Días de solapamiento por defecto. El SECOP publica con retraso; treinta días
#: cubren el retraso observado con margen. Es configuración, no una constante
#: del dominio: la señal `en_borde_de_ventana` del Ciclo dice si se queda corta.
VENTANA_DIAS_POR_DEFECTO = 30




def _fecha(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"fecha inválida {texto!r}; se espera AAAA-MM-DD"
        ) from error


def _entero_no_negativo(texto: str) -> int:
    try:
        valor = int(texto)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"se esperaba un entero; se recibió {texto!r}"
        ) from error
    if valor < 0:
        raise argparse.ArgumentTypeError(f"no puede ser negativo; se recibió {valor}")
    return valor


def _entero_positivo(texto: str) -> int:
    try:
        valor = int(texto)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"se esperaba un entero; se recibió {texto!r}"
        ) from error
    if valor < 1:
        raise argparse.ArgumentTypeError(f"debe ser al menos 1; se recibió {valor}")
    return valor


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(
        prog="vigia",
        description="Ingesta de datasets del SECOP a la capa cruda.",
    )
    analizador.add_argument(
        "--dataset",
        required=True,
        choices=sorted(DATASETS),
        help="Dataset a ingerir.",
    )
    analizador.add_argument(
        "--desde",
        type=_fecha,
        default=None,
        help=(
            "Fecha inicial (AAAA-MM-DD). Si se omite, el Ciclo arranca de la marca de "
            "agua menos la ventana. El primer Ciclo de un dataset sí la exige."
        ),
    )
    analizador.add_argument(
        "--hasta",
        type=_fecha,
        default=None,
        help="Fecha final, incluida (AAAA-MM-DD). Por defecto, hoy en hora de Colombia.",
    )
    analizador.add_argument(
        "--ventana-dias",
        type=_entero_no_negativo,
        default=None,
        help=(
            "Días de solapamiento que se releen hacia atrás. Por defecto, "
            f"VIGIA_VENTANA_DIAS o {VENTANA_DIAS_POR_DEFECTO}."
        ),
    )
    analizador.add_argument(
        "--dry-run",
        action="store_true",
        help="Recorre la fuente sin escribir en la base de datos.",
    )
    analizador.add_argument(
        "--limite-pagina",
        type=_entero_positivo,
        default=None,
        help=(
            "Registros por página. Por defecto, VIGIA_LIMITE_PAGINA o "
            f"{LIMITE_PAGINA_POR_DEFECTO}."
        ),
    )
    return analizador


def _limite_pagina(opciones: argparse.Namespace, analizador: argparse.ArgumentParser) -> int:
    if opciones.limite_pagina is not None:
        return opciones.limite_pagina
    crudo = os.environ.get("VIGIA_LIMITE_PAGINA")
    if crudo is None:
        return LIMITE_PAGINA_POR_DEFECTO
    try:
        return _entero_positivo(crudo)
    except argparse.ArgumentTypeError as error:
        analizador.error(f"VIGIA_LIMITE_PAGINA inválido: {error}")


def _ventana_dias(opciones: argparse.Namespace, analizador: argparse.ArgumentParser) -> int:
    if opciones.ventana_dias is not None:
        return opciones.ventana_dias
    crudo = os.environ.get("VIGIA_VENTANA_DIAS")
    if crudo is None:
        return VENTANA_DIAS_POR_DEFECTO
    try:
        return _entero_no_negativo(crudo)
    except argparse.ArgumentTypeError as error:
        analizador.error(f"VIGIA_VENTANA_DIAS inválido: {error}")


def main(argv: list[str] | None = None) -> int:
    # El resumen lleva acentos y separadores tipográficos; una consola que no
    # sea UTF-8 no debe tumbar un Ciclo que ya terminó bien.
    for flujo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(flujo, "reconfigure", None)
        if reconfigurar is not None:
            reconfigurar(errors="replace")

    logging.basicConfig(
        level=os.environ.get("VIGIA_LOG", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    analizador = _analizador()
    opciones = analizador.parse_args(argv)
    dataset = DATASETS[opciones.dataset]
    limite_pagina = _limite_pagina(opciones, analizador)
    ventana_dias = _ventana_dias(opciones, analizador)
    hoy = hoy_en_colombia()
    hasta = opciones.hasta or hoy
    if hasta > hoy:
        # Un --hasta futuro fija la marca en el futuro, y como la marca nunca
        # retrocede el dataset queda atascado hasta esa fecha. Sin salida por
        # línea de comandos: habría que corregir `ingesta_marca` a mano.
        analizador.error(
            f"--hasta no puede ser futura: {hasta.isoformat()} es posterior a hoy "
            f"({hoy.isoformat()} en hora de Colombia)"
        )

    dsn = os.environ.get("VIGIA_DSN")
    if not opciones.dry_run and not dsn:
        print(
            "falta VIGIA_DSN: define la conexión a PostgreSQL o usa --dry-run.",
            file=sys.stderr,
        )
        return CODIGO_USO

    with ExitStack() as recursos:
        try:
            http = recursos.enter_context(
                crear_cliente_http(token=os.environ.get("VIGIA_TOKEN_SOCRATA"))
            )
            cliente = ClienteSocrata(
                http,
                dominio=os.environ.get("VIGIA_DOMINIO_SOCRATA", DOMINIO_POR_DEFECTO),
                limite_pagina=limite_pagina,
            )
        except ValueError as error:
            print(f"configuración inválida: {error}", file=sys.stderr)
            return CODIGO_USO

        try:
            esperado = EsquemaEsperado.para(dataset.nombre)
        except EsquemaEsperadoAusente as error:
            print(f"no se puede validar el esquema: {error}", file=sys.stderr)
            return CODIGO_USO

        repositorio: RepositorioCrudo
        novedades: RepositorioNovedades
        estado: RepositorioEstado
        if opciones.dry_run:
            repositorio = RepositorioNulo()
            novedades = RepositorioNovedadesEnMemoria()
            # En seco no hay marca persistida: el Ciclo exige --desde, y nada
            # de lo que descubra avanza ningún cursor.
            estado = RepositorioEstadoEnMemoria()
        else:
            try:
                repositorio = recursos.enter_context(repositorio_postgres(str(dsn)))
                novedades = recursos.enter_context(repositorio_novedades_postgres(str(dsn)))
                estado = recursos.enter_context(repositorio_estado_postgres(str(dsn)))
            except ErrorAlmacen as error:
                print(f"la ingesta no arrancó: {error}", file=sys.stderr)
                return CODIGO_FALLO

        try:
            ciclo = ejecutar_ciclo(
                cliente=cliente,
                repositorio=repositorio,
                estado=estado,
                dataset=dataset,
                desde=opciones.desde,
                hasta=hasta,
                ventana_dias=ventana_dias,
                validador=ValidadorDeEsquema(cliente, esperado, novedades),
            )
        except RangoInvalido as error:
            print(f"rango inválido: {error}", file=sys.stderr)
            return CODIGO_USO
        except EsquemaCambiado as error:
            print(f"la fuente cambió de forma: {error}", file=sys.stderr)
            return CODIGO_FALLO
        except (
            ErrorFuente,
            ErrorAlmacen,
            RegistroSinIdentidad,
            ContenidoNoSerializable,
        ) as error:
            # Antes del `except ValueError` de abajo: RegistroSinIdentidad y
            # ContenidoNoSerializable son ValueError, y son fallos de ingesta,
            # no de configuración.
            print(f"la ingesta se detuvo: {error}", file=sys.stderr)
            return CODIGO_FALLO
        except ValueError as error:
            # p. ej. un esquema esperado que no corresponde al dataset pedido.
            print(f"configuración inconsistente: {error}", file=sys.stderr)
            return CODIGO_USO

    if opciones.dry_run:
        print(
            f"[dry-run, nada se escribió] Ciclo dataset={ciclo.dataset} "
            f"rango={ciclo.desde.isoformat()}..{ciclo.hasta.isoformat()} "
            f"páginas={ciclo.paginas} vistos={ciclo.vistos} "
            "(no se comparó contra la base: cuántos serían nuevos solo lo sabe ella, "
            "y por eso en seco tampoco puede encenderse la alarma de ventana corta)"
        )
        if ciclo.novedades:
            print(
                f"Campos nuevos en la fuente ({len(ciclo.novedades)}): "
                f"{', '.join(ciclo.novedades)} — en dry-run no quedan registrados; "
                "corre sin --dry-run para que entren a esquema_novedad."
            )
    else:
        print(_describir(ciclo))
    return 0


def _describir(registro: RegistroDeCiclo) -> str:
    """El Ciclo, tal como el operador necesita verlo."""
    duracion = (registro.fin - registro.inicio).total_seconds()
    entrada = registro.cursor_entrada.isoformat() if registro.cursor_entrada else "—"
    salida = registro.cursor_salida.isoformat() if registro.cursor_salida else "—"
    lineas = [
        f"Ciclo {'vacío' if registro.vacio else 'con registros'} · "
        f"dataset={registro.dataset} "
        f"rango={registro.desde.isoformat()}..{registro.hasta.isoformat()} "
        f"marca={entrada}→{salida} "
        f"páginas={registro.paginas} vistos={registro.vistos} "
        f"insertados={registro.insertados} duplicados={registro.duplicados} "
        f"duración={duracion:.1f}s"
    ]
    if registro.ventana_corta:
        lineas.append(
            f"VENTANA CORTA: {registro.en_borde_de_ventana} registro(s) nuevo(s) con "
            f"fecha de hecho en {registro.desde.isoformat()}, el día más viejo de la "
            "ventana. Ensánchala con --ventana-dias antes de perder algo."
        )
    if registro.recuperados_por_solapamiento:
        lineas.append(
            f"Recuperados por el solapamiento: {registro.recuperados_por_solapamiento} "
            "(se habrían perdido sin ventana)."
        )
    if registro.sin_fecha_de_hecho:
        lineas.append(
            f"Sin fecha de hecho legible: {registro.sin_fecha_de_hecho} registro(s)."
        )
    if registro.novedades:
        lineas.append(
            f"Campos nuevos en la fuente, sin revisar ({len(registro.novedades)}): "
            f"{', '.join(registro.novedades)}"
        )
    return "\n".join(lineas)


if __name__ == "__main__":
    raise SystemExit(main())
