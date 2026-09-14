"""Mide el hueco real de identidad de proveedor, contra la fuente.

Se escribió porque una nota mía en `deferred-work.md` afirmaba —sin medirlo—
que «casi todos» los 175 836 contratos con documento «No Definido» eran
Uniones Temporales y Consorcios. Este script existe para comprobar esa
afirmación, no para ilustrarla. Las consultas van sin filtrar por fecha:
miden el histórico nacional completo.

Solo lectura sobre una API pública. No escribe nada.

    python medir_uniones.py
"""

from __future__ import annotations

import json
import os
import sys

import httpx

RECURSO = "https://www.datos.gov.co/resource/jbjy-vk9h.json"

#: Estados en los que el registro NO es todavía un contrato del mundo real.
#: Un borrador no tiene proveedor porque aún no se ha adjudicado, y un
#: cancelado no lo tiene porque nunca llegó a adjudicarse. Contarlos como
#: «contratos sin identidad» infla el hueco con registros que no son contratos.
ESTADOS_NO_CONTRATO = ("Borrador", "Cancelado")

_SIN_ESTADO_MUERTO = " AND ".join(
    f"estado_contrato != '{estado}'" for estado in ESTADOS_NO_CONTRATO
)

CONSULTAS: dict[str, dict[str, str]] = {
    "1. universo por tipo de documento": {
        "$select": "tipodocproveedor, count(id_contrato) as n",
        "$group": "tipodocproveedor",
        "$order": "n desc",
    },
    "2. 'No Definido' por estado del contrato": {
        "$select": "estado_contrato, count(id_contrato) as n",
        "$where": "documento_proveedor = 'No Definido'",
        "$group": "estado_contrato",
        "$order": "n desc",
    },
    "3. 'No Definido': cuantos son grupo (UT/consorcio)": {
        "$select": "es_grupo, count(id_contrato) as n",
        "$where": "documento_proveedor = 'No Definido'",
        "$group": "es_grupo",
        "$order": "n desc",
    },
    "4. 'No Definido' YA CONTRATO: cuantos son grupo": {
        "$select": "es_grupo, count(id_contrato) as n",
        "$where": f"documento_proveedor = 'No Definido' AND {_SIN_ESTADO_MUERTO}",
        "$group": "es_grupo",
        "$order": "n desc",
    },
    "5. universo de grupos (es_grupo=Si) por tipo de documento": {
        "$select": "tipodocproveedor, count(id_contrato) as n",
        "$where": "es_grupo = 'Si'",
        "$group": "tipodocproveedor",
        "$order": "n desc",
    },
    "6. EL HUECO: grupo, sin documento, ya contrato": {
        "$select": (
            "count(id_contrato) as contratos, "
            "sum(valor_del_contrato) as valor, "
            "count(distinct proveedor_adjudicado) as nombres_distintos, "
            "count(distinct nit_entidad) as entidades"
        ),
        "$where": (
            f"es_grupo = 'Si' AND documento_proveedor = 'No Definido' "
            f"AND {_SIN_ESTADO_MUERTO}"
        ),
    },
    "7. el hueco: cuantos traen el nombre sin diligenciar": {
        "$select": "proveedor_adjudicado, count(id_contrato) as n",
        "$where": (
            f"es_grupo = 'Si' AND documento_proveedor = 'No Definido' "
            f"AND {_SIN_ESTADO_MUERTO}"
        ),
        "$group": "proveedor_adjudicado",
        "$order": "n desc",
        "$limit": "12",
    },
    "8. el hueco: los contratos mas grandes": {
        "$select": (
            "id_contrato, proveedor_adjudicado, nombre_entidad, "
            "valor_del_contrato, estado_contrato, proceso_de_compra"
        ),
        "$where": (
            f"es_grupo = 'Si' AND documento_proveedor = 'No Definido' "
            f"AND {_SIN_ESTADO_MUERTO}"
        ),
        "$order": "valor_del_contrato desc",
        "$limit": "8",
    },
    "9. grupos CON documento: sirve de referencia": {
        "$select": (
            "count(id_contrato) as contratos, sum(valor_del_contrato) as valor"
        ),
        "$where": (
            f"es_grupo = 'Si' AND documento_proveedor != 'No Definido' "
            f"AND {_SIN_ESTADO_MUERTO}"
        ),
    },
}


def _cabeceras() -> dict[str, str]:
    token = os.environ.get("VIGIA_TOKEN_SOCRATA")
    return {"X-App-Token": token} if token else {}


def main() -> int:
    with httpx.Client(timeout=120.0, headers=_cabeceras()) as cliente:
        for titulo, parametros in CONSULTAS.items():
            print(f"\n=== {titulo} ===", flush=True)
            try:
                respuesta = cliente.get(RECURSO, params=parametros)
                respuesta.raise_for_status()
            except httpx.HTTPError as error:
                print(f"  FALLO: {error}", flush=True)
                continue
            print(json.dumps(respuesta.json(), ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
