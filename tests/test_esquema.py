"""Validación de esquema: falla ruidosamente ante un campo que desaparece."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.conftest import CAMPOS_CONTRATOS, registro
from vigia.crudo.memoria import RepositorioEnMemoria
from vigia.ingest.ciclo import ingerir
from vigia.ingest.datasets import CONTRATOS
from vigia.ingest.socrata import ErrorFuente
from vigia.schema.definiciones import EsquemaEsperado, EsquemaEsperadoAusente
from vigia.schema.novedades import Novedad, RepositorioNovedadesEnMemoria
from vigia.schema.validacion import EsquemaCambiado, ValidadorDeEsquema

MOMENTO = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
DESDE = date(2026, 8, 1)
HASTA = date(2026, 8, 2)


def esperado(campos) -> EsquemaEsperado:
    return EsquemaEsperado(
        dataset="contratos",
        id_socrata=CONTRATOS.id_socrata,
        capturado_en=date(2026, 9, 2),
        procedencia="https://fuente.falsa/api/views/jbjy-vk9h.json",
        campos=frozenset(campos),
    )


def validador(cliente, campos, repositorio=None, reloj=None):
    # `is None` y no `or`: un repositorio vacío define __len__ y es falsy, así
    # que `repositorio or ...` lo cambiaría por otro y la prueba miraría el
    # objeto equivocado.
    return ValidadorDeEsquema(
        cliente,
        esperado(campos),
        RepositorioNovedadesEnMemoria() if repositorio is None else repositorio,
        reloj=reloj or (lambda: MOMENTO),
    )


# --- El esquema capturado ---------------------------------------------------


def test_el_esquema_capturado_de_contratos_esta_completo():
    capturado = EsquemaEsperado.para("contratos")

    assert capturado.id_socrata == "jbjy-vk9h"
    assert len(capturado.campos) == 85
    assert "ultima_actualizacion" in capturado.campos
    assert "urlproceso" in capturado.campos


def test_un_dataset_sin_esquema_capturado_dice_como_capturarlo(tmp_path):
    with pytest.raises(EsquemaEsperadoAusente, match="--capturar"):
        EsquemaEsperado.para("procesos", directorio=tmp_path)


def test_el_esquema_se_escribe_ordenado_y_se_relee_igual(tmp_path: Path):
    original = esperado({"zeta", "alfa", "medio"})

    ruta = original.escribir(tmp_path)
    releido = EsquemaEsperado.desde_archivo(ruta)

    assert releido == original
    # Orden estable: el archivo se lee en un `diff`.
    assert json.loads(ruta.read_text(encoding="utf-8"))["campos"] == ["alfa", "medio", "zeta"]


# --- Comparación ------------------------------------------------------------


def test_un_esquema_intacto_no_produce_nada(crear_cliente):
    cliente, fuente = crear_cliente([], columnas=CAMPOS_CONTRATOS)

    resultado = validador(cliente, CAMPOS_CONTRATOS).validar(CONTRATOS)

    assert resultado.intacto
    assert len(fuente.peticiones_metadatos) == 1


def test_un_campo_esperado_ausente_detiene_el_ciclo_nombrandolo(crear_cliente):
    sin_valor = CAMPOS_CONTRATOS - {"valor_del_contrato"}
    cliente, _ = crear_cliente([], columnas=sin_valor)

    with pytest.raises(EsquemaCambiado) as fallo:
        validador(cliente, CAMPOS_CONTRATOS).validar(CONTRATOS)

    mensaje = str(fallo.value)
    assert "valor_del_contrato" in mensaje
    assert "contratos" in mensaje
    assert CONTRATOS.id_socrata in mensaje
    assert "2026-09-02" in mensaje


def test_varios_campos_ausentes_se_nombran_todos_en_orden_estable(crear_cliente):
    faltantes = {"valor_del_contrato", "documento_proveedor", "fecha_de_firma"}
    cliente, _ = crear_cliente([], columnas=CAMPOS_CONTRATOS - faltantes)

    with pytest.raises(EsquemaCambiado) as fallo:
        validador(cliente, CAMPOS_CONTRATOS).validar(CONTRATOS)

    mensaje = str(fallo.value)
    assert "3 campo(s)" in mensaje
    assert "documento_proveedor, fecha_de_firma, valor_del_contrato" in mensaje


def test_un_campo_nuevo_no_detiene_nada_y_queda_registrado(crear_cliente):
    cliente, _ = crear_cliente([], columnas=CAMPOS_CONTRATOS | {"valor_reintegro"})
    novedades = RepositorioNovedadesEnMemoria()

    resultado = validador(cliente, CAMPOS_CONTRATOS, novedades).validar(CONTRATOS)

    assert resultado.faltantes == ()
    assert resultado.novedades == ("valor_reintegro",)
    assert novedades.registradas() == {("contratos", "valor_reintegro"): (MOMENTO, MOMENTO)}


def test_con_faltante_y_novedad_manda_el_faltante_pero_la_novedad_se_registra(crear_cliente):
    # Un campo renombrado son las dos mitades del mismo hecho: hacen falta ambas.
    columnas = (CAMPOS_CONTRATOS - {"valor_del_contrato"}) | {"valor_del_contrato_cop"}
    cliente, _ = crear_cliente([], columnas=columnas)
    novedades = RepositorioNovedadesEnMemoria()

    with pytest.raises(EsquemaCambiado, match="valor_del_contrato"):
        validador(cliente, CAMPOS_CONTRATOS, novedades).validar(CONTRATOS)

    assert ("contratos", "valor_del_contrato_cop") in novedades.registradas()


def test_una_novedad_repetida_conserva_su_primera_deteccion(crear_cliente):
    cliente, _ = crear_cliente([], columnas=CAMPOS_CONTRATOS | {"valor_reintegro"})
    novedades = RepositorioNovedadesEnMemoria()
    despues = MOMENTO + timedelta(days=1)

    validador(cliente, CAMPOS_CONTRATOS, novedades, reloj=lambda: MOMENTO).validar(CONTRATOS)
    validador(cliente, CAMPOS_CONTRATOS, novedades, reloj=lambda: despues).validar(CONTRATOS)

    assert len(novedades) == 1
    assert novedades.registradas()[("contratos", "valor_reintegro")] == (MOMENTO, despues)


def test_validar_un_dataset_distinto_del_esquema_es_un_error_de_programacion(crear_cliente):
    from vigia.ingest.datasets import PROCESOS

    cliente, _ = crear_cliente([])

    with pytest.raises(ValueError, match="'contratos'"):
        validador(cliente, CAMPOS_CONTRATOS).validar(PROCESOS)


# --- Lectura de metadatos ---------------------------------------------------


def test_unos_metadatos_inalcanzables_detienen_el_ciclo(crear_cliente):
    cliente, _ = crear_cliente([], fallo_metadatos=500)

    with pytest.raises(ErrorFuente) as fallo:
        validador(cliente, CAMPOS_CONTRATOS).validar(CONTRATOS)

    mensaje = str(fallo.value)
    assert "500" in mensaje
    assert "contratos" in mensaje


def test_unos_metadatos_sin_lista_de_columnas_se_rechazan(crear_cliente):
    import httpx

    def responder(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "SECOP II"})

    http = httpx.Client(transport=httpx.MockTransport(responder))
    from vigia.ingest.socrata import ClienteSocrata

    cliente = ClienteSocrata(http, dominio="https://fuente.falsa")

    with pytest.raises(ErrorFuente, match="`columns`"):
        cliente.columnas(CONTRATOS)

    http.close()


def test_unos_metadatos_sin_ningun_campo_se_rechazan(crear_cliente):
    cliente, _ = crear_cliente([], columnas=[])

    with pytest.raises(ErrorFuente, match="no declaran ningún campo"):
        validador(cliente, CAMPOS_CONTRATOS).validar(CONTRATOS)


# --- Integración con el Ciclo ----------------------------------------------


def test_el_ciclo_valida_antes_de_pedir_el_primer_registro(crear_cliente):
    cliente, fuente = crear_cliente(
        [registro("row-1")], columnas=CAMPOS_CONTRATOS - {"valor_del_contrato"}
    )
    repositorio = RepositorioEnMemoria()

    with pytest.raises(EsquemaCambiado):
        ingerir(
            cliente=cliente,
            repositorio=repositorio,
            dataset=CONTRATOS,
            desde=DESDE,
            hasta=HASTA,
            validador=validador(cliente, CAMPOS_CONTRATOS),
        )

    # Ni una petición de datos, ni una fila escrita.
    assert fuente.peticiones == []
    assert len(repositorio) == 0


def test_con_el_esquema_intacto_el_ciclo_procede(crear_cliente):
    cliente, _ = crear_cliente([registro("row-1")], columnas=CAMPOS_CONTRATOS)
    repositorio = RepositorioEnMemoria()

    resumen = ingerir(
        cliente=cliente,
        repositorio=repositorio,
        dataset=CONTRATOS,
        desde=DESDE,
        hasta=HASTA,
        validador=validador(cliente, CAMPOS_CONTRATOS),
    )

    assert resumen.insertados == 1


def test_sin_validador_el_ciclo_no_consulta_metadatos(crear_cliente):
    cliente, fuente = crear_cliente([registro("row-1")])

    ingerir(
        cliente=cliente,
        repositorio=RepositorioEnMemoria(),
        dataset=CONTRATOS,
        desde=DESDE,
        hasta=HASTA,
    )

    assert fuente.peticiones_metadatos == []


# --- Novedad -----------------------------------------------------------------


def test_una_novedad_sin_zona_horaria_se_rechaza():
    with pytest.raises(ValueError, match="zona horaria"):
        Novedad(dataset="contratos", campo="x", detectado_en=datetime(2026, 9, 2, 12, 0))


def test_una_novedad_se_normaliza_a_utc():
    bogota = timezone(timedelta(hours=-5))
    novedad = Novedad(
        dataset="contratos", campo="x", detectado_en=datetime(2026, 9, 2, 7, 0, tzinfo=bogota)
    )

    assert novedad.detectado_en == MOMENTO


# --- Lo que el operador llega a ver ----------------------------------------


def test_las_novedades_llegan_al_resumen_del_ciclo(crear_cliente):
    cliente, _ = crear_cliente([registro("row-1")], columnas=CAMPOS_CONTRATOS | {"valor_reintegro"})

    resumen = ingerir(
        cliente=cliente,
        repositorio=RepositorioEnMemoria(),
        dataset=CONTRATOS,
        desde=DESDE,
        hasta=HASTA,
        validador=validador(cliente, CAMPOS_CONTRATOS),
    )

    assert resumen.novedades == ("valor_reintegro",)
    assert "valor_reintegro" in str(resumen)
    assert "sin revisar" in str(resumen)


def test_las_novedades_quedan_en_el_log(crear_cliente, caplog):
    import logging

    cliente, _ = crear_cliente([], columnas=CAMPOS_CONTRATOS | {"valor_reintegro"})

    with caplog.at_level(logging.WARNING, logger="vigia.schema.validacion"):
        validador(cliente, CAMPOS_CONTRATOS).validar(CONTRATOS)

    assert "valor_reintegro" in caplog.text


def test_un_fallo_al_registrar_una_novedad_no_detiene_el_ciclo(crear_cliente, caplog):
    import logging

    from vigia.crudo.repositorio import ErrorAlmacen

    class RepositorioRoto:
        def registrar(self, novedades):
            raise ErrorAlmacen("la tabla esquema_novedad no existe")

    cliente, _ = crear_cliente([registro("row-1")], columnas=CAMPOS_CONTRATOS | {"nuevo"})

    with caplog.at_level(logging.ERROR, logger="vigia.schema.validacion"):
        resumen = ingerir(
            cliente=cliente,
            repositorio=RepositorioEnMemoria(),
            dataset=CONTRATOS,
            desde=DESDE,
            hasta=HASTA,
            validador=validador(cliente, CAMPOS_CONTRATOS, RepositorioRoto()),
        )

    # Un campo nuevo no detiene nada: eso incluye no poder anotarlo.
    assert resumen.insertados == 1
    assert "el Ciclo continúa" in caplog.text


# --- La invariante que justifica toda la historia ---------------------------


def test_un_registro_al_que_le_faltan_claves_nulas_no_produce_faltantes(crear_cliente):
    # Socrata omite las claves nulas por fila. Este registro trae solo `:id` y
    # aun así el esquema está intacto: la comparación es contra lo DECLARADO
    # por el dataset, nunca contra las claves de una fila. Si alguien cambiara
    # eso, esta prueba es la que se cae.
    cliente, _ = crear_cliente([registro("row-1")], columnas=CAMPOS_CONTRATOS)

    resultado = validador(cliente, CAMPOS_CONTRATOS).validar(CONTRATOS)

    assert resultado.faltantes == ()


def test_las_columnas_internas_de_socrata_no_son_novedades(crear_cliente):
    # La plataforma añade `:@computed_region_*` por su cuenta al cruzar el
    # dataset con capas geográficas. No es un cambio del publicador.
    cliente, _ = crear_cliente(
        [], columnas=set(CAMPOS_CONTRATOS) | {":@computed_region_abcd_1234"}
    )

    resultado = validador(cliente, CAMPOS_CONTRATOS).validar(CONTRATOS)

    assert resultado.intacto


# --- Archivos de esquema en mal estado -------------------------------------


def test_un_esquema_esperado_ilegible_se_reporta_como_ausente(tmp_path):
    (tmp_path / "contratos.json").write_text("{esto no es json", encoding="utf-8")

    with pytest.raises(EsquemaEsperadoAusente, match="no se pudo leer"):
        EsquemaEsperado.para("contratos", tmp_path)


def test_un_esquema_esperado_sin_una_clave_se_reporta_como_ausente(tmp_path):
    (tmp_path / "contratos.json").write_text(
        json.dumps({"dataset": "contratos", "campos": ["a"]}), encoding="utf-8"
    )

    with pytest.raises(EsquemaEsperadoAusente, match="no se pudo leer"):
        EsquemaEsperado.para("contratos", tmp_path)


def test_un_esquema_esperado_sin_campos_se_rechaza(tmp_path):
    # Un esperado vacío no reporta faltantes nunca: apagaría la validación.
    (tmp_path / "contratos.json").write_text(
        json.dumps(
            {
                "dataset": "contratos",
                "id_socrata": "jbjy-vk9h",
                "capturado_en": "2026-09-02",
                "procedencia": "x",
                "campos": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EsquemaEsperadoAusente, match="no se pudo leer"):
        EsquemaEsperado.para("contratos", tmp_path)


def test_un_esquema_esperado_de_otro_dataset_se_rechaza(tmp_path):
    esperado(CAMPOS_CONTRATOS).escribir(tmp_path)
    (tmp_path / "procesos.json").write_bytes((tmp_path / "contratos.json").read_bytes())

    with pytest.raises(EsquemaEsperadoAusente, match="dice ser el esquema de 'contratos'"):
        EsquemaEsperado.para("procesos", tmp_path)


def test_la_escritura_es_atomica_y_no_deja_temporales(tmp_path):
    esperado(CAMPOS_CONTRATOS).escribir(tmp_path)

    assert [ruta.name for ruta in tmp_path.iterdir()] == ["contratos.json"]
