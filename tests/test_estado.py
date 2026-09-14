"""Marca de agua, ventana de solapamiento y registro de Ciclo."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from tests.conftest import CAMPOS_CONTRATOS, registro
from vigia.crudo.memoria import RepositorioEnMemoria
from vigia.ingest.ciclo import RangoInvalido, ejecutar_ciclo, fecha_de_hecho
from vigia.ingest.datasets import CONTRATOS, PROCESOS
from vigia.ingest.estado import (
    EstadoCiclo,
    MarcaDeAgua,
    RegistroDeCiclo,
    RepositorioEstadoEnMemoria,
)
from vigia.ingest.socrata import ErrorFuente

MOMENTO = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
HOY = date(2026, 9, 2)


def contrato(id_fila: str, firmado: str) -> dict:
    return registro(id_fila, fecha_de_firma=f"{firmado}T00:00:00.000")


def correr(cliente, repositorio, estado, *, desde=None, hasta=HOY, ventana=30):
    return ejecutar_ciclo(
        cliente=cliente,
        repositorio=repositorio,
        estado=estado,
        dataset=CONTRATOS,
        desde=desde,
        hasta=hasta,
        ventana_dias=ventana,
    )


# --- Lectura de la fecha de hecho ------------------------------------------


def test_la_fecha_de_hecho_sale_del_campo_del_dataset():
    assert fecha_de_hecho(CONTRATOS, contrato("row-1", "2026-08-15")) == date(2026, 8, 15)


def test_cada_dataset_lee_su_propio_campo():
    proceso = {":id": "row-1", "fecha_de_publicacion_del": "2026-08-15T00:00:00.000"}

    assert fecha_de_hecho(PROCESOS, proceso) == date(2026, 8, 15)
    # El campo de Contratos no está: no se inventa nada.
    assert fecha_de_hecho(CONTRATOS, proceso) is None


@pytest.mark.parametrize("valor", ["", "no es una fecha", 20260815, {"url": "x"}])
def test_una_fecha_ilegible_devuelve_none_en_vez_de_romper(valor):
    assert fecha_de_hecho(CONTRATOS, registro("row-1", fecha_de_firma=valor)) is None


def test_un_contenido_sin_el_campo_devuelve_none():
    assert fecha_de_hecho(CONTRATOS, {":id": "row-1"}) is None


# --- Primer Ciclo -----------------------------------------------------------


def test_el_primer_ciclo_sin_desde_no_arranca(crear_cliente):
    cliente, fuente = crear_cliente([contrato("row-1", "2026-08-15")])

    with pytest.raises(RangoInvalido, match="--desde"):
        correr(cliente, RepositorioEnMemoria(), RepositorioEstadoEnMemoria())

    # Sin marca no se inventa el alcance del histórico, ni se gasta una petición.
    assert fuente.peticiones == []


def test_el_primer_ciclo_con_desde_deja_la_marca_en_hasta(crear_cliente):
    cliente, _ = crear_cliente([contrato("row-1", "2026-08-15")])
    estado = RepositorioEstadoEnMemoria()

    ciclo = correr(cliente, RepositorioEnMemoria(), estado, desde=date(2026, 8, 1))

    assert ciclo.cursor_entrada is None
    assert ciclo.cursor_salida == HOY
    assert estado.marca("contratos").fecha_hecho == HOY


# --- Ciclo incremental ------------------------------------------------------


def test_el_ciclo_incremental_retrocede_la_ventana(crear_cliente):
    cliente, fuente = crear_cliente([])
    estado = RepositorioEstadoEnMemoria()
    estado.cerrar_ciclo(
        RegistroDeCiclo(
            dataset="contratos",
            cursor_entrada=None,
            cursor_salida=date(2026, 8, 20),
            desde=date(2026, 8, 1),
            hasta=date(2026, 8, 20),
            estado=EstadoCiclo.COMPLETO,
            inicio=MOMENTO,
            fin=MOMENTO,
        )
    )

    ciclo = correr(cliente, RepositorioEnMemoria(), estado, ventana=30)

    assert ciclo.cursor_entrada == date(2026, 8, 20)
    assert ciclo.desde == date(2026, 7, 21)  # 20 de agosto menos 30 días
    filtro = fuente.peticiones[0].url.params["$where"]
    assert "2026-07-21" in filtro


def test_una_ventana_de_cero_arranca_exactamente_en_la_marca(crear_cliente):
    cliente, _ = crear_cliente([])
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 20), MOMENTO)

    ciclo = correr(cliente, RepositorioEnMemoria(), estado, ventana=0)

    assert ciclo.desde == date(2026, 8, 20)


def test_una_ventana_negativa_se_rechaza(crear_cliente):
    cliente, _ = crear_cliente([])

    with pytest.raises(RangoInvalido, match="negativa"):
        correr(cliente, RepositorioEnMemoria(), RepositorioEstadoEnMemoria(), ventana=-1)


def test_una_marca_por_delante_del_rango_es_un_rango_invertido(crear_cliente):
    cliente, fuente = crear_cliente([])
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 12, 1), MOMENTO)

    with pytest.raises(RangoInvalido) as fallo:
        correr(cliente, RepositorioEnMemoria(), estado, hasta=HOY, ventana=0)

    assert "2026-12-01" in str(fallo.value)
    assert fuente.peticiones == []


# --- La marca solo avanza si el Ciclo termina bien --------------------------


def test_un_ciclo_completo_avanza_la_marca(crear_cliente):
    cliente, _ = crear_cliente([contrato("row-1", "2026-08-15")])
    estado = RepositorioEstadoEnMemoria()

    correr(cliente, RepositorioEnMemoria(), estado, desde=date(2026, 8, 1))

    assert estado.marca("contratos").fecha_hecho == HOY


def test_un_ciclo_fallido_no_avanza_la_marca_y_deja_su_causa(crear_cliente):
    cliente, _ = crear_cliente(
        [contrato(f"row-{i}", "2026-08-15") for i in range(4)],
        limite_pagina=2,
        fallos={2: 500},
    )
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 20), MOMENTO)

    with pytest.raises(ErrorFuente):
        correr(cliente, RepositorioEnMemoria(), estado, ventana=30)

    assert estado.marca("contratos").fecha_hecho == date(2026, 8, 20)
    fallido = estado.ciclos[-1]
    assert fallido.estado == EstadoCiclo.FALLIDO
    assert "500" in fallido.causa
    assert fallido.cursor_salida is None


def test_el_siguiente_ciclo_reanuda_desde_la_marca_vieja(crear_cliente):
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 20), MOMENTO)

    roto, _ = crear_cliente([contrato("row-1", "2026-08-15")], fallos={0: 500})
    with pytest.raises(ErrorFuente):
        correr(roto, RepositorioEnMemoria(), estado, ventana=0)

    sano, fuente = crear_cliente([contrato("row-1", "2026-08-15")])
    correr(sano, RepositorioEnMemoria(), estado, ventana=0)

    assert "2026-08-20" in fuente.peticiones[0].url.params["$where"]


def test_la_marca_nunca_retrocede(crear_cliente):
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 20), MOMENTO)
    cliente, _ = crear_cliente([])

    # Un reproceso de un rango viejo no debe obligar a releer lo que vino después.
    correr(cliente, RepositorioEnMemoria(), estado, desde=date(2026, 1, 1), hasta=date(2026, 3, 1))

    assert estado.marca("contratos").fecha_hecho == date(2026, 8, 20)


# --- Ciclo vacío vs. Ciclo fallido -----------------------------------------


def test_un_ciclo_vacio_es_completo_y_avanza_la_marca(crear_cliente):
    cliente, _ = crear_cliente([])
    estado = RepositorioEstadoEnMemoria()

    ciclo = correr(cliente, RepositorioEnMemoria(), estado, desde=date(2026, 8, 1))

    assert ciclo.vacio
    assert ciclo.completo
    assert ciclo.vistos == 0
    assert estado.marca("contratos").fecha_hecho == HOY


def test_un_ciclo_vacio_y_uno_fallido_se_distinguen(crear_cliente):
    estado = RepositorioEstadoEnMemoria()

    vacio, _ = crear_cliente([])
    correr(vacio, RepositorioEnMemoria(), estado, desde=date(2026, 8, 1))

    roto, _ = crear_cliente([], fallos={0: 503})
    with pytest.raises(ErrorFuente):
        correr(roto, RepositorioEnMemoria(), estado, ventana=0)

    uno, otro = estado.ciclos
    assert (uno.vacio, uno.estado) == (True, EstadoCiclo.COMPLETO)
    assert otro.estado == EstadoCiclo.FALLIDO
    assert not otro.vacio


def test_un_registro_de_ciclo_fallido_sin_causa_se_rechaza():
    with pytest.raises(ValueError, match="causa"):
        RegistroDeCiclo(
            dataset="contratos",
            cursor_entrada=None,
            cursor_salida=None,
            desde=date(2026, 8, 1),
            hasta=HOY,
            estado=EstadoCiclo.FALLIDO,
            inicio=MOMENTO,
            fin=MOMENTO,
        )


def test_un_estado_de_ciclo_desconocido_se_rechaza():
    with pytest.raises(ValueError, match="estado de Ciclo desconocido"):
        RegistroDeCiclo(
            dataset="contratos",
            cursor_entrada=None,
            cursor_salida=None,
            desde=date(2026, 8, 1),
            hasta=HOY,
            estado="a medias",
            inicio=MOMENTO,
            fin=MOMENTO,
        )


# --- La señal de ventana corta ----------------------------------------------


def test_un_registro_nuevo_en_el_borde_de_la_ventana_enciende_la_alarma(crear_cliente):
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 31), MOMENTO)
    # Con ventana de 30 días el borde es 2026-08-01.
    cliente, _ = crear_cliente([contrato("row-1", "2026-08-01")])

    ciclo = correr(cliente, RepositorioEnMemoria(), estado, ventana=30)

    assert ciclo.desde == date(2026, 8, 1)
    assert ciclo.en_borde_de_ventana == 1
    assert ciclo.ventana_corta


def test_un_duplicado_en_el_borde_no_enciende_la_alarma(crear_cliente):
    # Lo que se espera ver en el borde es precisamente lo ya ingerido: contarlo
    # volvería la alarma inútil.
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 31), MOMENTO)
    almacen = RepositorioEnMemoria()

    uno, _ = crear_cliente([contrato("row-1", "2026-08-01")])
    correr(uno, almacen, estado, ventana=30)

    otro, _ = crear_cliente([contrato("row-1", "2026-08-01")])
    segundo = correr(otro, almacen, estado, ventana=30)

    assert segundo.insertados == 0
    assert segundo.en_borde_de_ventana == 0
    assert not segundo.ventana_corta


def test_un_registro_publicado_con_retraso_cuenta_como_recuperado(crear_cliente):
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 20), MOMENTO)
    # Firmado antes de la marca, visto ahora: sin ventana se habría perdido.
    cliente, _ = crear_cliente([contrato("row-1", "2026-08-10")])

    ciclo = correr(cliente, RepositorioEnMemoria(), estado, ventana=30)

    assert ciclo.recuperados_por_solapamiento == 1
    assert ciclo.en_borde_de_ventana == 0


def test_en_el_primer_ciclo_nada_cuenta_como_recuperado(crear_cliente):
    # Sin marca previa no hay nada que recuperar: todo es histórico pedido a mano.
    cliente, _ = crear_cliente([contrato("row-1", "2026-08-10")])

    ciclo = correr(
        cliente, RepositorioEnMemoria(), RepositorioEstadoEnMemoria(), desde=date(2026, 8, 1)
    )

    assert ciclo.recuperados_por_solapamiento == 0


def test_un_registro_sin_fecha_de_hecho_no_vuelve_de_una_consulta_por_rango(crear_cliente):
    """La consulta filtra sobre el mismo campo, y SoQL descarta los nulos.

    Consecuencia que conviene tener escrita: un contrato sin `fecha_de_firma`
    es invisible para TODO Ciclo incremental, para siempre. Está anotado en
    `deferred-work.md` como medición pendiente de cobertura del campo.
    """
    sin_fecha = {":id": "row-1", "nit_entidad": "899999027"}
    cliente, _ = crear_cliente([sin_fecha], columnas=CAMPOS_CONTRATOS)
    almacen = RepositorioEnMemoria()

    ciclo = correr(cliente, almacen, RepositorioEstadoEnMemoria(), desde=date(2026, 8, 1))

    assert len(almacen) == 0
    assert ciclo.vacio


def test_si_la_fuente_lo_devolviera_igual_se_ingiere_y_se_cuenta_aparte(crear_cliente):
    # Camino defensivo: la fuente no debería mandarlo, pero si lo manda no
    # rompe el Ciclo y queda contado.
    import httpx

    cliente, _ = crear_cliente(
        [],
        columnas=CAMPOS_CONTRATOS,
        respuesta_cruda=lambda offset: httpx.Response(
            200,
            json=[{":id": "row-1", "id_contrato": "c-1"}] if offset == 0 else [],
        ),
    )
    almacen = RepositorioEnMemoria()

    ciclo = correr(cliente, almacen, RepositorioEstadoEnMemoria(), desde=date(2026, 8, 1))

    assert len(almacen) == 1
    assert ciclo.sin_fecha_de_hecho == 1
    assert ciclo.en_borde_de_ventana == 0


# --- Registro de Ciclo (AD-4) ----------------------------------------------


def test_el_ciclo_registra_sus_cursores_y_conteos(crear_cliente):
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 20), MOMENTO)
    cliente, _ = crear_cliente(
        [contrato(f"row-{i}", "2026-08-25") for i in range(3)], limite_pagina=2
    )

    ciclo = correr(cliente, RepositorioEnMemoria(), estado, ventana=10)

    assert ciclo.dataset == "contratos"
    assert ciclo.cursor_entrada == date(2026, 8, 20)
    assert ciclo.cursor_salida == HOY
    assert (ciclo.paginas, ciclo.vistos, ciclo.insertados, ciclo.duplicados) == (2, 3, 3, 0)
    assert ciclo.inicio <= ciclo.fin
    # La 1.4 llenará los huérfanos; hoy queda declarado que no se sabe.
    assert ciclo.huerfanos is None


def test_las_novedades_de_esquema_viajan_al_registro_de_ciclo(crear_cliente):
    from vigia.schema.definiciones import EsquemaEsperado
    from vigia.schema.novedades import RepositorioNovedadesEnMemoria
    from vigia.schema.validacion import ValidadorDeEsquema

    cliente, _ = crear_cliente(
        [contrato("row-1", "2026-08-15")], columnas=set(CAMPOS_CONTRATOS) | {"nuevo"}
    )
    esperado = EsquemaEsperado(
        dataset="contratos",
        id_socrata=CONTRATOS.id_socrata,
        capturado_en=date(2026, 9, 2),
        procedencia="x",
        campos=frozenset(CAMPOS_CONTRATOS),
    )

    ciclo = ejecutar_ciclo(
        cliente=cliente,
        repositorio=RepositorioEnMemoria(),
        estado=RepositorioEstadoEnMemoria(),
        dataset=CONTRATOS,
        desde=date(2026, 8, 1),
        hasta=HOY,
        ventana_dias=30,
        validador=ValidadorDeEsquema(cliente, esperado, RepositorioNovedadesEnMemoria()),
    )

    assert ciclo.novedades == ("nuevo",)


def test_una_marca_sin_zona_horaria_se_rechaza():
    with pytest.raises(ValueError, match="zona horaria"):
        MarcaDeAgua("contratos", HOY, datetime(2026, 9, 2, 12, 0))


def test_la_marca_se_normaliza_a_utc():
    bogota = timezone(timedelta(hours=-5))

    marca = MarcaDeAgua("contratos", HOY, datetime(2026, 9, 2, 7, 0, tzinfo=bogota))

    assert marca.actualizada_en == MOMENTO


def test_un_rango_explicito_no_enciende_la_alarma_de_ventana(crear_cliente):
    # En un histórico pedido a mano, que haya registros nuevos el primer día
    # del rango es lo normal. La alarma solo significa algo cuando `desde` es
    # un borde de ventana derivado de la marca.
    cliente, _ = crear_cliente([contrato("row-1", "2026-08-01")])

    ciclo = correr(
        cliente,
        RepositorioEnMemoria(),
        RepositorioEstadoEnMemoria(),
        desde=date(2026, 8, 1),
        hasta=date(2026, 8, 31),
    )

    assert ciclo.insertados == 1
    assert ciclo.en_borde_de_ventana == 0
    assert not ciclo.ventana_corta
    assert not ciclo.desde_derivado


def test_una_llave_repetida_en_la_pagina_no_infla_las_senales(crear_cliente):
    # El repositorio cuenta una sola inserción; las señales tienen que contar
    # lo mismo, o superarían a `insertados` y la alarma mentiría.
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 31), MOMENTO)
    repetido = contrato("row-1", "2026-08-01")
    cliente, _ = crear_cliente([repetido, dict(repetido)])

    ciclo = correr(cliente, RepositorioEnMemoria(), estado, ventana=30)

    assert (ciclo.insertados, ciclo.duplicados) == (1, 1)
    assert ciclo.en_borde_de_ventana == 1


def test_un_ciclo_registra_la_ventana_con_la_que_corrio(crear_cliente):
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 8, 20), MOMENTO)
    cliente, _ = crear_cliente([])

    ciclo = correr(cliente, RepositorioEnMemoria(), estado, ventana=7)

    assert ciclo.ventana_dias == 7
    assert ciclo.desde_derivado


def test_una_marca_por_delante_del_rango_deja_registro_de_ciclo(crear_cliente):
    # Es un fallo operativo recurrente: tiene que verse en la tabla `ciclo`.
    cliente, _ = crear_cliente([])
    estado = RepositorioEstadoEnMemoria()
    estado.fijar_marca("contratos", date(2026, 12, 1), MOMENTO)

    with pytest.raises(RangoInvalido):
        correr(cliente, RepositorioEnMemoria(), estado, hasta=HOY, ventana=0)

    fallido = estado.ciclos[-1]
    assert fallido.estado == EstadoCiclo.FALLIDO
    assert "la marca de 'contratos' está en 2026-12-01" in fallido.causa


def test_una_interrupcion_a_mano_tambien_deja_registro(crear_cliente):
    class FuenteQueSeInterrumpe:
        def paginas(self, dataset, *, filtro=None):
            raise KeyboardInterrupt()
            yield  # pragma: no cover

    estado = RepositorioEstadoEnMemoria()

    with pytest.raises(KeyboardInterrupt):
        ejecutar_ciclo(
            cliente=FuenteQueSeInterrumpe(),
            repositorio=RepositorioEnMemoria(),
            estado=estado,
            dataset=CONTRATOS,
            desde=date(2026, 8, 1),
            hasta=HOY,
            ventana_dias=30,
        )

    assert estado.ciclos[-1].estado == EstadoCiclo.FALLIDO
    assert "KeyboardInterrupt" in estado.ciclos[-1].causa


def test_si_el_almacen_falla_al_registrar_sube_la_causa_original(crear_cliente, caplog):
    import logging

    from vigia.crudo.repositorio import ErrorAlmacen

    class EstadoRoto:
        def marca(self, dataset):
            return None

        def cerrar_ciclo(self, registro):
            raise ErrorAlmacen("la base no responde")

    cliente, _ = crear_cliente([contrato("row-1", "2026-08-15")], fallos={0: 500})

    with caplog.at_level(logging.ERROR, logger="vigia.ingest.ciclo"):
        with pytest.raises(ErrorFuente, match="500"):
            correr(cliente, RepositorioEnMemoria(), EstadoRoto(), desde=date(2026, 8, 1))

    # La causa que sube sigue siendo la de la fuente, no la de la base.
    assert "no se pudo registrar el Ciclo fallido" in caplog.text


@pytest.mark.parametrize("campo", ["inicio", "fin"])
def test_un_registro_de_ciclo_con_fecha_ingenua_se_rechaza(campo):
    momentos = {"inicio": MOMENTO, "fin": MOMENTO}
    momentos[campo] = datetime(2026, 9, 2, 12, 0)

    with pytest.raises(ValueError, match="zona horaria"):
        RegistroDeCiclo(
            dataset="contratos",
            cursor_entrada=None,
            cursor_salida=HOY,
            desde=date(2026, 8, 1),
            hasta=HOY,
            estado=EstadoCiclo.COMPLETO,
            **momentos,
        )


def test_un_ciclo_completo_sin_cursor_de_salida_se_rechaza():
    with pytest.raises(ValueError, match="cursor de salida"):
        RegistroDeCiclo(
            dataset="contratos",
            cursor_entrada=None,
            cursor_salida=None,
            desde=date(2026, 8, 1),
            hasta=HOY,
            estado=EstadoCiclo.COMPLETO,
            inicio=MOMENTO,
            fin=MOMENTO,
        )


def test_unos_conteos_incoherentes_se_rechazan():
    with pytest.raises(ValueError, match="no suma vistos"):
        RegistroDeCiclo(
            dataset="contratos",
            cursor_entrada=None,
            cursor_salida=HOY,
            desde=date(2026, 8, 1),
            hasta=HOY,
            estado=EstadoCiclo.COMPLETO,
            inicio=MOMENTO,
            fin=MOMENTO,
            vistos=3,
            insertados=1,
            duplicados=1,
        )
