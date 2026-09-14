"""Dobles de la fuente. Ninguna prueba de esta suite sale a la red."""

from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

import httpx
import pytest

from vigia.crudo.modelo import CAMPO_ID_FUENTE
from vigia.ingest.socrata import ClienteSocrata
from vigia.schema.definiciones import EsquemaEsperado

#: El esquema capturado de Contratos, que sirve de base a los dobles.
CAMPOS_CONTRATOS = EsquemaEsperado.para("contratos").campos


@pytest.fixture(autouse=True)
def sin_esperas_reales(monkeypatch):
    """Ninguna prueba espera de verdad.

    El cliente reintenta con espera exponencial ante un fallo transitorio de la
    fuente. Una prueba que ejerza ese camino tardaría decenas de segundos y la
    suite dejaría de correrse. Se sustituye el reloj, no el reintento: lo que
    se prueba sigue siendo el comportamiento completo.

    `ClienteSocrata` resuelve `time.sleep` al construirse, no al definirse, y
    por eso este parche le llega.
    """
    monkeypatch.setattr(time, "sleep", lambda _segundos: None)


class FuenteFalsa:
    """Sirve una lista de registros paginada, como lo haría Socrata.

    Ordena por `:id` igual que lo haría la fuente ante `$order=:id`, y exige
    esa cláusula: sin ella Socrata no garantiza orden, así que un doble que
    respondiera igual con y sin `$order` no probaría nada sobre la paginación.

    **Aplica el `$where` de rango de verdad.** Un doble que lo ignorara dejaría
    pasar pruebas que alimentan registros fuera del rango declarado —algo que
    la fuente real nunca devolvería— y sobre esos datos imposibles se calculan
    las señales de ventana del Ciclo.

    Registra cada petición recibida para que las pruebas puedan afirmar sobre
    los parámetros de consulta.
    """

    #: `campo >= 'AAAA-MM-DDT..' AND campo < 'AAAA-MM-DDT..'`, que es la única
    #: forma de $where que produce `filtro_por_rango`.
    _RANGO = re.compile(
        r"(?P<campo>\w+) >= '(?P<inicio>[\d-]{10})T[^']*' AND "
        r"\w+ < '(?P<fin>[\d-]{10})T[^']*'"
    )

    def __init__(
        self,
        registros: Sequence[Mapping[str, Any]],
        *,
        fallos: Mapping[int, int] | None = None,
        fallos_pasajeros: Mapping[int, tuple[int, int]] | None = None,
        cabeceras_fallo: Mapping[str, str] | None = None,
        respuesta_cruda: Callable[[int], httpx.Response] | None = None,
        columnas: Iterable[str] | None = None,
        fallo_metadatos: int | None = None,
    ) -> None:
        """`fallos` mapea un `$offset` al código de estado con el que responder.

        `fallos_pasajeros` mapea un `$offset` a `(codigo, veces)`: falla esas
        veces y después responde bien. Es como se ve de verdad un tropiezo de
        la fuente, y es lo único que distingue un reintento que sirve de uno
        que solo repite el mismo error hasta agotarse.
        """
        self._registros = list(registros)
        self._fallos = dict(fallos or {})
        self._pasajeros = dict(fallos_pasajeros or {})
        self._cabeceras_fallo = dict(cabeceras_fallo or {})
        self._respuesta_cruda = respuesta_cruda
        # Por defecto declara el esquema esperado de Contratos, para que las
        # pruebas que no van sobre validación no tengan que ocuparse de ella.
        self._columnas = (
            sorted(columnas) if columnas is not None else sorted(CAMPOS_CONTRATOS)
        )
        self._fallo_metadatos = fallo_metadatos
        self.peticiones: list[httpx.Request] = []
        self.peticiones_metadatos: list[httpx.Request] = []

    @property
    def offsets(self) -> list[int]:
        return [int(peticion.url.params["$offset"]) for peticion in self.peticiones]

    @property
    def limites(self) -> list[int]:
        return [int(peticion.url.params["$limit"]) for peticion in self.peticiones]

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        if peticion.url.path.startswith("/api/views/"):
            self.peticiones_metadatos.append(peticion)
            if self._fallo_metadatos is not None:
                return httpx.Response(self._fallo_metadatos, text="metadatos no disponibles")
            return httpx.Response(
                200,
                json={"columns": [{"fieldName": campo} for campo in self._columnas]},
            )

        self.peticiones.append(peticion)
        parametros = peticion.url.params
        if parametros.get("$order") != CAMPO_ID_FUENTE:
            raise AssertionError(
                "la petición llegó sin $order=:id; sin orden, paginar salta y repite filas"
            )

        offset = int(parametros["$offset"])
        limite = int(parametros["$limit"])

        if offset in self._pasajeros:
            codigo, restantes = self._pasajeros[offset]
            if restantes > 0:
                self._pasajeros[offset] = (codigo, restantes - 1)
                return httpx.Response(
                    codigo, text="tropiezo pasajero", headers=self._cabeceras_fallo
                )
        if offset in self._fallos:
            return httpx.Response(
                self._fallos[offset], text="la fuente falló", headers=self._cabeceras_fallo
            )
        if self._respuesta_cruda is not None:
            return self._respuesta_cruda(offset)

        candidatos = self._filtrar(parametros.get("$where"))
        ordenados = sorted(candidatos, key=lambda fila: fila[CAMPO_ID_FUENTE])
        return httpx.Response(200, json=ordenados[offset : offset + limite])

    def _filtrar(self, filtro: str | None) -> list[Mapping[str, Any]]:
        if not filtro:
            return list(self._registros)
        coincidencia = self._RANGO.search(filtro)
        if coincidencia is None:
            raise AssertionError(f"$where con una forma que el doble no sabe aplicar: {filtro}")

        campo = coincidencia.group("campo")
        inicio = date.fromisoformat(coincidencia.group("inicio"))
        fin = coincidencia.group("fin")
        fin = date.fromisoformat(fin)

        def dentro(fila: Mapping[str, Any]) -> bool:
            valor = fila.get(campo)
            if not isinstance(valor, str):
                # Socrata descarta los nulos en una comparación de rango: una
                # fila sin el campo simplemente no vuelve.
                return False
            try:
                fecha = date.fromisoformat(valor[:10])
            except ValueError:
                return False
            return inicio <= fecha < fin

        return [fila for fila in self._registros if dentro(fila)]


#: Fecha de firma por defecto de los registros de prueba. Cae dentro del rango
#: que usan casi todas las pruebas. Sin ella, la FuenteFalsa —que ahora sí
#: aplica el $where— no devolvería nada, igual que la fuente real.
FECHA_DE_FIRMA_POR_DEFECTO = "2026-08-01T00:00:00.000"


def registro(id_fila: str, **campos: Any) -> dict[str, Any]:
    """Un registro como los que devuelve Socrata, con su campo de sistema.

    Trae `fecha_de_firma` salvo que la prueba diga otra cosa: la fuente real
    nunca devuelve un contrato sin ella en una consulta por rango, porque la
    consulta filtra justamente sobre ese campo.

    Trae también `id_contrato`, que desde la propuesta de cambio del
    2026-09-04 es la identidad de negocio de la capa cruda. `:id` sigue
    presente porque la fuente lo manda y la capa cruda lo guarda; lo que ya no
    hace es identificar la fila. Una prueba que quiera un registro SIN
    identidad pasa `id_contrato=None` explícitamente.
    """
    campos.setdefault("fecha_de_firma", FECHA_DE_FIRMA_POR_DEFECTO)
    campos.setdefault("id_contrato", id_fila)
    if campos.get("id_contrato") is None:
        campos.pop("id_contrato")
    return {CAMPO_ID_FUENTE: id_fila, **campos}


@pytest.fixture
def crear_cliente() -> Iterator[Callable[..., tuple[ClienteSocrata, FuenteFalsa]]]:
    """Fabrica un ClienteSocrata apuntado a una FuenteFalsa."""
    clientes_http: list[httpx.Client] = []

    def fabricar(
        registros: Sequence[Mapping[str, Any]],
        *,
        limite_pagina: int = 1000,
        fallos: Mapping[int, int] | None = None,
        fallos_pasajeros: Mapping[int, tuple[int, int]] | None = None,
        cabeceras_fallo: Mapping[str, str] | None = None,
        respuesta_cruda: Callable[[int], httpx.Response] | None = None,
        columnas: Iterable[str] | None = None,
        fallo_metadatos: int | None = None,
        reloj: Callable[[], datetime] | None = None,
        intentos: int = 5,
        esperas: list[float] | None = None,
        transporte: httpx.BaseTransport | None = None,
    ) -> tuple[ClienteSocrata, FuenteFalsa]:
        fuente = FuenteFalsa(
            registros,
            fallos=fallos,
            fallos_pasajeros=fallos_pasajeros,
            cabeceras_fallo=cabeceras_fallo,
            respuesta_cruda=respuesta_cruda,
            columnas=columnas,
            fallo_metadatos=fallo_metadatos,
        )
        http = httpx.Client(transport=transporte or httpx.MockTransport(fuente))
        clientes_http.append(http)
        cliente = ClienteSocrata(
            http,
            dominio="https://fuente.falsa",
            limite_pagina=limite_pagina,
            reloj=reloj or reloj_fijo(),
            intentos=intentos,
            # Las esperas se anotan en vez de dormirse, y el azar se fija: una
            # prueba de reintentos no puede tardar ni salir distinta cada vez.
            dormir=(esperas.append if esperas is not None else (lambda _s: None)),
            azar=lambda: 1.0,
        )
        return cliente, fuente

    yield fabricar

    for http in clientes_http:
        http.close()


def reloj_fijo(
    inicio: datetime | None = None,
    paso: timedelta = timedelta(seconds=1),
) -> Callable[[], datetime]:
    """Reloj determinista que avanza un paso en cada lectura."""
    momento = inicio or datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)
    estado = {"ahora": momento}

    def leer() -> datetime:
        actual = estado["ahora"]
        estado["ahora"] = actual + paso
        return actual

    return leer
