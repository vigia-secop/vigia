"""Identidad determinista del registro crudo."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from vigia.crudo.modelo import RegistroCrudo, RegistroSinIdentidad, hash_contenido
from vigia.ingest.datasets import CONTRATOS, PROCESOS

#: Identidad de Contratos, para no repetirla en cada llamada.
IDENTIDAD = CONTRATOS.campos_identidad


def construir(contenido, momento=None, campos_identidad=IDENTIDAD):
    return RegistroCrudo.desde_respuesta(
        "contratos", contenido, momento or MOMENTO, campos_identidad=campos_identidad
    )

MOMENTO = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def test_el_hash_no_depende_del_orden_de_las_claves():
    uno = {":id": "row-1", "id_contrato": "c-1", "a": 1, "b": 2}
    otro = {"b": 2, "id_contrato": "c-1", ":id": "row-1", "a": 1}

    assert hash_contenido(uno) == hash_contenido(otro)


def test_el_hash_distingue_contenidos_distintos():
    assert hash_contenido({":id": "row-1", "valor": "1"}) != hash_contenido(
        {":id": "row-1", "valor": "2"}
    )


def test_el_hash_distingue_una_clave_ausente_de_una_clave_nula():
    # Socrata omite las claves nulas. Que ausente y nulo hasheen distinto es lo
    # que permite, aguas abajo, notar que la fuente empezó a mandar nulos.
    assert hash_contenido({":id": "row-1"}) != hash_contenido({":id": "row-1", "campo": None})


def test_el_contenido_se_guarda_sin_transformar():
    contenido = {
        ":id": "row-1",
        "id_contrato": "CO1.PCCNTR.1",
        "valor_del_contrato": "8959088",
        "urlproceso": {"url": "https://community.secop.gov.co/x"},
        "acentos": "Bogotá",
    }

    crudo = construir(contenido, MOMENTO)

    assert dict(crudo.contenido) == contenido


def test_el_contenido_almacenado_no_cambia_si_muta_el_original():
    contenido = {":id": "row-1", "id_contrato": "c-1", "estado": "original"}
    crudo = construir(contenido, MOMENTO)

    contenido["estado"] = "mutado"

    assert crudo.contenido["estado"] == "original"


def test_un_registro_sin_identidad_de_negocio_no_se_acepta():
    with pytest.raises(RegistroSinIdentidad, match="id_contrato"):
        construir({":id": "row-1", "nit_entidad": "899999027"}, MOMENTO)


@pytest.mark.parametrize("id_invalido", ["", None, 42])
def test_una_identidad_vacia_o_de_otro_tipo_no_se_acepta(id_invalido):
    with pytest.raises(RegistroSinIdentidad):
        construir({":id": "row-1", "id_contrato": id_invalido}, MOMENTO)


def test_la_fecha_de_consulta_se_normaliza_a_utc():
    bogota = timezone(timedelta(hours=-5))
    local = datetime(2026, 9, 2, 7, 0, tzinfo=bogota)

    crudo = construir({":id": "row-1", "id_contrato": "c-1"}, local)

    assert crudo.consultado_en == MOMENTO
    assert crudo.consultado_en.tzinfo == timezone.utc


def test_una_fecha_de_consulta_sin_zona_horaria_no_se_acepta():
    with pytest.raises(ValueError, match="zona horaria"):
        construir({":id": "row-1", "id_contrato": "c-1"}, datetime(2026, 9, 2, 12, 0))


def test_la_llave_sigue_el_orden_de_la_llave_primaria():
    crudo = construir({":id": "row-1", "id_contrato": "c-1"}, MOMENTO)

    assert crudo.llave == ("contratos", "c-1", crudo.hash_contenido)


def test_una_identidad_en_blanco_no_se_acepta():
    with pytest.raises(RegistroSinIdentidad):
        construir({":id": "row-1", "id_contrato": "   "}, MOMENTO)


def test_un_contenido_que_no_es_objeto_no_se_acepta():
    with pytest.raises(RegistroSinIdentidad, match="no es un objeto"):
        construir(["row-1"], MOMENTO)


# --------------------------------------------------------------------------
# La llave de negocio. Añadido por `sprint-change-proposal-2026-09-04.md`:
# el `:id` de Socrata no es estable entre publicaciones y apoyar la identidad
# en él hacía reinsertar la ventana entera en cada Ciclo.
# --------------------------------------------------------------------------


def test_el_id_de_socrata_no_participa_en_la_identidad():
    # El mismo contrato, republicado: `:id` nuevo, `:updated_at` nuevo, y una
    # clave de plataforma que antes no venía. Es el caso real medido el
    # 2026-09-03 sobre 24 685 contratos.
    antes = construir(
        {":id": "aaa", ":updated_at": "2026-09-03T10:00:00.000",
         "id_contrato": "CO1.PCCNTR.1", "estado_contrato": "Aprobado"}
    )
    despues = construir(
        {":id": "zzz", ":updated_at": "2026-09-03T17:00:00.000", ":version": "3",
         "id_contrato": "CO1.PCCNTR.1", "estado_contrato": "Aprobado"}
    )

    assert antes.llave == despues.llave


def test_un_cambio_de_negocio_si_produce_una_version_nueva():
    # El otro lado de la misma moneda: de 300 contratos duplicados medidos, 17
    # traían un cambio real. Colapsarlos sería perder dato de la fuente.
    antes = construir({":id": "aaa", "id_contrato": "CO1.PCCNTR.1", "estado_contrato": "Aprobado"})
    despues = construir({":id": "zzz", "id_contrato": "CO1.PCCNTR.1", "estado_contrato": "Modificado"})

    assert antes.llave != despues.llave


def test_los_campos_de_plataforma_se_guardan_aunque_no_se_hasheen():
    # La capa cruda conserva lo que llegó. Lo que cambia es sobre qué se
    # calcula la identidad, no qué se almacena.
    crudo = construir({":id": "aaa", ":version": "3", "id_contrato": "CO1.PCCNTR.1"})

    assert crudo.contenido[":id"] == "aaa"
    assert crudo.contenido[":version"] == "3"


def test_procesos_se_identifica_por_proceso_y_adjudicacion():
    # El dataset trae una fila por ADJUDICACIÓN. Identificar solo por proceso
    # colapsaría los lotes de un multilote en una sola fila cruda.
    lote_uno = RegistroCrudo.desde_respuesta(
        "procesos", {":id": "a", "id_del_proceso": "CO1.REQ.7", "id_adjudicacion": "ADJ1"},
        MOMENTO, campos_identidad=PROCESOS.campos_identidad)
    lote_dos = RegistroCrudo.desde_respuesta(
        "procesos", {":id": "b", "id_del_proceso": "CO1.REQ.7", "id_adjudicacion": "ADJ2"},
        MOMENTO, campos_identidad=PROCESOS.campos_identidad)

    assert lote_uno.id_fila_fuente != lote_dos.id_fila_fuente


def test_un_proceso_sin_adjudicar_tiene_identidad_igualmente():
    # Y la gana cuando la tenga, sin cambiar la de los que ya la tienen.
    sin_adjudicar = RegistroCrudo.desde_respuesta(
        "procesos", {":id": "a", "id_del_proceso": "CO1.REQ.7"},
        MOMENTO, campos_identidad=PROCESOS.campos_identidad)

    assert sin_adjudicar.id_fila_fuente == "CO1.REQ.7"


def test_el_contenido_anidado_tampoco_cambia_si_muta_el_original():
    # La copia es profunda: contenido y hash no pueden divergir.
    anidado = {"lista": [1, 2]}
    contenido = {":id": "row-1", "id_contrato": "c-1", "anidado": anidado}
    crudo = construir(contenido, MOMENTO)

    anidado["lista"].append(3)

    assert crudo.contenido["anidado"] == {"lista": [1, 2]}
    assert hash_contenido(crudo.contenido) == crudo.hash_contenido


def test_un_valor_no_representable_en_json_se_rechaza_antes_de_hashear():
    from vigia.crudo.modelo import ContenidoNoSerializable

    # NaN pasa el analizador de JSON de Python pero PostgreSQL lo rechaza:
    # descubrirlo al insertar costaría la página entera.
    with pytest.raises(ContenidoNoSerializable):
        construir({":id": "row-1", "id_contrato": "c-1", "valor": float("nan")}, MOMENTO)


def test_el_hash_recalculado_sobre_lo_guardado_coincide():
    contenido = {":id": "row-1", "id_contrato": "c-1", "b": 2, "a": {"z": [1, 2]}}
    crudo = construir(contenido, MOMENTO)

    assert hash_contenido(crudo.contenido) == crudo.hash_contenido
