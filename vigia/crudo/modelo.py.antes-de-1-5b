"""Identidad y forma de un registro de la capa cruda."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from vigia.tiempo import a_utc as _a_utc

#: Campo de sistema de Socrata. Se pide con ``$select=:*,*`` y es la cláusula
#: de orden que la API exige para paginar sin saltos ni repeticiones.
#:
#: **No sirve como identidad.** La fuente se lo reasigna a la misma fila entre
#: publicaciones del dataset: medido el 2026-09-03, tres Ciclos sobre el rango
#: idéntico dejaron 50 434 filas crudas con 50 434 `:id` distintos para 25 749
#: contratos. Se conserva la constante porque el paginador sigue ordenando por
#: él, y porque el contenido guardado lo sigue trayendo.
CAMPO_ID_FUENTE = ":id"

#: Prefijo de los campos de sistema de Socrata: ``:id``, ``:created_at``,
#: ``:updated_at``, ``:version``. Es convención de la plataforma, no del SECOP.
#:
#: Se excluyen del hash porque cambian sin que cambie el dato: si entran en el
#: hash, cada republicación del dataset produce «una versión nueva» de todos
#: los registros. Medido sobre 300 contratos duplicados: 283 (94,3 %) diferían
#: SOLO en estos campos. Los otros 17 traían cambios de negocio reales
#: —`estado_contrato`, `fecha_de_inicio_del_contrato`— y esos sí tienen que
#: seguir produciendo una versión nueva.
PREFIJO_CAMPO_DE_PLATAFORMA = ":"


class RegistroSinIdentidad(ValueError):
    """La respuesta trajo un registro sin su identificador de negocio.

    No es un caso tolerable: sin identidad de fila no hay idempotencia, y
    guardar el registro de todos modos produciría duplicados silenciosos en
    cada Ciclo.
    """


class ContenidoNoSerializable(ValueError):
    """El contenido no se puede representar en JSON canónico.

    Ocurre con ``NaN`` e ``Infinity``, que el analizador de JSON de Python
    acepta pero que ni el estándar ni PostgreSQL admiten. Fallar aquí evita
    calcular un hash sobre algo que la base va a rechazar después, con la
    página entera ya perdida.
    """


def _canonizar(contenido: Mapping[str, Any]) -> str:
    """Serializa el contenido en la forma canónica sobre la que se hashea."""
    try:
        return json.dumps(
            # `dict(...)` acepta cualquier Mapping, incluido el MappingProxyType
            # que guarda RegistroCrudo: así el hash se puede recalcular sobre lo
            # ya almacenado y compararlo con el que se guardó.
            dict(contenido),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ContenidoNoSerializable(
            f"el contenido no es JSON válido: {error}"
        ) from error


def solo_negocio(contenido: Mapping[str, Any]) -> dict[str, Any]:
    """El contenido sin los campos de sistema de la plataforma."""
    return {
        clave: valor
        for clave, valor in contenido.items()
        if not str(clave).startswith(PREFIJO_CAMPO_DE_PLATAFORMA)
    }


def hash_contenido(contenido: Mapping[str, Any]) -> str:
    """SHA-256 del contenido **de negocio** serializado en JSON canónico.

    Dos decisiones, y las dos importan:

    - Se canoniza antes de hashear porque el orden de las claves de una
      respuesta HTTP no es estable entre peticiones. Así «el mismo contenido»
      significa lo mismo hoy y dentro de seis meses.
    - Se excluyen los campos de plataforma. Sin esto, la republicación del
      dataset —que les cambia `:updated_at` y `:version` a todas las filas—
      haría entrar la ventana entera como versiones nuevas en cada Ciclo.

    Lo que se GUARDA sigue siendo la fila completa, campos de plataforma
    incluidos: el trabajo de la capa cruda es conservar lo que llegó. Lo que
    cambia es sobre qué se calcula la identidad de la versión.
    """
    return hashlib.sha256(
        _canonizar(solo_negocio(contenido)).encode("utf-8")
    ).hexdigest()


def identidad_de_negocio(
    contenido: Mapping[str, Any], campos: tuple[str, ...]
) -> str | None:
    """Identidad de la fila a partir de sus campos de negocio, o `None`.

    El primer campo es obligatorio. Los siguientes se añaden si vienen
    poblados, separados por `|`, de modo que una fila que todavía no tiene el
    segundo componente —un proceso sin adjudicar— tenga identidad igualmente y
    la gane cuando lo tenga, sin cambiar la de las que ya la tienen.
    """
    partes: list[str] = []
    for indice, campo in enumerate(campos):
        valor = contenido.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            if indice == 0:
                return None
            break
        partes.append(valor.strip())
    return "|".join(partes)


@dataclass(frozen=True)
class RegistroCrudo:
    """Un registro de la fuente, listo para la capa cruda.

    La terna ``(dataset, id_fila_fuente, hash_contenido)`` es la identidad
    determinista: reingerir contenido idéntico no produce fila nueva, y un
    registro modificado en la fuente sí, sin tocar la versión anterior.

    Ambos componentes son **de negocio**, no de la plataforma: `id_fila_fuente`
    se compone de los campos que el dataset declara como identidad, y
    `hash_contenido` ignora los campos de sistema de Socrata. Ver
    `sprint-change-proposal-2026-09-04.md`.
    """

    dataset: str
    id_fila_fuente: str
    hash_contenido: str
    contenido: Mapping[str, Any]
    consultado_en: datetime

    @classmethod
    def desde_respuesta(
        cls,
        dataset: str,
        contenido: Mapping[str, Any],
        consultado_en: datetime,
        *,
        campos_identidad: tuple[str, ...],
    ) -> RegistroCrudo:
        """Construye el registro sin transformar el contenido.

        El contenido se conserva tal como lo devolvió la API: no se renombran
        campos, no se coercionan tipos, no se rellenan claves ausentes. Socrata
        omite por completo las claves nulas y esa ausencia es un dato, no un
        hueco que corresponda tapar aquí.

        La copia que se guarda es profunda: se reconstruye desde la cadena
        canónica, de modo que quien llamó pueda seguir mutando su diccionario
        sin afectar al registro.

        El hash NO cubre todo lo que se guarda: se calcula sobre el contenido
        de negocio, sin los campos de sistema de la plataforma. Es deliberado y
        está explicado en `hash_contenido`.
        """
        if not isinstance(contenido, Mapping):
            raise RegistroSinIdentidad(
                f"el dataset {dataset!r} devolvió un elemento que no es un objeto: "
                f"{type(contenido).__name__}"
            )

        if not campos_identidad:
            raise ValueError(
                f"no se declararon campos de identidad para el dataset {dataset!r}"
            )
        id_fila = identidad_de_negocio(contenido, campos_identidad)
        if id_fila is None:
            raise RegistroSinIdentidad(
                f"registro del dataset {dataset!r} sin {campos_identidad[0]!r} "
                f"utilizable; claves recibidas: {sorted(contenido)!r}"
            )

        # Se canoniza el contenido ENTERO —eso es lo que se guarda— y se
        # hashea solo la parte de negocio. Canonizar lo entero primero también
        # sirve de comprobación: si el contenido no es JSON válido, se falla
        # aquí y no a mitad de la escritura.
        canonico = _canonizar(contenido)
        return cls(
            dataset=dataset,
            id_fila_fuente=id_fila,
            hash_contenido=hash_contenido(contenido),
            contenido=MappingProxyType(json.loads(canonico)),
            consultado_en=_a_utc(consultado_en, "consultado_en"),
        )

    @property
    def llave(self) -> tuple[str, str, str]:
        """La identidad determinista, en el mismo orden que la llave primaria."""
        return (self.dataset, self.id_fila_fuente, self.hash_contenido)
