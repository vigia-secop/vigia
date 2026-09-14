"""Cliente de la API Socrata del SECOP.

Es la única frontera con la red del proyecto. Todo lo que está por encima
trabaja sobre páginas ya traídas, y por eso se puede probar sin salir a
internet.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Mapping, Sequence

import httpx

from vigia.crudo.modelo import CAMPO_ID_FUENTE
from vigia.ingest.datasets import DatasetSecop

registro_log = logging.getLogger(__name__)

DOMINIO_POR_DEFECTO = "https://www.datos.gov.co"
LIMITE_PAGINA_POR_DEFECTO = 1000

#: Códigos ante los que se reintenta. Todos dicen «ahora no puedo», no «lo que
#: pediste está mal»: reintentar una consulta mal formada solo la repite. El
#: 202 es la respuesta de Socrata a una consulta que todavía se está
#: ejecutando, y también se resuelve esperando.
#:
#: Medido el 2026-09-03 contra la fuente real: un 500 en la página 6 de 25 y un
#: 503 en la página 1 abortaron dos Ciclos consecutivos. Sin reintento, un
#: Ciclo diario desatendido falla la mayoría de los días.
CODIGOS_REINTENTABLES = frozenset({202, 408, 425, 429, 500, 502, 503, 504})

INTENTOS_POR_DEFECTO = 5
ESPERA_BASE_SEGUNDOS = 2.0

#: Tope de una espera individual. La fuente puede pedir por `Retry-After` que
#: se espere una hora; el Ciclo no puede quedarse colgado porque ella lo diga.
ESPERA_MAXIMA_SEGUNDOS = 60.0

#: Tope de `$limit` que acepta Socrata. Pedir más no da error: la fuente
#: recorta la página en silencio, y una página recortada parece una página
#: final. Rechazarlo aquí evita que el Ciclo se declare completo tras una sola
#: petición.
LIMITE_PAGINA_MAXIMO = 50_000

ESPERA_POR_DEFECTO = 60.0

#: Trae las columnas de sistema (`:id`, `:updated_at`, ...) además de las de datos.
_SELECT_COMPLETO = ":*,*"


class ErrorFuente(RuntimeError):
    """La fuente respondió algo que impide continuar el Ciclo.

    Aborta el recorrido. Las páginas ya confirmadas quedan guardadas y ninguna
    marca de agua avanza: el siguiente Ciclo reanuda desde donde iba.

    Solo se levanta cuando el fallo no es transitorio, o cuando ya se agotaron
    los reintentos: un tropiezo pasajero de la fuente no llega hasta aquí.
    """


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Pagina:
    """Una respuesta de la fuente, con el instante en que llegó."""

    offset: int
    consultado_en: datetime
    registros: tuple[Mapping[str, Any], ...]

    def __len__(self) -> int:
        return len(self.registros)


class ClienteSocrata:
    """Recorre un dataset de Socrata página por página."""

    def __init__(
        self,
        cliente_http: httpx.Client,
        *,
        dominio: str = DOMINIO_POR_DEFECTO,
        limite_pagina: int = LIMITE_PAGINA_POR_DEFECTO,
        reloj: Callable[[], datetime] = _ahora_utc,
        intentos: int = INTENTOS_POR_DEFECTO,
        dormir: Callable[[float], None] | None = None,
        azar: Callable[[], float] | None = None,
    ) -> None:
        if not dominio.startswith(("http://", "https://")):
            raise ValueError(
                f"el dominio debe incluir el esquema http:// o https://; se recibió {dominio!r}"
            )
        if not 1 <= limite_pagina <= LIMITE_PAGINA_MAXIMO:
            raise ValueError(
                f"limite_pagina debe estar entre 1 y {LIMITE_PAGINA_MAXIMO}; "
                f"se recibió {limite_pagina}"
            )
        if intentos < 1:
            raise ValueError(f"intentos debe ser al menos 1; se recibió {intentos}")
        self._http = cliente_http
        self._dominio = dominio.rstrip("/")
        self._limite_pagina = limite_pagina
        self._reloj = reloj
        self._intentos = intentos
        # Se resuelven aquí y no en la firma para que una prueba pueda
        # sustituirlos sin que ninguna espera real llegue a ocurrir.
        self._dormir = dormir if dormir is not None else time.sleep
        self._azar = azar if azar is not None else random.random

    @property
    def limite_pagina(self) -> int:
        return self._limite_pagina

    @property
    def intentos(self) -> int:
        return self._intentos

    def _espera_tras(self, intento: int, respuesta: httpx.Response | None) -> float:
        """Cuánto esperar antes del siguiente intento."""
        if respuesta is not None:
            pedida = respuesta.headers.get("Retry-After", "").strip()
            if pedida:
                try:
                    segundos = float(pedida)
                except ValueError:
                    # `Retry-After` admite también una fecha HTTP. No se
                    # interpreta: se cae a la espera calculada, que siempre
                    # existe. Obedecer a medias una cabecera es peor que
                    # ignorarla.
                    segundos = -1.0
                if segundos >= 0:
                    return min(segundos, ESPERA_MAXIMA_SEGUNDOS)

        techo = min(ESPERA_BASE_SEGUNDOS * (2 ** (intento - 1)), ESPERA_MAXIMA_SEGUNDOS)
        # Con dispersión: si varios Ciclos tropiezan a la vez, esperar todos lo
        # mismo los vuelve a estrellar juntos contra la fuente.
        return techo * (0.5 + 0.5 * self._azar())

    def _solicitar(
        self,
        url: str,
        *,
        parametros: Mapping[str, Any] | None = None,
        contexto: str,
    ) -> httpx.Response:
        """GET que reintenta los tropiezos pasajeros de la fuente.

        Un 500 a mitad de un recorrido de 25 páginas no es motivo para tirar el
        Ciclo entero: medido contra el SECOP real, pasa. Un 400 sí lo es, y por
        eso solo se reintentan los códigos de `CODIGOS_REINTENTABLES` y los
        fallos de red, nunca una respuesta que dice que la consulta está mal.
        """
        ultima_causa = "sin intentos"
        for intento in range(1, self._intentos + 1):
            respuesta: httpx.Response | None = None
            try:
                respuesta = self._http.get(url, params=parametros)
            except httpx.HTTPError as error:
                ultima_causa = f"fallo de red: {error}"
            else:
                if respuesta.status_code == httpx.codes.OK:
                    if intento > 1:
                        registro_log.info(
                            "la fuente respondió al intento %d · %s", intento, contexto
                        )
                    return respuesta
                ultima_causa = (
                    f"la fuente respondió {respuesta.status_code}: {respuesta.text[:500]}"
                )
                if respuesta.status_code not in CODIGOS_REINTENTABLES:
                    raise ErrorFuente(f"{ultima_causa} · {contexto}")

            if intento == self._intentos:
                break
            espera = self._espera_tras(intento, respuesta)
            registro_log.warning(
                "reintento %d de %d en %.1fs · %s · %s",
                intento + 1,
                self._intentos,
                espera,
                contexto,
                ultima_causa,
            )
            self._dormir(espera)

        raise ErrorFuente(
            f"la fuente no respondió tras {self._intentos} intentos · {contexto} · "
            f"{ultima_causa}"
        )

    def columnas(self, dataset: DatasetSecop) -> frozenset[str]:
        """Los campos que el dataset declara en sus metadatos.

        Es lo que hay que comparar contra el esquema esperado: las claves de un
        registro no sirven, porque Socrata omite las nulas por fila.
        """
        url = f"{self._dominio}/api/views/{dataset.id_socrata}.json"
        contexto = f"metadatos del dataset {dataset.nombre!r} ({dataset.id_socrata})"

        respuesta = self._solicitar(url, contexto=contexto)

        try:
            cuerpo = respuesta.json()
        except ValueError as error:
            raise ErrorFuente(
                f"la fuente respondió algo que no es JSON para los {contexto}: {error}"
            ) from error

        if not isinstance(cuerpo, Mapping) or not isinstance(cuerpo.get("columns"), list):
            raise ErrorFuente(f"los {contexto} no traen la lista `columns`")

        campos = {
            columna["fieldName"].strip()
            for columna in cuerpo["columns"]
            if isinstance(columna, Mapping)
            and isinstance(columna.get("fieldName"), str)
            and columna["fieldName"].strip()
            # Las columnas `:@computed_region_*` las añade la plataforma por su
            # cuenta al cruzar el dataset con capas geográficas. No son un
            # cambio del publicador y aparecerían como novedad permanente.
            and not columna["fieldName"].startswith(":@computed_region")
        }
        if not campos:
            raise ErrorFuente(f"los {contexto} no declaran ningún campo")
        return frozenset(campos)

    def paginas(self, dataset: DatasetSecop, *, filtro: str | None = None) -> Iterator[Pagina]:
        """Emite páginas hasta agotar el resultado.

        El recorrido pide siempre ``$order=:id``: Socrata documenta que sin
        cláusula de orden el resultado no tiene orden implícito, y paginar así
        salta y repite registros entre páginas. Termina cuando una respuesta
        trae menos elementos que el límite; con un total múltiplo exacto del
        límite eso implica una petición final vacía, que es el precio de no
        confiar en un conteo que la fuente no garantiza.
        """
        offset = 0
        while True:
            consultado_en = self._reloj()
            registros = self._pedir(dataset, filtro=filtro, offset=offset)
            yield Pagina(
                offset=offset,
                consultado_en=consultado_en,
                registros=tuple(registros),
            )
            if len(registros) < self._limite_pagina:
                return
            offset += self._limite_pagina

    def _pedir(
        self,
        dataset: DatasetSecop,
        *,
        filtro: str | None,
        offset: int,
    ) -> Sequence[Mapping[str, Any]]:
        url = f"{self._dominio}/resource/{dataset.id_socrata}.json"
        parametros: dict[str, Any] = {
            "$select": _SELECT_COMPLETO,
            "$order": CAMPO_ID_FUENTE,
            "$limit": self._limite_pagina,
            "$offset": offset,
        }
        if filtro:
            parametros["$where"] = filtro

        contexto = f"dataset {dataset.nombre!r} ({dataset.id_socrata}) en $offset={offset}"

        respuesta = self._solicitar(url, parametros=parametros, contexto=contexto)

        try:
            cuerpo = respuesta.json()
        except ValueError as error:
            raise ErrorFuente(
                f"la fuente respondió algo que no es JSON para el {contexto}: {error}"
            ) from error

        if not isinstance(cuerpo, list):
            raise ErrorFuente(
                f"se esperaba una lista de registros del {contexto}; "
                f"llegó {type(cuerpo).__name__}"
            )
        if not all(isinstance(elemento, Mapping) for elemento in cuerpo):
            raise ErrorFuente(
                f"la lista del {contexto} trae elementos que no son objetos JSON"
            )
        if len(cuerpo) > self._limite_pagina:
            # El avance del cursor es de un límite exacto: si la fuente devuelve
            # de más, la diferencia se saltaría sin dejar rastro.
            raise ErrorFuente(
                f"la fuente devolvió {len(cuerpo)} registros para el {contexto}, "
                f"más de los {self._limite_pagina} pedidos"
            )
        return cuerpo


def crear_cliente_http(
    *,
    token: str | None = None,
    espera: float = ESPERA_POR_DEFECTO,
) -> httpx.Client:
    """Cliente HTTP configurado para la fuente.

    El token de aplicación es opcional: sin él la API responde igual, pero con
    cuota compartida por dirección IP.

    No sigue redirecciones: httpx reenvía las cabeceras propias a través de un
    redirect a otro host, y `X-App-Token` es una credencial. Una redirección
    inesperada del dominio configurado debe verse como un error, no entregar el
    token a un tercero.
    """
    cabeceras = {"X-App-Token": token} if token else {}
    if espera <= 0:
        raise ValueError(f"espera debe ser positiva; se recibió {espera}")
    return httpx.Client(timeout=espera, headers=cabeceras, follow_redirects=False)
