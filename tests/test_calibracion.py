"""Modo calibración sobre un recorte (historia 2.5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vigia.reglas.calibracion import (
    MUESTRA_POR_DEFECTO, Recorte, RecorteVacio, ResultadoCalibracion,
    calibrar, promover,
)
from vigia.reglas.modelo import ACTIVA, BORRADOR, CALIBRACION, TransicionNoPermitida
from vigia.reglas.oferente_unico import crear, evaluar

MOMENTO = datetime(2026, 9, 6, 3, 0, tzinfo=timezone.utc)
CONSULTA = datetime(2026, 9, 6, 2, 30, tzinfo=timezone.utc)

RECORTE = Recorte(
    nombre="Boyacá, competitivos de agosto",
    motivo=(
        "Departamento mediano y con licitación pública suficiente para ver la "
        "forma de la bandera sin mirar el país entero."
    ),
    filtros={"departamento": "15", "desde": "2026-08-01"},
)


def proceso(unicos="1", modalidad="Licitación pública", identificador="CO1.REQ.1"):
    return {
        "id_del_proceso": identificador,
        "adjudicado": "Si",
        "modalidad_de_contratacion": modalidad,
        "proveedores_invitados": "14",
        "proveedores_con_invitacion": "14",
        "visualizaciones_del": "77",
        "proveedores_que_manifestaron": "0",
        "respuestas_al_procedimiento": unicos,
        "respuestas_externas": "0",
        "conteo_de_respuestas_a_ofertas": unicos,
        "proveedores_unicos_con": unicos,
        "numero_de_lotes": "0",
    }


def regla_calibrando():
    r = crear(MOMENTO)
    r.mover_a(CALIBRACION)
    return r


def _calibrar(registros, regla=None, **extra):
    r = regla or regla_calibrando()
    return calibrar(
        registros, regla=r, version=r.vigente, recorte=RECORTE,
        evaluador=evaluar, consultado_en=CONSULTA, momento=MOMENTO, **extra,
    )


# ------------------------------------------------------- lo que produce


def test_las_alertas_de_calibracion_no_salen_del_resultado():
    # El criterio de aceptación literal: no entran a la cola general. Aquí eso
    # es estructural — `calibrar` devuelve conteos y muestra, y no hay ninguna
    # ruta por la que una Alerta de calibración llegue a otra parte.
    resultado = _calibrar([proceso(identificador=f"CO1.REQ.{i}") for i in range(4)])

    assert resultado.encendidas == 4
    assert resultado.evaluados == 4
    assert len(resultado.muestra) == 4
    assert all(hasattr(a, "expediente") for a in resultado.muestra)


def test_se_reporta_conteo_distribucion_y_muestra():
    registros = (
        [proceso(identificador=f"L{i}") for i in range(3)]
        + [proceso(identificador=f"S{i}", modalidad="Selección abreviada subasta inversa")
           for i in range(2)]
        + [proceso(identificador=f"M{i}", modalidad="Mínima cuantía") for i in range(5)]
    )

    r = _calibrar(registros, dimension="modalidad_de_contratacion")

    assert r.evaluados == 10
    assert r.encendidas == 5          # las cinco competitivas
    assert r.distribucion == {
        "Licitación pública": 3,
        "Selección abreviada subasta inversa": 2,
    }
    assert round(r.tasa, 2) == 0.5


def test_la_muestra_se_recorta_y_es_repetible():
    # Dos calibraciones sobre los mismos datos tienen que mostrar lo mismo:
    # una muestra al azar haría irrepetible la revisión.
    registros = [proceso(identificador=f"CO1.REQ.{i}") for i in range(60)]

    una = _calibrar(registros)
    otra = _calibrar(registros)

    assert una.encendidas == 60
    assert len(una.muestra) == MUESTRA_POR_DEFECTO
    assert [a.identidad for a in una.muestra] == [a.identidad for a in otra.muestra]


def test_la_muestra_no_trae_alertas_repetidas():
    # Si la identidad determinista de la 2.2 se rompiera, aquí se vería antes
    # de que la cola se llenara de duplicadas.
    r = _calibrar([proceso(identificador=f"CO1.REQ.{i}") for i in range(30)])

    assert r.identidades_unicas == len(r.muestra)


# --------------------------------------- las tres distinciones que sostiene


def test_un_recorte_sin_resultados_no_es_un_fallo():
    # Diez procesos de mínima cuantía: la Regla no enciende en ninguno, y eso
    # es información, no una avería.
    r = _calibrar([proceso(identificador=f"M{i}", modalidad="Mínima cuantía")
                   for i in range(10)])

    assert r.evaluados == 10
    assert r.encendidas == 0
    assert r.sin_resultados
    assert "no es un fallo" in r.resumen()


def test_un_recorte_vacio_es_otra_cosa_y_se_distingue():
    # No hubo nada que mirar. Confundirlo con «no encendió» haría concluir que
    # la Regla no encuentra nada a partir de no haber mirado nada.
    with pytest.raises(RecorteVacio, match="no se le puso nada delante"):
        _calibrar([])


def test_una_regla_que_no_esta_en_calibracion_no_se_calibra():
    r = crear(MOMENTO)          # nace en borrador
    with pytest.raises(TransicionNoPermitida, match="borrador"):
        _calibrar([proceso()], regla=r)


# ------------------------------------------------------------- promover


def test_promover_exige_una_calibracion_delante():
    r = regla_calibrando()
    with pytest.raises(TransicionNoPermitida, match="sin una calibración"):
        promover(r, None)
    assert r.estado == CALIBRACION


def test_promover_con_la_calibracion_de_otra_regla_se_rechaza():
    r = regla_calibrando()
    resultado = _calibrar([proceso()], regla=r)
    ajena = ResultadoCalibracion(
        regla_codigo="plazo-expres", regla_version=1, recorte=RECORTE,
        evaluados=10, encendidas=1, distribucion={}, muestra=(),
        corrida_en=MOMENTO,
    )

    with pytest.raises(TransicionNoPermitida, match="plazo-expres"):
        promover(r, ajena)
    # La suya sí sirve.
    promover(r, resultado)
    assert r.estado == ACTIVA


def test_calibrar_deja_constancia_de_que_corrio():
    r = regla_calibrando()
    assert not r.corrio_en_calibracion

    _calibrar([proceso()], regla=r)

    assert r.corrio_en_calibracion


def test_una_regla_en_borrador_nunca_llega_a_activa_por_este_camino():
    # El invariante que protege la cola: sin pasar por calibración no hay
    # forma de activar.
    r = crear(MOMENTO)
    assert r.estado == BORRADOR
    with pytest.raises(TransicionNoPermitida):
        r.mover_a(ACTIVA)


# ------------------------------------------------------------- el recorte


def test_un_recorte_sin_motivo_se_rechaza():
    # Seis meses después la pregunta es «¿sobre qué se calibró y por qué ese
    # pedazo?». Sin respuesta, la calibración no se puede repetir.
    with pytest.raises(ValueError, match="no dice por qué"):
        Recorte(nombre="Boyacá", motivo="")


def test_un_resultado_no_puede_encender_mas_de_lo_que_evaluo():
    with pytest.raises(ValueError, match="no puede encender más veces"):
        ResultadoCalibracion(
            regla_codigo="x", regla_version=1, recorte=RECORTE,
            evaluados=3, encendidas=4, distribucion={}, muestra=(),
            corrida_en=MOMENTO,
        )


def test_sin_evaluados_la_tasa_es_desconocida_no_cero():
    r = ResultadoCalibracion(
        regla_codigo="x", regla_version=1, recorte=RECORTE,
        evaluados=0, encendidas=0, distribucion={}, muestra=(),
        corrida_en=MOMENTO,
    )
    assert r.tasa is None
    assert not r.sin_resultados
    assert "no trajo registros" in r.resumen()
