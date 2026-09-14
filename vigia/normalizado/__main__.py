"""Normaliza la capa cruda y cruza Contratos con Procesos.

    python -m vigia.normalizado

Lee lo ya ingerido, no la fuente: no sale a la red. Se puede correr las veces
que se quiera y el resultado es el mismo, porque cada fila se reescribe entera
desde el crudo que la originó.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
import os
import sys

from vigia.crudo.repositorio import ErrorAlmacen
from vigia.normalizado.cruce import (
    cruzar_contratos,
    deduplicar_procesos,
    indexar_por_portafolio,
    resumir,
)
from vigia.normalizado.postgres import repositorio_normalizado_postgres
from vigia.normalizado.proveedor import IdentidadProveedor, Proveedor
from vigia.tiempo import ahora_utc

CODIGO_USO = 2
CODIGO_FALLO = 1

registro_log = logging.getLogger("vigia.normalizado")


def agrupar_desde_contratos(contratos) -> dict[str, Proveedor]:
    """Agrupa por identidad de proveedor sin releer la capa cruda.

    Los contratos ya normalizados traen su identidad y su razón social, así que
    agrupar es recorrerlos una vez. Los que no tienen identidad no entran —y se
    cuentan aparte en el resumen—, porque agruparlos por el centinela de la
    fuente crearía un proveedor falso enorme.

    Las identidades provisionales de Unión Temporal y Consorcio SÍ entran: cada
    una tiene el número de su propio contrato, así que aportan un proveedor con
    un contrato. Es justamente lo que se quiere: que se cuenten.
    """
    proveedores: dict[str, Proveedor] = {}
    for contrato in contratos:
        if contrato.proveedor_tipo is None or contrato.proveedor_numero is None:
            continue
        identidad = IdentidadProveedor(
            tipo=contrato.proveedor_tipo, numero=contrato.proveedor_numero
        )
        proveedor = proveedores.get(identidad.clave)
        if proveedor is None:
            proveedor = Proveedor(identidad=identidad)
            proveedores[identidad.clave] = proveedor
        proveedor.registrar(contrato.proveedor_nombre)
    return proveedores


@dataclass(frozen=True)
class Resultado:
    """Todo lo que produjo una normalización, para imprimirlo o afirmar sobre ello."""

    resumen: object
    proveedores: dict
    contratos: list
    procesos_sin_id: int
    contratos_sin_id: int


def ejecutar(dsn: str, *, momento=None) -> Resultado:
    """La tubería completa. La usan el comando y las pruebas, sin duplicarla."""
    momento = momento or ahora_utc()
    with repositorio_normalizado_postgres(dsn, momento=momento) as repositorio:
        # Procesos primero: sin el índice de portafolios no hay contra qué
        # cruzar, y todo contrato con llave saldría huérfano.
        procesos, procesos_leidos, procesos_sin_id = deduplicar_procesos(
            repositorio.ultimos_registros("procesos"), momento=momento
        )
        repositorio.guardar_procesos(procesos.values())
        indice = indexar_por_portafolio(procesos.values())

        contratos, contratos_leidos, contratos_sin_id = cruzar_contratos(
            repositorio.ultimos_registros("contratos"),
            indice_portafolio=indice,
            momento=momento,
        )

        # Los proveedores van ANTES que los contratos: la llave foránea de
        # `contrato.proveedor_*` los exige ya escritos.
        proveedores = agrupar_desde_contratos(contratos)
        repositorio.guardar_proveedores(proveedores.values())
        repositorio.guardar_contratos(contratos)

    resumen = resumir(
        contratos,
        procesos_leidos=procesos_leidos,
        procesos_normalizados=len(procesos),
        contratos_leidos=contratos_leidos,
        contratos_sin_identidad=contratos_sin_id,
    )
    return Resultado(
        resumen=resumen,
        proveedores=proveedores,
        contratos=contratos,
        procesos_sin_id=procesos_sin_id,
        contratos_sin_id=contratos_sin_id,
    )


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        prog="vigia.normalizado",
        description="Normaliza la capa cruda y cruza Contratos con Procesos.",
    )
    analizador.add_argument(
        "--dsn",
        default=os.environ.get("VIGIA_DSN"),
        help="Cadena de conexión. Por defecto, VIGIA_DSN del entorno.",
    )
    opciones = analizador.parse_args(argv)

    if not opciones.dsn:
        print(
            "falta la cadena de conexión: pásala con --dsn o en VIGIA_DSN",
            file=sys.stderr,
        )
        return CODIGO_USO

    logging.basicConfig(
        level=os.environ.get("VIGIA_LOG", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        resultado = ejecutar(opciones.dsn)
    except ErrorAlmacen as error:
        print(f"la normalización se detuvo: {error}", file=sys.stderr)
        return CODIGO_FALLO

    resumen = resultado.resumen
    proveedores = resultado.proveedores
    contratos = resultado.contratos
    procesos_sin_id = resultado.procesos_sin_id
    contratos_sin_id = resultado.contratos_sin_id

    print()
    print(f"Procesos   leídos {resumen.procesos_leidos}  ->  {resumen.procesos_normalizados} tras deduplicar")
    if resumen.procesos_colapsados:
        print(
            f"           {resumen.procesos_colapsados} filas colapsadas "
            "(el dataset trae una fila por adjudicación, no por Proceso)"
        )
    if procesos_sin_id:
        print(f"           {procesos_sin_id} descartados por no traer id_del_proceso")

    sin_proveedor = sum(1 for c in contratos if c.sin_proveedor)
    provisionales = sum(1 for c in contratos if c.proveedor_provisional)
    con_variantes = sum(
        1 for p in proveedores.values()
        if p.cuantas_variantes > 1 and not p.provisional
    )
    identidades_reales = sum(1 for p in proveedores.values() if not p.provisional)

    print(f"Contratos  {resumen.contratos_normalizados} normalizados")
    print(f"           {resumen.enlazados} enlazados a su Proceso")
    print(f"           {resumen.huerfanos} huérfanos (traen llave, no encontraron Proceso)")
    print(f"           {resumen.sin_llave_de_cruce} sin llave de cruce poblada")
    if contratos_sin_id:
        print(f"           {contratos_sin_id} descartados por no traer id_contrato")

    print()
    print(f"Proveedores {identidades_reales} identidades distintas")
    print(f"            {con_variantes} con el nombre escrito de más de una forma")

    valor_provisional = sum(
        c.valor for c in contratos if c.proveedor_provisional and c.valor is not None
    )
    print(
        f"            {provisionales} contratos de unión temporal o consorcio "
        "sin documento"
    )
    if provisionales:
        # Separador de miles con punto: es como se escribe la plata en Colombia,
        # y este número lo va a leer alguien que audita en Colombia.
        plata = f"{valor_provisional:,.0f}".replace(",", ".")
        print(
            f"            ${plata} es lo que mueven: se cuentan y se ven, pero "
            "cada uno es su propia identidad, así que no se les puede medir "
            "concentración"
        )
    print(
        f"            {sin_proveedor} contratos sin identidad ninguna "
        "(casi todos borradores y cancelados: nunca adjudicaron a nadie)"
    )
    if resumen.contratos_normalizados:
        fuera = sin_proveedor + provisionales
        print(
            f"            {100 * fuera / resumen.contratos_normalizados:.1f} % "
            "del total: es la parte que «concentración por proveedor» no podrá vigilar"
        )

    # ------------------------------------------------------ territorio (1.6)
    sin_territorio = sum(1 for c in contratos if c.sin_territorio)
    sin_orden = sum(1 for c in contratos if c.orden is None)
    por_orden: dict[str, int] = {}
    for c in contratos:
        if c.orden is not None:
            por_orden[c.orden] = por_orden.get(c.orden, 0) + 1
    departamentos = {c.departamento_codigo for c in contratos} - {None}

    print()
    print(f"Territorio  {len(departamentos)} departamentos con codigo DIVIPOLA")
    for nombre, cuantos in sorted(por_orden.items(), key=lambda p: -p[1]):
        print(f"            {cuantos} {nombre.lower()}")
    if sin_orden:
        print(
            f"            {sin_orden} sin orden declarado "
            "(no es «territorial»: es desconocido)"
        )
    if sin_territorio:
        print(
            f"            {sin_territorio} sin departamento: es la parte que "
            "ninguna Regla con corte territorial puede mirar"
        )

    print()
    if resumen.proporcion_huerfanos is None:
        print(
            "Porcentaje de huérfanos: no medible — ningún contrato traía llave "
            "de cruce. No es cero: es que no hay de qué hablar."
        )
    else:
        print(
            f"Porcentaje de huérfanos: {resumen.proporcion_huerfanos:.1%} "
            "(sobre los contratos que sí traen llave)"
        )
        if resumen.proporcion_huerfanos > 0.5 and resumen.procesos_normalizados == 0:
            print()
            print(
                "Casi todo salió huérfano y no hay ni un Proceso ingerido. "
                "Eso no es un problema del cruce: falta ingerir el dataset "
                "`procesos`, con `python -m vigia --dataset procesos`."
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
