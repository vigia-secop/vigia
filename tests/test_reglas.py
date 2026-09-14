"""Motor de Reglas: versiones, identidad de Alerta y Expediente (2.1-2.3, 2.6)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from vigia.reglas.lenguaje import (
    NOTA_DE_EXPORTACION, PROHIBIDAS, limpio, revisar, revisar_archivo,
)
from vigia.reglas.modelo import (
    ACTIVA, BORRADOR, CALIBRACION, RETIRADA,
    Alerta, Expediente, ExpedienteIncompleto, Regla, ReglaNoModificable,
    TopeNormativo, TransicionNoPermitida, VersionDeRegla, emitir,
)

MOMENTO = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
CONSULTA = datetime(2026, 9, 5, 11, 30, tzinfo=timezone.utc)


def regla_con_version(umbral=1):
    r = Regla(
        codigo="oferente-unico",
        nombre="Oferente único",
        descripcion="Procesos competitivos que terminan con un solo proponente.",
    )
    r.nueva_version({"respuestas_maximas": umbral}, momento=MOMENTO)
    return r


# ------------------------------------------------- 2.1 reglas versionadas


def test_cambiar_un_umbral_crea_version_nueva_y_conserva_la_anterior():
    r = regla_con_version(umbral=1)
    primera = r.vigente

    r.nueva_version({"respuestas_maximas": 2}, momento=MOMENTO, nota="se abre a 2")

    assert len(r.versiones) == 2
    assert r.vigente.version == 2
    assert r.vigente.umbrales == {"respuestas_maximas": 2}
    # La anterior NO se tocó: es lo que permite explicar una Alerta vieja.
    assert r.version(1).umbrales == {"respuestas_maximas": 1}
    assert r.version(1) is primera


def test_una_version_no_se_puede_modificar():
    v = regla_con_version().vigente
    with pytest.raises(Exception):
        v.umbrales["respuestas_maximas"] = 99  # type: ignore[index]
    with pytest.raises(Exception):
        v.version = 7  # type: ignore[misc]


def test_versionar_lo_mismo_dos_veces_se_rechaza():
    # Un «cambio» que no cambia nada ensucia la historia y hace creer que se
    # calibró algo.
    r = regla_con_version(umbral=1)
    with pytest.raises(ReglaNoModificable, match="idénticos"):
        r.nueva_version({"respuestas_maximas": 1}, momento=MOMENTO)


def test_una_regla_sin_umbrales_no_es_una_regla():
    with pytest.raises(ValueError, match="no tiene umbrales"):
        VersionDeRegla(codigo="x", version=1, umbrales={}, creada_en=MOMENTO)


def test_los_cuatro_estados_y_sus_transiciones():
    r = regla_con_version()
    assert r.estado == BORRADOR

    r.mover_a(CALIBRACION)
    assert r.estado == CALIBRACION

    r.corrio_en_calibracion = True
    r.mover_a(ACTIVA)
    r.mover_a(RETIRADA)
    # De retirada no se sale.
    with pytest.raises(TransicionNoPermitida):
        r.mover_a(ACTIVA)


def test_una_regla_en_borrador_no_puede_activarse():
    # El corazón de la 2.5: inundar la cola con una bandera sin calibrar quema
    # la credibilidad una sola vez.
    r = regla_con_version()
    with pytest.raises(TransicionNoPermitida, match="«borrador» a «activa»"):
        r.mover_a(ACTIVA)


def test_una_regla_que_nunca_corrio_en_calibracion_no_puede_activarse():
    r = regla_con_version()
    r.mover_a(CALIBRACION)
    with pytest.raises(TransicionNoPermitida, match="nunca en calibración"):
        r.mover_a(ACTIVA)


def test_un_tope_normativo_lleva_fecha_y_fuente():
    tope = TopeNormativo(
        concepto="menor cuantia",
        ambito="entidad presupuesto medio",
        valor=Decimal("280000000"),
        unidad="COP",
        vigente_desde=date(2026, 1, 1),
        fuente="Ley 1150 de 2007, art. 2",
    )
    assert tope.clave == "menor cuantia|entidad presupuesto medio"


def test_un_tope_sin_fuente_se_rechaza():
    # Un número normativo que nadie puede rastrear no se puede defender.
    with pytest.raises(ValueError, match="sin fuente"):
        TopeNormativo(
            concepto="menor cuantia", ambito="x", valor=Decimal("1"),
            unidad="COP", vigente_desde=date(2026, 1, 1), fuente="",
        )


# ---------------------------------------------- 2.2 identidad de la alerta


def _emitir(regla, version, disparadores=None, registro="CO1.REQ.1"):
    return emitir(
        regla, version,
        id_registro_fuente=registro,
        dataset="procesos",
        valores_disparadores=disparadores or {"respuestas": 1, "invitados": 14},
        consultado_en=CONSULTA,
        momento=MOMENTO,
        url_proceso="https://community.secop.gov.co/…",
    )


def test_evaluar_dos_veces_produce_una_sola_alerta():
    r = regla_con_version()
    una = _emitir(r, r.vigente)
    otra = _emitir(r, r.vigente)

    assert una.identidad == otra.identidad


def test_la_hora_de_emision_no_entra_en_la_identidad():
    # Es el error del `:id` de Socrata, otra vez: una identidad que cambia
    # entre corridas no identifica nada.
    r = regla_con_version()
    una = _emitir(r, r.vigente)
    tarde = Alerta(expediente=una.expediente, emitida_en=datetime(2027, 1, 1, tzinfo=timezone.utc))

    assert una.identidad == tarde.identidad


def test_una_version_nueva_de_regla_produce_una_alerta_distinta():
    r = regla_con_version(umbral=1)
    antes = _emitir(r, r.vigente)
    r.nueva_version({"respuestas_maximas": 2}, momento=MOMENTO)
    despues = _emitir(r, r.vigente)

    assert antes.identidad != despues.identidad


def test_valores_disparadores_distintos_dan_alertas_distintas():
    r = regla_con_version()
    una = _emitir(r, r.vigente, {"respuestas": 1})
    otra = _emitir(r, r.vigente, {"respuestas": 0})

    assert una.identidad != otra.identidad


def test_el_orden_de_los_disparadores_no_cambia_la_identidad():
    r = regla_con_version()
    una = _emitir(r, r.vigente, {"respuestas": 1, "invitados": 14})
    otra = _emitir(r, r.vigente, {"invitados": 14, "respuestas": 1})

    assert una.identidad == otra.identidad


def test_un_decimal_y_su_texto_dan_la_misma_identidad():
    # El mismo valor leído de PostgreSQL y de JSON no es el mismo objeto de
    # Python. Si la identidad dependiera de eso, reprocesar duplicaría.
    r = regla_con_version()
    una = _emitir(r, r.vigente, {"valor": Decimal("1000.00")})
    otra = _emitir(r, r.vigente, {"valor": Decimal("1000")})

    assert una.identidad == otra.identidad


# ------------------------------------------------------ 2.3 el expediente


def test_el_expediente_trae_todo_lo_que_hay_que_defender():
    r = regla_con_version()
    a = _emitir(r, r.vigente)
    e = a.expediente

    assert e.id_registro_fuente == "CO1.REQ.1"
    assert e.dataset == "procesos"
    assert e.regla_codigo == "oferente-unico"
    assert e.regla_version == 1
    assert e.umbral_aplicado == {"respuestas_maximas": 1}
    assert e.valores_disparadores == {"respuestas": 1, "invitados": 14}
    assert e.consultado_en == CONSULTA
    assert e.url_proceso.startswith("https://community.secop.gov.co")


@pytest.mark.parametrize(
    "quitar",
    ["id_registro_fuente", "dataset", "regla_codigo", "umbral_aplicado",
     "valores_disparadores", "consultado_en"],
)
def test_sin_un_campo_del_expediente_la_alerta_no_se_crea(quitar):
    campos = dict(
        id_registro_fuente="CO1.REQ.1", dataset="procesos",
        regla_codigo="oferente-unico", regla_version=1,
        umbral_aplicado={"respuestas_maximas": 1},
        valores_disparadores={"respuestas": 1},
        consultado_en=CONSULTA,
    )
    campos[quitar] = None if quitar == "consultado_en" else type(campos[quitar])()

    with pytest.raises(ExpedienteIncompleto, match=quitar):
        Expediente(**campos)


def test_el_expediente_admite_no_tener_enlace():
    # No todos los registros traen `urlproceso`. Exigirlo dejaría fuera
    # Alertas legítimas; por eso es el único campo opcional.
    e = Expediente(
        id_registro_fuente="CO1.REQ.1", dataset="procesos",
        regla_codigo="x", regla_version=1, umbral_aplicado={"a": 1},
        valores_disparadores={"b": 2}, consultado_en=CONSULTA,
    )
    assert e.url_proceso is None


def test_emitir_con_una_version_de_otra_regla_se_rechaza():
    r = regla_con_version()
    otra = Regla(codigo="plazo-expres", nombre="Plazo exprés", descripcion="…")
    otra.nueva_version({"dias": 1}, momento=MOMENTO)

    with pytest.raises(ValueError, match="la versión es de"):
        _emitir(r, otra.vigente)


# --------------------------------------------- 2.6 vocabulario prohibido


@pytest.mark.parametrize("palabra", ["irregular", "corrupto", "fraude", "ilegal"])
def test_las_cuatro_palabras_que_nombra_la_historia_se_detectan(palabra):
    assert revisar(f"el contrato presenta un caso {palabra} en la entidad")


def test_se_detectan_con_tilde_y_en_mayusculas():
    assert revisar("SE DETECTÓ CORRUPCIÓN")
    assert revisar("hay irregularidades")


def test_una_frase_correcta_pasa():
    assert limpio(
        "Este proceso presenta un indicador que vale la pena revisar: "
        "14 invitados y una sola respuesta."
    )


def test_la_nota_de_exportacion_existe_y_dice_que_no_es_imputacion():
    assert "no constituyen imputación" in NOTA_DE_EXPORTACION.lower()
    assert limpio(NOTA_DE_EXPORTACION)


def test_ningun_texto_de_cara_al_usuario_acusa_a_nadie():
    """LA PRUEBA QUE IMPORTA: recorre el código de verdad, no una lista.

    Una norma escrita en un documento se erosiona; una prueba que recorre los
    archivos falla el día que alguien escribe la palabra.
    """
    raiz = Path(__file__).resolve().parent.parent / "vigia"
    hallazgos = []
    for archivo in sorted(raiz.rglob("*.py")):
        for numero, palabra, linea in revisar_archivo(archivo):
            hallazgos.append(f"{archivo.name}:{numero} «{palabra}» → {linea[:70]}")

    assert not hallazgos, "texto acusatorio:\n" + "\n".join(hallazgos)


def test_la_prueba_de_vocabulario_encuentra_de_verdad(tmp_path):
    # Una prueba que no puede fallar no prueba nada: se comprueba que el
    # detector encuentra algo cuando lo hay.
    falso = tmp_path / "malo.py"
    falso.write_text('print("contrato irregular")\n', encoding="utf-8")

    assert revisar_archivo(falso)


# ------------------------------------------------ 2.4 bandera de oferente unico
#
# Los casos salen de la medicion sobre 9 942 procesos adjudicados de la base
# real (2026-09-05), no de un supuesto. Ver el docstring de `oferente_unico.py`.

from vigia.reglas.oferente_unico import (  # noqa: E402
    CODIGO, crear, embudo, es_competitiva, evaluar, umbrales_iniciales,
)


def proceso(**campos):
    base = {
        "id_del_proceso": "CO1.REQ.10884642",
        "adjudicado": "Si",
        "modalidad_de_contratacion": "Licitación pública",
        "proveedores_invitados": "14",
        "proveedores_con_invitacion": "14",
        "visualizaciones_del": "77",
        "proveedores_que_manifestaron": "0",
        "respuestas_al_procedimiento": "1",
        "respuestas_externas": "0",
        "conteo_de_respuestas_a_ofertas": "1",
        "proveedores_unicos_con": "1",
        "numero_de_lotes": "0",
        "urlproceso": {"url": "https://community.secop.gov.co/…"},
    }
    base.update(campos)
    return base


def _evaluar(fila, regla=None):
    r = regla or crear(MOMENTO)
    return evaluar(fila, regla=r, version=r.vigente,
                   consultado_en=CONSULTA, momento=MOMENTO)


def test_un_proceso_competitivo_con_un_solo_proponente_enciende():
    a = _evaluar(proceso())

    assert a is not None
    assert a.expediente.regla_codigo == CODIGO
    assert a.expediente.valores_disparadores["proveedores_unicos_con"] == 1


def test_una_modalidad_no_competitiva_no_enciende():
    # Tercer criterio de aceptación, y la razón está medida: mínima cuantía,
    # contratación directa y régimen especial son 7 766 de los 9 942 procesos
    # adjudicados. Sin este filtro, el 78 % de las alertas serían modalidades
    # donde una sola oferta es el desenlace esperado.
    for modalidad in ("Mínima cuantía", "Contratación Directa (con ofertas)",
                      "Contratación régimen especial (con ofertas)"):
        assert _evaluar(proceso(modalidad_de_contratacion=modalidad)) is None


def test_un_proceso_no_adjudicado_no_enciende():
    # La primera fila que miré de la fuente traía TODO el embudo en cero y el
    # proceso todavía abierto. Sin esta condición, la bandera marcaría cada
    # proceso publicado del país por no haber recibido ofertas... todavía.
    assert _evaluar(proceso(adjudicado="No")) is None


def test_con_mas_proponentes_que_el_umbral_no_enciende():
    assert _evaluar(proceso(proveedores_unicos_con="2")) is None


def test_sin_el_contador_no_se_inventa_una_alerta():
    # 8 de los 9 942 adjudicados llegan sin el dato. Emitir igual sería
    # afirmar algo que la fuente no dice.
    assert _evaluar(proceso(proveedores_unicos_con=None)) is None
    assert _evaluar(proceso(proveedores_unicos_con="")) is None


def test_el_expediente_registra_el_embudo_completo():
    # Segundo criterio de aceptación, literal: invitados, manifestaciones,
    # respuestas, proveedores únicos y ganadores.
    a = _evaluar(proceso())
    d = a.expediente.valores_disparadores

    for campo in ("proveedores_invitados", "visualizaciones_del",
                  "proveedores_que_manifestaron", "respuestas_al_procedimiento",
                  "proveedores_unicos_con", "numero_de_lotes"):
        assert campo in d, campo
    assert d["proveedores_invitados"] == 14
    assert d["visualizaciones_del"] == 77
    # Este llega en cero en TODOS los casos medidos. Va igual, para que quien
    # revise vea que la fuente no lo pobla.
    assert d["proveedores_que_manifestaron"] == 0


def test_el_expediente_lleva_el_enlace_del_secop():
    a = _evaluar(proceso())
    assert a.expediente.url_proceso.startswith("https://community.secop.gov.co")


def test_un_proceso_sin_enlace_igual_emite():
    a = _evaluar(proceso(urlproceso=None))
    assert a is not None and a.expediente.url_proceso is None


def test_la_modalidad_se_compara_sin_tildes_ni_mayusculas():
    # La fuente escribe «Selección Abreviada de Menor Cuantía» y
    # «Seleccion Abreviada Menor Cuantia» en el mismo campo.
    competitivas = umbrales_iniciales()["modalidades_competitivas"]
    assert es_competitiva("SELECCION ABREVIADA DE MENOR CUANTIA", competitivas)
    assert es_competitiva("  Licitacion   publica  ", competitivas)
    assert not es_competitiva("Mínima cuantía", competitivas)


def test_el_embudo_lee_los_nueve_contadores():
    cuenta = embudo(proceso())
    assert len(cuenta) == 9
    assert cuenta["respuestas_al_procedimiento"] == 1


def test_la_regla_nace_en_borrador_y_no_se_puede_activar_de_una():
    r = crear(MOMENTO)
    assert r.estado == BORRADOR
    with pytest.raises(TransicionNoPermitida):
        r.mover_a(ACTIVA)


def test_los_umbrales_no_estan_escritos_en_el_codigo_de_la_regla():
    # 2.1: el valor que manda es el de la VERSIÓN. Cambiarlo en la versión
    # cambia el comportamiento sin tocar una línea de la Regla.
    r = crear(MOMENTO)
    assert _evaluar(proceso(proveedores_unicos_con="2"), regla=r) is None

    r.nueva_version({**umbrales_iniciales(), "proveedores_unicos_maximos": 2},
                    momento=MOMENTO, nota="se abre a dos")

    assert _evaluar(proceso(proveedores_unicos_con="2"), regla=r) is not None


def test_reevaluar_el_mismo_proceso_da_la_misma_alerta():
    r = crear(MOMENTO)
    assert _evaluar(proceso(), regla=r).identidad == _evaluar(proceso(), regla=r).identidad
