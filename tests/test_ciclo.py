"""El Ciclo de ingesta de punta a punta, con la fuente sustituida."""

from __future__ import annotations

from datetime import date, timezone

import pytest

from tests.conftest import registro
from vigia.crudo.memoria import RepositorioEnMemoria
from vigia.ingest.ciclo import RangoInvalido, filtro_por_rango, ingerir
from vigia.ingest.datasets import CONTRATOS, PROCESOS

DESDE = date(2026, 8, 1)
HASTA = date(2026, 8, 2)

CONTRATO = registro(
    "row-eah6~gu28.rnh4",
    id_contrato="CO1.PCCNTR.4168447",
    valor_del_contrato="8959088",
    urlproceso={"url": "https://community.secop.gov.co/x"},
    departamento="Quindío",
)


def _ingerir(cliente, repositorio, dataset=CONTRATOS, desde=DESDE, hasta=HASTA):
    return ingerir(
        cliente=cliente,
        repositorio=repositorio,
        dataset=dataset,
        desde=desde,
        hasta=hasta,
    )


def test_cada_registro_queda_crudo_con_su_fecha_de_consulta(crear_cliente):
    registros = [registro(f"row-{indice}", valor=str(indice)) for indice in range(3)]
    cliente, _ = crear_cliente(registros)
    repositorio = RepositorioEnMemoria()

    resumen = _ingerir(cliente, repositorio)

    assert resumen.vistos == 3
    assert resumen.insertados == 3
    assert len(repositorio) == 3
    for guardado, original in zip(repositorio.registros, registros):
        assert dict(guardado.contenido) == original
        assert guardado.consultado_en.tzinfo == timezone.utc
        assert guardado.dataset == "contratos"


def test_el_contenido_guardado_es_identico_al_que_devolvio_la_fuente(crear_cliente):
    cliente, _ = crear_cliente([CONTRATO])
    repositorio = RepositorioEnMemoria()

    _ingerir(cliente, repositorio)

    assert dict(repositorio.registros[0].contenido) == CONTRATO


def test_una_clave_ausente_en_la_fuente_no_se_inventa(crear_cliente):
    # Socrata omite las claves nulas: el registro llega sin `ultima_actualizacion`.
    cliente, _ = crear_cliente([CONTRATO])
    repositorio = RepositorioEnMemoria()

    _ingerir(cliente, repositorio)

    guardado = repositorio.registros[0].contenido
    assert "ultima_actualizacion" not in guardado


def test_reingerir_sin_cambios_no_duplica(crear_cliente):
    registros = [registro(f"row-{indice}") for indice in range(3)]
    repositorio = RepositorioEnMemoria()

    cliente_uno, _ = crear_cliente(registros)
    _ingerir(cliente_uno, repositorio)

    cliente_dos, _ = crear_cliente(registros)
    segundo = _ingerir(cliente_dos, repositorio)

    assert segundo.vistos == 3
    assert segundo.insertados == 0
    assert segundo.duplicados == 3
    assert len(repositorio) == 3


def test_un_registro_modificado_en_la_fuente_entra_como_fila_nueva(crear_cliente):
    repositorio = RepositorioEnMemoria()

    cliente_uno, _ = crear_cliente([registro("row-1", estado="En ejecución")])
    _ingerir(cliente_uno, repositorio)

    cliente_dos, _ = crear_cliente([registro("row-1", estado="Terminado")])
    segundo = _ingerir(cliente_dos, repositorio)

    assert segundo.insertados == 1
    assert len(repositorio) == 2
    estados = {guardado.contenido["estado"] for guardado in repositorio.registros}
    assert estados == {"En ejecución", "Terminado"}


def test_un_registro_repetido_dentro_de_la_misma_pagina_se_cuenta_una_vez(crear_cliente):
    repetido = registro("row-1", valor="1")
    cliente, _ = crear_cliente([repetido, repetido])
    repositorio = RepositorioEnMemoria()

    resumen = _ingerir(cliente, repositorio)

    assert resumen.vistos == 2
    assert resumen.insertados == 1
    assert resumen.duplicados == 1
    assert len(repositorio) == 1


def test_un_resultado_mayor_que_la_pagina_se_recorre_completo(crear_cliente):
    registros = [registro(f"row-{indice:04d}") for indice in range(2500)]
    cliente, fuente = crear_cliente(registros, limite_pagina=1000)
    repositorio = RepositorioEnMemoria()

    resumen = _ingerir(cliente, repositorio)

    assert fuente.offsets == [0, 1000, 2000]
    assert resumen.paginas == 3
    assert resumen.vistos == 2500
    assert len(repositorio) == 2500


def test_un_ciclo_vacio_es_un_resultado_valido(crear_cliente):
    cliente, _ = crear_cliente([])
    repositorio = RepositorioEnMemoria()

    resumen = _ingerir(cliente, repositorio)

    assert resumen.vacio
    assert (resumen.vistos, resumen.insertados, resumen.duplicados) == (0, 0, 0)
    assert resumen.paginas == 1
    assert len(repositorio) == 0


def test_un_ciclo_con_registros_no_es_vacio(crear_cliente):
    cliente, _ = crear_cliente([registro("row-1")])

    resumen = _ingerir(cliente, RepositorioEnMemoria())

    assert not resumen.vacio


def test_un_fallo_a_mitad_del_ciclo_conserva_lo_ya_guardado(crear_cliente):
    from vigia.ingest.socrata import ErrorFuente

    registros = [registro(f"row-{indice}") for indice in range(4)]
    cliente, _ = crear_cliente(registros, limite_pagina=2, fallos={2: 500})
    repositorio = RepositorioEnMemoria()

    with pytest.raises(ErrorFuente):
        _ingerir(cliente, repositorio)

    # La primera página entró completa; la segunda no entró en absoluto.
    assert len(repositorio) == 2


def test_un_rango_invertido_falla_antes_de_la_primera_peticion(crear_cliente):
    cliente, fuente = crear_cliente([registro("row-1")])

    with pytest.raises(RangoInvalido) as fallo:
        _ingerir(cliente, RepositorioEnMemoria(), desde=date(2026, 8, 5), hasta=date(2026, 8, 1))

    assert "2026-08-05" in str(fallo.value)
    assert "2026-08-01" in str(fallo.value)
    assert fuente.peticiones == []


def test_el_rango_incluye_el_dia_completo_del_extremo_derecho():
    filtro = filtro_por_rango(CONTRATOS, date(2026, 8, 1), date(2026, 8, 2))

    assert filtro == (
        "fecha_de_firma >= '2026-08-01T00:00:00.000' "
        "AND fecha_de_firma < '2026-08-03T00:00:00.000'"
    )


def test_un_rango_de_un_solo_dia_es_valido():
    filtro = filtro_por_rango(PROCESOS, date(2026, 8, 1), date(2026, 8, 1))

    assert filtro == (
        "fecha_de_publicacion_del >= '2026-08-01T00:00:00.000' "
        "AND fecha_de_publicacion_del < '2026-08-02T00:00:00.000'"
    )


def test_cada_dataset_acota_por_su_propio_campo_de_fecha(crear_cliente):
    cliente, fuente = crear_cliente([])

    _ingerir(cliente, RepositorioEnMemoria(), dataset=PROCESOS)

    assert "fecha_de_publicacion_del" in fuente.peticiones[0].url.params["$where"]


def test_el_resumen_registra_el_intervalo_del_ciclo(crear_cliente):
    cliente, _ = crear_cliente([registro("row-1")])

    resumen = _ingerir(cliente, RepositorioEnMemoria())

    assert resumen.inicio <= resumen.fin
    assert resumen.inicio.tzinfo == timezone.utc
    assert resumen.dataset == "contratos"
    assert (resumen.desde, resumen.hasta) == (DESDE, HASTA)


def test_un_extremo_derecho_en_el_limite_del_calendario_se_rechaza():
    from datetime import date as fecha

    with pytest.raises(RangoInvalido, match="fuera de rango"):
        filtro_por_rango(CONTRATOS, fecha(2026, 8, 1), fecha.max)


def test_al_abortar_se_registran_las_paginas_ya_confirmadas(crear_cliente, caplog):
    import logging

    from vigia.ingest.socrata import ErrorFuente

    registros = [registro(f"row-{indice}") for indice in range(4)]
    cliente, _ = crear_cliente(registros, limite_pagina=2, fallos={2: 500})

    with caplog.at_level(logging.ERROR, logger="vigia.ingest.ciclo"):
        with pytest.raises(ErrorFuente):
            _ingerir(cliente, RepositorioEnMemoria())

    assert "páginas confirmadas=1" in caplog.text
