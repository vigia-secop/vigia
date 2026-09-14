"""Recorrido de páginas contra la fuente."""

from __future__ import annotations

from datetime import timezone

import httpx
import pytest

from tests.conftest import registro
from vigia.ingest.datasets import CONTRATOS
from vigia.ingest.socrata import (
    ESPERA_MAXIMA_SEGUNDOS,
    ClienteSocrata,
    ErrorFuente,
)


def test_toda_peticion_pide_orden_por_id_de_sistema(crear_cliente):
    # Socrata no garantiza orden implícito: paginar sin $order salta y repite
    # registros entre páginas.
    cliente, fuente = crear_cliente([registro("row-1")])

    list(cliente.paginas(CONTRATOS))

    parametros = fuente.peticiones[0].url.params
    assert parametros["$order"] == ":id"
    assert parametros["$select"] == ":*,*"


def test_el_filtro_viaja_como_where(crear_cliente):
    cliente, fuente = crear_cliente([])

    filtro = (
        "fecha_de_firma >= '2026-08-01T00:00:00.000' "
        "AND fecha_de_firma < '2026-08-03T00:00:00.000'"
    )

    list(cliente.paginas(CONTRATOS, filtro=filtro))

    assert fuente.peticiones[0].url.params["$where"] == filtro


def test_sin_filtro_no_se_manda_where(crear_cliente):
    cliente, fuente = crear_cliente([])

    list(cliente.paginas(CONTRATOS))

    assert "$where" not in fuente.peticiones[0].url.params


def test_recorre_todas_las_paginas_cuando_el_resultado_supera_el_limite(crear_cliente):
    registros = [registro(f"row-{indice:04d}") for indice in range(2500)]
    cliente, fuente = crear_cliente(registros, limite_pagina=1000)

    paginas = list(cliente.paginas(CONTRATOS))

    assert fuente.offsets == [0, 1000, 2000]
    assert [len(pagina) for pagina in paginas] == [1000, 1000, 500]
    assert sum(len(pagina) for pagina in paginas) == 2500


def test_un_total_multiplo_del_limite_cierra_con_una_pagina_vacia(crear_cliente):
    registros = [registro(f"row-{indice:04d}") for indice in range(2000)]
    cliente, fuente = crear_cliente(registros, limite_pagina=1000)

    paginas = list(cliente.paginas(CONTRATOS))

    assert fuente.offsets == [0, 1000, 2000]
    assert len(paginas[-1]) == 0


def test_un_resultado_vacio_produce_una_sola_pagina_vacia(crear_cliente):
    cliente, fuente = crear_cliente([])

    paginas = list(cliente.paginas(CONTRATOS))

    assert fuente.offsets == [0]
    assert [len(pagina) for pagina in paginas] == [0]


def test_cada_pagina_lleva_su_propia_fecha_de_consulta(crear_cliente):
    registros = [registro(f"row-{indice}") for indice in range(3)]
    cliente, _ = crear_cliente(registros, limite_pagina=2)

    paginas = list(cliente.paginas(CONTRATOS))

    momentos = [pagina.consultado_en for pagina in paginas]
    assert momentos == sorted(momentos)
    assert len(set(momentos)) == len(momentos)
    assert all(momento.tzinfo == timezone.utc for momento in momentos)


def test_un_error_http_persistente_aborta_tras_agotar_los_intentos(crear_cliente):
    registros = [registro(f"row-{indice}") for indice in range(4)]
    cliente, fuente = crear_cliente(registros, limite_pagina=2, fallos={2: 500}, intentos=3)

    with pytest.raises(ErrorFuente) as fallo:
        list(cliente.paginas(CONTRATOS))

    mensaje = str(fallo.value)
    assert "500" in mensaje
    assert "3 intentos" in mensaje
    assert "contratos" in mensaje
    assert CONTRATOS.id_socrata in mensaje
    assert "$offset=2" in mensaje
    # La primera página sí llegó a pedirse: lo ya confirmado no se pierde.
    # La segunda se pidió tres veces, una por intento, y ninguna más.
    assert fuente.offsets == [0, 2, 2, 2]


def test_un_tropiezo_pasajero_se_reintenta_y_el_recorrido_termina(crear_cliente):
    # Es la razón de ser del reintento: medido contra el SECOP real el
    # 2026-09-03, un 500 en la página 6 de 25 abortaba el Ciclo entero.
    registros = [registro(f"row-{indice}") for indice in range(4)]
    esperas: list[float] = []
    cliente, fuente = crear_cliente(
        registros, limite_pagina=2, fallos_pasajeros={2: (500, 2)}, esperas=esperas
    )

    paginas = list(cliente.paginas(CONTRATOS))

    assert [len(pagina) for pagina in paginas] == [2, 2, 0]
    assert fuente.offsets == [0, 2, 2, 2, 4]
    # Espera creciente: dos reintentos, el segundo espera el doble que el
    # primero. Sin crecimiento, insistir sobre una fuente saturada la hunde más.
    assert esperas == [2.0, 4.0]


def test_un_error_que_no_es_pasajero_no_se_reintenta(crear_cliente):
    # Un 400 dice que la consulta está mal formada. Repetirla la repite mal:
    # reintentar solo gasta tiempo y cuota, y esconde el error real.
    registros = [registro("row-0")]
    esperas: list[float] = []
    cliente, fuente = crear_cliente(
        registros, limite_pagina=2, fallos={0: 400}, esperas=esperas
    )

    with pytest.raises(ErrorFuente) as fallo:
        list(cliente.paginas(CONTRATOS))

    assert "400" in str(fallo.value)
    assert fuente.offsets == [0]
    assert esperas == []


def test_se_obedece_retry_after_pero_con_tope(crear_cliente):
    registros = [registro(f"row-{indice}") for indice in range(2)]
    esperas: list[float] = []
    cliente, _ = crear_cliente(
        registros,
        limite_pagina=2,
        fallos_pasajeros={0: (429, 1)},
        cabeceras_fallo={"Retry-After": "7"},
        esperas=esperas,
    )

    list(cliente.paginas(CONTRATOS))

    assert esperas == [7.0]


def test_retry_after_desmedido_se_recorta_al_tope(crear_cliente):
    # La fuente puede pedir que se espere una hora. El Ciclo no puede quedarse
    # colgado porque ella lo diga.
    registros = [registro(f"row-{indice}") for indice in range(2)]
    esperas: list[float] = []
    cliente, _ = crear_cliente(
        registros,
        limite_pagina=2,
        fallos_pasajeros={0: (503, 1)},
        cabeceras_fallo={"Retry-After": "3600"},
        esperas=esperas,
    )

    list(cliente.paginas(CONTRATOS))

    assert esperas == [ESPERA_MAXIMA_SEGUNDOS]


def test_un_retry_after_ilegible_cae_en_la_espera_calculada(crear_cliente):
    # `Retry-After` admite una fecha HTTP. No se interpreta: obedecer a medias
    # una cabecera es peor que ignorarla, y la espera calculada siempre existe.
    registros = [registro(f"row-{indice}") for indice in range(2)]
    esperas: list[float] = []
    cliente, _ = crear_cliente(
        registros,
        limite_pagina=2,
        fallos_pasajeros={0: (503, 1)},
        cabeceras_fallo={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"},
        esperas=esperas,
    )

    list(cliente.paginas(CONTRATOS))

    assert esperas == [2.0]


def test_un_fallo_de_red_tambien_se_reintenta(crear_cliente):
    # El caso que motivó todo esto es de red tanto como de servidor: un hipo
    # del enlace no debería costar un Ciclo.
    intentos_hechos = {"n": 0}

    def transporte_inestable(_peticion: httpx.Request) -> httpx.Response:
        intentos_hechos["n"] += 1
        if intentos_hechos["n"] == 1:
            raise httpx.ConnectError("se cayó el enlace")
        return httpx.Response(200, json=[])

    esperas: list[float] = []
    cliente, _ = crear_cliente(
        [],
        limite_pagina=2,
        transporte=httpx.MockTransport(transporte_inestable),
        esperas=esperas,
    )

    paginas = list(cliente.paginas(CONTRATOS))

    assert [len(pagina) for pagina in paginas] == [0]
    assert intentos_hechos["n"] == 2
    assert esperas == [2.0]


def test_los_metadatos_tambien_se_reintentan(crear_cliente):
    # La validación de esquema abre el Ciclo. Si un 503 ahí lo aborta, el
    # reintento de las páginas no sirve de nada.
    cliente, _ = crear_cliente([], fallos_pasajeros={}, columnas={"alfa", "beta"})
    assert cliente.columnas(CONTRATOS) == frozenset({"alfa", "beta"})


def test_intentos_debe_ser_al_menos_uno(crear_cliente):
    with pytest.raises(ValueError, match="intentos"):
        crear_cliente([], intentos=0)


def test_una_respuesta_que_no_es_lista_aborta(crear_cliente, monkeypatch):
    import httpx

    def responder(_peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "algo pasó"})

    http = httpx.Client(transport=httpx.MockTransport(responder))
    cliente = ClienteSocrata(http, dominio="https://fuente.falsa", limite_pagina=10)

    with pytest.raises(ErrorFuente, match="se esperaba una lista"):
        list(cliente.paginas(CONTRATOS))

    http.close()


def test_un_limite_de_pagina_invalido_se_rechaza_al_construir():
    import httpx

    http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[])))
    with pytest.raises(ValueError, match="limite_pagina"):
        ClienteSocrata(http, limite_pagina=0)
    http.close()


def test_un_limite_por_encima_del_tope_de_socrata_se_rechaza():
    # Socrata recorta el $limit en silencio; una página recortada parece la
    # última y el Ciclo se declararía completo tras una sola petición.
    import httpx

    from vigia.ingest.socrata import LIMITE_PAGINA_MAXIMO

    http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[])))
    with pytest.raises(ValueError, match="limite_pagina"):
        ClienteSocrata(http, limite_pagina=LIMITE_PAGINA_MAXIMO + 1)
    http.close()


def test_una_pagina_mas_larga_que_el_limite_aborta(crear_cliente):
    # El cursor avanza un límite exacto: los registros de más se saltarían.
    import httpx

    cliente, _ = crear_cliente(
        [],
        limite_pagina=2,
        respuesta_cruda=lambda _offset: httpx.Response(
            200, json=[{":id": f"row-{indice}"} for indice in range(5)]
        ),
    )

    with pytest.raises(ErrorFuente, match="más de los 2 pedidos"):
        list(cliente.paginas(CONTRATOS))


def test_una_lista_con_elementos_que_no_son_objetos_aborta(crear_cliente):
    import httpx

    cliente, _ = crear_cliente(
        [],
        respuesta_cruda=lambda _offset: httpx.Response(200, json=[1, 2, 3]),
    )

    with pytest.raises(ErrorFuente, match="no son objetos"):
        list(cliente.paginas(CONTRATOS))


def test_un_fallo_de_red_se_traduce_a_error_de_fuente():
    import httpx

    def caer(_peticion: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("la conexión se cayó")

    http = httpx.Client(transport=httpx.MockTransport(caer))
    cliente = ClienteSocrata(http, dominio="https://fuente.falsa")

    with pytest.raises(ErrorFuente, match="fallo de red"):
        list(cliente.paginas(CONTRATOS))

    http.close()


def test_un_dominio_sin_esquema_se_rechaza():
    import httpx

    http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[])))
    with pytest.raises(ValueError, match="esquema"):
        ClienteSocrata(http, dominio="datos.gov.co")
    http.close()
