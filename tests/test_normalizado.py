"""Capa normalizada: conversión, deduplicación y cruce proceso–contrato.

La llave de cruce es `proceso_de_compra` (Contratos) ↔ `id_del_portafolio`
(Procesos). El PRD decía `id_del_proceso`, que vive en otro espacio de nombres
y no cruza nunca. Medido el 2026-09-03 contra la fuente real.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from vigia.crudo.modelo import RegistroCrudo
from vigia.ingest.datasets import DATASETS
from vigia.normalizado.cruce import (
    ResumenNormalizacion,
    cruzar_contratos,
    deduplicar_procesos,
    indexar_por_portafolio,
    resumir,
)
from vigia.normalizado.modelo import (
    ContratoNormalizado,
    ProcesoNormalizado,
    RegistroSinIdentidadNormalizada,
)

MOMENTO = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


def sin_identidad_de_negocio(dataset: str, **campos) -> RegistroCrudo:
    """Una fila cruda SIN identidad de negocio, como las que dejó la llave vieja.

    `RegistroCrudo.desde_respuesta` ya no puede construirla —rechaza el
    registro—, y eso es correcto. Pero las filas escritas antes del cambio de
    llave siguen en la tabla y el reproceso desde crudo de la 6.3 las va a
    leer, así que la guarda de la capa normalizada tiene que seguir ahí.
    """
    return RegistroCrudo(
        dataset=dataset,
        id_fila_fuente="fila-de-la-llave-vieja",
        hash_contenido="0" * 64,
        contenido=dict(campos),
        consultado_en=MOMENTO,
    )


#: La identidad es del negocio, no del `:id` de la plataforma. El helper la
#: toma del descriptor del dataset, igual que el Ciclo real, para que una
#: prueba no pueda pasar con una identidad que producción no usaría.
def crudo(dataset: str, id_fila: str, **campos) -> RegistroCrudo:
    descriptor = DATASETS[dataset]
    identidad = {descriptor.campos_identidad[0]: id_fila}
    return RegistroCrudo.desde_respuesta(
        dataset=dataset,
        # Lo de `campos` gana: una prueba que pasa `id_contrato` explícito
        # está diciendo algo sobre la identidad y tiene que poder decirlo.
        contenido={":id": id_fila, **identidad, **campos},
        consultado_en=MOMENTO,
        campos_identidad=descriptor.campos_identidad,
    )


def contrato_crudo(id_fila: str, **campos) -> RegistroCrudo:
    campos.setdefault("id_contrato", f"CO1.PCCNTR.{id_fila}")
    return crudo("contratos", id_fila, **campos)


def proceso_crudo(id_fila: str, **campos) -> RegistroCrudo:
    campos.setdefault("id_del_proceso", f"CO1.REQ.{id_fila}")
    return crudo("procesos", id_fila, **campos)


# --------------------------------------------------------------- conversión


def test_un_contrato_se_convierte_con_sus_tipos():
    registro = contrato_crudo(
        "fila-1",
        id_contrato="CO1.PCCNTR.4168447",
        proceso_de_compra="CO1.BDOS.3452554",
        referencia_del_contrato="CPS-3548-2022",
        nit_entidad="899999027",
        nombre_entidad="DANE",
        valor_del_contrato="57333333",
        fecha_de_firma="2026-08-01T00:00:00.000",
        estado_contrato="En ejecucion",
    )

    contrato = ContratoNormalizado.desde_crudo(registro, momento=MOMENTO)

    assert contrato.id_contrato == "CO1.PCCNTR.4168447"
    assert contrato.proceso_de_compra == "CO1.BDOS.3452554"
    assert contrato.valor == Decimal("57333333")
    assert contrato.fecha_de_firma == date(2026, 8, 1)
    # Procedencia: sin esto la capa normalizada es una afirmación sin respaldo.
    # Desde la propuesta del 2026-09-04 la procedencia apunta a la identidad de
    # NEGOCIO de la fila cruda, no al `:id` de la plataforma, que la fuente
    # reasigna. Aquí coinciden con el propio `id_contrato` a propósito.
    assert contrato.id_fila_fuente == "CO1.PCCNTR.4168447"
    assert contrato.hash_contenido == registro.hash_contenido


def test_un_valor_ilegible_no_tumba_la_conversion():
    # La capa normalizada expone la calidad del dato, no la juzga. Un contrato
    # con el valor corrupto sigue siendo un contrato que hay que poder mirar.
    registro = contrato_crudo(
        "fila-1", valor_del_contrato="no es un numero", fecha_de_firma="ayer"
    )

    contrato = ContratoNormalizado.desde_crudo(registro, momento=MOMENTO)

    assert contrato.valor is None
    assert contrato.fecha_de_firma is None


def test_un_campo_vacio_o_de_espacios_cuenta_como_ausente():
    # La fuente usa las dos cosas para lo mismo; distinguirlas aquí solo
    # movería el problema aguas abajo.
    registro = contrato_crudo("fila-1", proceso_de_compra="   ", nit_entidad="")

    contrato = ContratoNormalizado.desde_crudo(registro, momento=MOMENTO)

    assert contrato.proceso_de_compra is None
    assert contrato.nit_entidad is None
    assert contrato.sin_llave_de_cruce


def test_un_contrato_sin_id_no_se_puede_normalizar():
    # Sin identidad, dos versiones del mismo contrato entrarían como filas
    # distintas y los conteos de cualquier Regla saldrían inflados.
    #
    # Desde el cambio de llave del 2026-09-04 la capa cruda ya no admite un
    # contrato sin `id_contrato`, así que este caso solo puede llegar de una
    # fila escrita bajo la llave vieja. Se construye a mano justamente por eso:
    # la guarda del normalizador sigue haciendo falta para el reproceso.
    registro = sin_identidad_de_negocio("contratos", proceso_de_compra="CO1.BDOS.1")

    with pytest.raises(RegistroSinIdentidadNormalizada, match="id_contrato"):
        ContratoNormalizado.desde_crudo(registro, momento=MOMENTO)


def test_el_si_y_el_no_del_secop_se_leen_como_booleano():
    for crudo_valor, esperado in [("Si", True), ("No", False), ("Quizá", None)]:
        proceso = ProcesoNormalizado.desde_crudo(
            proceso_crudo("f", adjudicado=crudo_valor), momento=MOMENTO
        )
        assert proceso.adjudicado is esperado


def test_un_enlace_sin_llave_de_cruce_es_imposible_de_construir():
    with pytest.raises(ValueError, match="se inventó"):
        ContratoNormalizado(
            id_contrato="CO1.PCCNTR.1",
            proceso_de_compra=None,
            id_del_proceso="CO1.REQ.1",
            referencia=None,
            nit_entidad=None,
            nombre_entidad=None,
            valor=None,
            fecha_de_firma=None,
            estado=None,
            proveedor_tipo=None,
            proveedor_numero=None,
            proveedor_nombre=None,
            orden=None,
            departamento_codigo=None,
            departamento_nombre=None,
            municipio_nombre=None,
            id_fila_fuente="f",
            hash_contenido="h",
            normalizado_en=MOMENTO,
        )


# ------------------------------------------------------------ deduplicación


def test_un_proceso_de_varios_lotes_colapsa_en_uno():
    # Medido contra la fuente: `CO1.REQ.10772032` devuelve 21 filas, iguales en
    # lo procedimental y distintas en el adjudicatario. El dataset tiene una
    # fila por ADJUDICACIÓN, no por Proceso.
    filas = [
        proceso_crudo(
            f"fila-{i}",
            id_del_proceso="CO1.REQ.10772032",
            id_del_portafolio="CO1.BDOS.10494164",
            nombre_del_proveedor=f"PROVEEDOR {i}",
        )
        for i in range(21)
    ]

    procesos, leidos, sin_identidad = deduplicar_procesos(filas, momento=MOMENTO)

    assert leidos == 21
    assert len(procesos) == 1
    assert sin_identidad == 0
    assert procesos["CO1.REQ.10772032"].id_del_portafolio == "CO1.BDOS.10494164"


def test_un_proceso_sin_id_se_descarta_y_se_cuenta():
    filas = [proceso_crudo("buena"), sin_identidad_de_negocio("procesos", entidad="X")]

    procesos, leidos, sin_identidad = deduplicar_procesos(filas, momento=MOMENTO)

    assert leidos == 2
    assert len(procesos) == 1
    assert sin_identidad == 1


def test_el_indice_avisa_cuando_un_portafolio_apunta_a_dos_procesos(caplog):
    # No está medido si esto puede pasar. Si pasa, resolverlo en silencio
    # dejaría un cruce que nadie puede sustentar.
    procesos = [
        ProcesoNormalizado.desde_crudo(p, momento=MOMENTO)
        for p in (
            proceso_crudo("a", id_del_proceso="CO1.REQ.1", id_del_portafolio="CO1.BDOS.9"),
            proceso_crudo("b", id_del_proceso="CO1.REQ.2", id_del_portafolio="CO1.BDOS.9"),
        )
    ]

    with caplog.at_level("WARNING"):
        indice = indexar_por_portafolio(procesos)

    assert indice["CO1.BDOS.9"] == "CO1.REQ.2"
    assert "más de un proceso" in caplog.text


def test_un_proceso_sin_portafolio_no_entra_al_indice():
    procesos = [
        ProcesoNormalizado.desde_crudo(
            proceso_crudo("a", id_del_proceso="CO1.REQ.1"), momento=MOMENTO
        )
    ]

    assert indexar_por_portafolio(procesos) == {}


# -------------------------------------------------------------------- cruce


def test_un_contrato_encuentra_su_proceso_por_el_portafolio():
    procesos, _, _ = deduplicar_procesos(
        [proceso_crudo("p", id_del_proceso="CO1.REQ.3544146", id_del_portafolio="CO1.BDOS.3452554")],
        momento=MOMENTO,
    )
    indice = indexar_por_portafolio(procesos.values())

    contratos, leidos, _ = cruzar_contratos(
        [contrato_crudo("c", proceso_de_compra="CO1.BDOS.3452554")],
        indice_portafolio=indice,
        momento=MOMENTO,
    )

    assert leidos == 1
    assert contratos[0].id_del_proceso == "CO1.REQ.3544146"
    assert not contratos[0].huerfano


def test_no_se_cruza_contra_id_del_proceso():
    # El fallo que este proyecto estuvo a punto de cometer: `id_del_proceso`
    # es del espacio CO1.REQ. y no comparte un solo valor con Contratos.
    # Un contrato cuya llave coincida con un `id_del_proceso` NO debe enlazar.
    procesos, _, _ = deduplicar_procesos(
        [proceso_crudo("p", id_del_proceso="CO1.BDOS.3452554", id_del_portafolio=None)],
        momento=MOMENTO,
    )
    indice = indexar_por_portafolio(procesos.values())

    contratos, _, _ = cruzar_contratos(
        [contrato_crudo("c", proceso_de_compra="CO1.BDOS.3452554")],
        indice_portafolio=indice,
        momento=MOMENTO,
    )

    assert contratos[0].id_del_proceso is None
    assert contratos[0].huerfano


def test_un_contrato_huerfano_se_conserva_y_es_consultable():
    # FR-2: los registros sin correspondencia quedan marcados y son
    # consultables, no descartados en silencio.
    contratos, _, _ = cruzar_contratos(
        [contrato_crudo("c", proceso_de_compra="CO1.BDOS.nadie")],
        indice_portafolio={},
        momento=MOMENTO,
    )

    assert len(contratos) == 1
    assert contratos[0].huerfano
    assert not contratos[0].sin_llave_de_cruce


def test_huerfano_y_sin_llave_son_fallos_distintos():
    contratos, _, _ = cruzar_contratos(
        [
            contrato_crudo("enlazado", proceso_de_compra="CO1.BDOS.1"),
            contrato_crudo("huerfano", proceso_de_compra="CO1.BDOS.nadie"),
            contrato_crudo("sin_llave"),
        ],
        indice_portafolio={"CO1.BDOS.1": "CO1.REQ.1"},
        momento=MOMENTO,
    )
    resumen = resumir(
        contratos,
        procesos_leidos=1,
        procesos_normalizados=1,
        contratos_leidos=3,
        contratos_sin_identidad=0,
    )

    assert resumen.enlazados == 1
    assert resumen.huerfanos == 1
    assert resumen.sin_llave_de_cruce == 1
    # La proporción se mide sobre los que SÍ traen llave: 1 de 2. Incluir al
    # que no la trae daría 33% y movería el indicador por la razón equivocada.
    assert resumen.proporcion_huerfanos == pytest.approx(0.5)


# ------------------------------------------------------------------ resumen


def test_el_resumen_expone_cuantas_filas_se_colapsaron():
    resumen = ResumenNormalizacion(
        procesos_leidos=21,
        procesos_normalizados=1,
        contratos_leidos=0,
        contratos_normalizados=0,
        huerfanos=0,
        sin_llave_de_cruce=0,
        sin_identidad=0,
    )

    assert resumen.procesos_colapsados == 20


def test_sin_contratos_con_llave_la_proporcion_es_desconocida_no_cero():
    # Cero por ciento de huérfanos y «no hay de qué hablar» son cosas
    # distintas. Devolver 0.0 las confundiría y pintaría de verde un Ciclo
    # que no midió nada.
    resumen = ResumenNormalizacion(
        procesos_leidos=0,
        procesos_normalizados=0,
        contratos_leidos=1,
        contratos_normalizados=1,
        huerfanos=0,
        sin_llave_de_cruce=1,
        sin_identidad=0,
    )

    assert resumen.proporcion_huerfanos is None


def test_un_resumen_incoherente_no_se_puede_construir():
    with pytest.raises(ValueError, match="incoherentes"):
        ResumenNormalizacion(
            procesos_leidos=0,
            procesos_normalizados=0,
            contratos_leidos=10,
            contratos_normalizados=3,
            huerfanos=0,
            sin_llave_de_cruce=0,
            sin_identidad=0,
        )


def test_no_puede_haber_mas_huerfanos_que_contratos():
    with pytest.raises(ValueError, match="superan"):
        ResumenNormalizacion(
            procesos_leidos=0,
            procesos_normalizados=0,
            contratos_leidos=2,
            contratos_normalizados=2,
            huerfanos=2,
            sin_llave_de_cruce=1,
            sin_identidad=0,
        )
