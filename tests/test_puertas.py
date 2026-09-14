"""Pruebas del semáforo.

En el escritorio el guardián era una persona leyendo antes de publicar. En un
servidor que corre solo a las cinco y media de la mañana no hay nadie leyendo,
y estas seis puertas son lo que la reemplaza. Si una se abre cuando no debía,
Vigía publica algo que está mal y no hay forma de despublicarlo.

Lo que se cuida aquí, en orden de gravedad:

1. Que la **puerta 3** —la de Tipacoque— detenga ante una errata que nadie ha
   mirado, y que se abra sola en cuanto alguien la mire.
2. Que la **puerta 6** detenga si una cédula llegó a `docs/`, y que NO detenga
   por un NIT, que es justo lo que hay que publicar.
3. Que ninguna puerta se salte porque otra esté en rojo.
"""

from __future__ import annotations

import json

import pytest

from vigia.puertas import (anotar_revisada, leer_revisadas, revisar)

TIPACOQUE = {
    "id_contrato": "CO1.PCCNTR.9762242",
    "entidad": "ALCALDÍA MUNICIPAL DE TIPACOQUE",
    "valor": 431340000000,
    "valor_probable": 431340000,
}
CVC = {
    "id_contrato": "CO1.PCCNTR.9762244",
    "entidad": "CVC",
    "valor": 99070693000,
    "valor_probable": 99070693,
}

REVISION_LIMPIA = {
    "conteos": {"imposibles": 1, "sin_razon_social": 5, "uniones": 102,
                "huerfanos": 0},
    "conteo_erratas": {"erratas": 0, "valor_erratas": 0},
    "erratas_x1000": [],
}


def _revision(erratas, conteo=None):
    return {
        "conteos": REVISION_LIMPIA["conteos"],
        "conteo_erratas": {"erratas": len(erratas) if conteo is None else conteo,
                           "valor_erratas": 0},
        "erratas_x1000": erratas,
    }


def _docs(tmp_path, **archivos):
    carpeta = tmp_path / "docs"
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, texto in archivos.items():
        destino = carpeta / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
    return carpeta


class TestLaPuertaDeTipacoque:
    """La puerta 3 no tiene umbral, y esa es toda su virtud.

    Tres banderas de este proyecto murieron por umbrales inventados. Aquí no
    se pregunta «¿las erratas mueven más del X % del valor?» sino «¿hay alguna
    que nadie haya mirado?». Eso no hay que sacárselo de la manga.
    """

    def test_una_errata_nueva_detiene(self, tmp_path):
        v = revisar(revision=_revision([TIPACOQUE]), docs=_docs(tmp_path))
        assert not v.verde
        assert v.detenida.numero == 3

    def test_el_motivo_nombra_la_entidad_y_el_presupuesto(self, tmp_path):
        v = revisar(revision=_revision([TIPACOQUE]), docs=_docs(tmp_path))
        assert "TIPACOQUE" in v.detenida.detalle
        assert "431340000" in v.detenida.detalle

    def test_revisada_por_una_persona_deja_pasar(self, tmp_path):
        v = revisar(revision=_revision([TIPACOQUE]), docs=_docs(tmp_path),
                    revisadas={"CO1.PCCNTR.9762242"})
        assert v.puertas[2].verde

    def test_revisar_una_no_abre_la_puerta_para_las_demas(self, tmp_path):
        # El riesgo real: alguien mira una, la anota, y cree que ya está.
        v = revisar(revision=_revision([TIPACOQUE, CVC]), docs=_docs(tmp_path),
                    revisadas={"CO1.PCCNTR.9762242"})
        assert not v.puertas[2].verde
        assert "CVC" in v.puertas[2].detalle

    def test_sin_erratas_la_puerta_esta_verde(self, tmp_path):
        v = revisar(revision=REVISION_LIMPIA, docs=_docs(tmp_path))
        assert v.puertas[2].verde

    def test_si_hay_mas_erratas_de_las_que_se_pueden_nombrar_detiene(self, tmp_path):
        # `revision.sql` corta la lista en 25 filas. Si el conteo total es
        # mayor, hay erratas que ni siquiera puedo enumerar — y no se puede
        # pedir que se revise lo que no se sabe nombrar.
        v = revisar(revision=_revision([TIPACOQUE], conteo=40),
                    docs=_docs(tmp_path), revisadas={"CO1.PCCNTR.9762242"})
        assert not v.puertas[2].verde
        assert "no puedo saber" in v.puertas[2].detalle

    def test_sin_revision_json_detiene_en_vez_de_suponer(self, tmp_path):
        # «No pude comprobarlo» nunca se traduce a «está bien».
        v = revisar(revision=None, docs=_docs(tmp_path))
        assert not v.puertas[2].verde


class TestLaPuertaDeLosDocumentos:
    def test_una_cedula_en_docs_detiene(self, tmp_path):
        docs = _docs(tmp_path, **{
            "index.html": "<p>CEDULA DE CIUDADANIA 1074521847</p>"})
        v = revisar(revision=REVISION_LIMPIA, docs=docs)
        assert not v.puertas[5].verde
        assert v.detenida.numero == 6

    def test_un_nit_no_detiene(self, tmp_path):
        # Es la mitad del punto: el NIT de una empresa se publica a propósito.
        # Una puerta que lo bloqueara abortaría cada publicación por hacer
        # justo lo que decidimos hacer.
        docs = _docs(tmp_path, **{"index.html": "<p>NIT 900555111</p>"})
        v = revisar(revision=REVISION_LIMPIA, docs=docs)
        assert v.puertas[5].verde

    def test_un_documento_enmascarado_no_detiene(self, tmp_path):
        docs = _docs(tmp_path, **{
            "index.html": "<p>Persona natural · C.C. •••••••847</p>"})
        v = revisar(revision=REVISION_LIMPIA, docs=docs)
        assert v.puertas[5].verde

    def test_se_revisan_las_subcarpetas(self, tmp_path):
        # La lista de archivos escrita a mano que había antes no miraba
        # `semanas/`. Una lista se queda vieja en silencio; un recorrido no.
        docs = _docs(tmp_path, **{
            "index.html": "<p>todo bien</p>",
            "semanas/2026-09-07.html": "<p>PASAPORTE 1074521847</p>"})
        v = revisar(revision=REVISION_LIMPIA, docs=docs)
        assert not v.puertas[5].verde

    def test_sin_carpeta_docs_detiene(self, tmp_path):
        v = revisar(revision=REVISION_LIMPIA, docs=tmp_path / "no-existe")
        assert not v.puertas[5].verde


class TestLasOtrasPuertas:
    def test_una_ingesta_fallida_detiene(self, tmp_path):
        v = revisar(revision=REVISION_LIMPIA, docs=_docs(tmp_path),
                    ingesta_ok=False)
        assert not v.puertas[0].verde
        assert v.detenida.numero == 1

    def test_un_periodo_anterior_incompleto_detiene(self, tmp_path):
        # Sin esto el boletín diría «cayó un 100 %» cuando lo que pasa es que
        # no tenemos datos de antes. Ya casi nos pasa una vez.
        boletin = {"anterior": {"desde": "2026-06-01", "hasta": "2026-06-07"},
                   "cobertura_temporal": {"primer_contrato": "2026-07-01",
                                          "ultimo_contrato": "2026-09-10"}}
        v = revisar(revision=REVISION_LIMPIA, docs=_docs(tmp_path),
                    boletin=boletin)
        assert not v.puertas[3].verde

    def test_un_post_demasiado_largo_detiene(self, tmp_path):
        v = revisar(revision=REVISION_LIMPIA, docs=_docs(tmp_path),
                    posts=["x" * 400])
        assert not v.puertas[4].verde

    def test_un_hilo_correcto_pasa(self, tmp_path):
        # La nota de cierre no es opcional: la barrera exige que el hilo diga
        # qué es esto —estadística descriptiva, no una imputación— y ese es
        # justo el tipo de cosa que se olvida con prisa.
        from vigia.publicacion import NOTA

        v = revisar(revision=REVISION_LIMPIA, docs=_docs(tmp_path),
                    posts=["Todo se compara por dia habil.", NOTA])
        assert v.puertas[4].verde


class TestElVeredicto:
    def test_se_evaluan_las_seis_aunque_la_primera_este_en_rojo(self, tmp_path):
        # Quien lea el informe quiere saber qué más había mal, no ir
        # descubriéndolo de a una corrida por día.
        docs = _docs(tmp_path, **{"index.html": "<p>CEDULA 1074521847</p>"})
        v = revisar(revision=_revision([TIPACOQUE]), docs=docs, ingesta_ok=False)
        assert len(v.puertas) == 6
        assert [p.numero for p in v.puertas] == [1, 2, 3, 4, 5, 6]
        assert sum(1 for p in v.puertas if not p.verde) >= 3

    def test_la_detenida_es_la_primera_en_rojo(self, tmp_path):
        v = revisar(revision=_revision([TIPACOQUE]), docs=_docs(tmp_path),
                    ingesta_ok=False)
        assert v.detenida.numero == 1

    def test_el_telegrama_en_rojo_dice_que_no_publico(self, tmp_path):
        v = revisar(revision=_revision([TIPACOQUE]), docs=_docs(tmp_path))
        mensaje = v.como_telegrama()
        assert "NO publiqué" in mensaje
        assert "Puerta 3" in mensaje

    def test_el_telegrama_en_verde_no_promete_haber_publicado_en_x(self, tmp_path):
        # Vigía nunca publica solo en X, y el mensaje no puede sugerir que sí.
        mensaje = revisar(revision=REVISION_LIMPIA,
                          docs=_docs(tmp_path)).como_telegrama()
        assert "para que lo leas" in mensaje


class TestElRegistroDeRevisadas:
    def test_lo_anotado_se_vuelve_a_leer(self, tmp_path):
        ruta = tmp_path / "erratas-revisadas.txt"
        anotar_revisada(ruta, "CO1.PCCNTR.9762242", "es errata x1000, tecla")
        assert "CO1.PCCNTR.9762242" in leer_revisadas(ruta)

    def test_los_comentarios_no_cuentan_como_identificadores(self, tmp_path):
        ruta = tmp_path / "r.txt"
        ruta.write_text("# CO1.PCCNTR.999 esto es un comentario\nCO1.X  2026-09-14\n",
                        encoding="utf-8")
        assert leer_revisadas(ruta) == {"CO1.X"}

    def test_un_archivo_que_no_existe_es_un_conjunto_vacio(self, tmp_path):
        assert leer_revisadas(tmp_path / "nada.txt") == set()
