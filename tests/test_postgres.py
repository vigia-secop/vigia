"""Idempotencia y durabilidad verificadas contra PostgreSQL real.

La garantía de la capa cruda es de la llave primaria y de la transacción por
página, no del código Python. El doble en memoria replica la semántica de
conflicto, pero no puede distinguir un COMMIT de un ROLLBACK: solo el motor
demuestra eso.

Estas pruebas **borran filas**, así que corren contra `VIGIA_DSN_PRUEBAS` y
nunca contra `VIGIA_DSN`. Sin esa variable se omiten.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from tests.conftest import registro
from vigia.crudo.memoria import RepositorioEnMemoria
from vigia.crudo.modelo import RegistroCrudo, hash_contenido
from vigia.crudo.postgres import RepositorioPostgres, repositorio_postgres
from vigia.ingest.ciclo import ingerir
from vigia.ingest.datasets import CONTRATOS, DATASETS
from vigia.normalizado.proveedor import TIPO_GRUPO_PROVISIONAL

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.postgres

MOMENTO = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def _crudo(id_fila: str, **campos) -> RegistroCrudo:
    return RegistroCrudo.desde_respuesta(
        "contratos", registro(id_fila, **campos), MOMENTO,
        campos_identidad=CONTRATOS.campos_identidad,
    )


@pytest.fixture
def dsn() -> str:
    valor = os.environ.get("VIGIA_DSN_PRUEBAS")
    if not valor:
        pytest.skip(
            "sin VIGIA_DSN_PRUEBAS: estas pruebas borran filas y no corren "
            "contra la base de trabajo"
        )
    return valor


@pytest.fixture
def limpiar(dsn: str):
    def borrar() -> None:
        with psycopg.connect(dsn) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("DELETE FROM crudo_registro WHERE dataset = 'contratos'")
            conexion.commit()

    borrar()
    yield
    borrar()


@pytest.fixture
def repositorio(dsn: str, limpiar):
    with psycopg.connect(dsn) as conexion:
        yield RepositorioPostgres(conexion)


def _filas(dsn: str) -> int:
    """Cuenta desde una conexión nueva: lo no confirmado no se ve desde aquí."""
    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM crudo_registro WHERE dataset = 'contratos'")
        return cursor.fetchone()[0]


def test_una_pagina_nueva_entra_completa(repositorio, dsn):
    registros = [_crudo(f"row-{indice}", valor=str(indice)) for indice in range(3)]

    resultado = repositorio.guardar_pagina(registros)

    assert (resultado.insertados, resultado.duplicados) == (3, 0)
    assert resultado.vistos == 3
    assert _filas(dsn) == 3


def test_cada_pagina_queda_confirmada_por_si_sola(repositorio, dsn):
    # Leído desde otra conexión: si la página no se hubiera confirmado, este
    # conteo sería cero.
    repositorio.guardar_pagina([_crudo("row-1")])

    assert _filas(dsn) == 1


def test_reingerir_la_misma_pagina_no_inserta_nada(repositorio, dsn):
    registros = [_crudo(f"row-{indice}") for indice in range(3)]
    repositorio.guardar_pagina(registros)

    resultado = repositorio.guardar_pagina(registros)

    assert (resultado.insertados, resultado.duplicados) == (0, 3)
    assert _filas(dsn) == 3


def test_un_registro_repetido_dentro_de_la_pagina_se_cuenta_una_vez(repositorio, dsn):
    repetido = _crudo("row-1", valor="1")

    resultado = repositorio.guardar_pagina([repetido, repetido])

    assert (resultado.insertados, resultado.duplicados) == (1, 1)
    assert _filas(dsn) == 1


def test_un_contenido_distinto_para_el_mismo_id_entra_como_fila_nueva(repositorio, dsn):
    repositorio.guardar_pagina([_crudo("row-1", estado="En ejecución")])

    resultado = repositorio.guardar_pagina([_crudo("row-1", estado="Terminado")])

    assert resultado.insertados == 1
    assert _filas(dsn) == 2


def test_una_pagina_vacia_no_toca_la_base(repositorio, dsn):
    resultado = repositorio.guardar_pagina([])

    assert (resultado.insertados, resultado.duplicados) == (0, 0)
    assert _filas(dsn) == 0


def test_el_contenido_vuelve_de_jsonb_sin_perder_nada(repositorio, dsn):
    contenido = registro(
        "row-1",
        urlproceso={"url": "https://community.secop.gov.co/x"},
        departamento="Quindío",
        valor_del_contrato="8959088",
        anidado={"lista": [1, 2, {"a": None}]},
    )
    repositorio.guardar_pagina([
        RegistroCrudo.desde_respuesta(
            "contratos", contenido, MOMENTO,
            campos_identidad=CONTRATOS.campos_identidad,
        )
    ])

    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT contenido, consultado_en, hash_contenido FROM crudo_registro "
            "WHERE dataset = 'contratos'"
        )
        guardado, consultado_en, hash_guardado = cursor.fetchone()

    assert guardado == contenido
    assert consultado_en == MOMENTO
    # El sustento tiene que poder reverificarse desde la fila: recalcular el
    # hash sobre lo recuperado debe dar exactamente lo almacenado.
    assert hash_contenido(guardado) == hash_guardado


def test_postgres_y_memoria_cuentan_igual(repositorio):
    # Si estas dos divergen, el doble de las pruebas unitarias deja de valer.
    registros = [_crudo("row-1"), _crudo("row-1"), _crudo("row-2")]
    memoria = RepositorioEnMemoria()

    assert repositorio.guardar_pagina(registros) == memoria.guardar_pagina(registros)


def test_un_ciclo_abortado_conserva_las_paginas_ya_confirmadas(dsn, limpiar, crear_cliente):
    from datetime import date

    from vigia.ingest.socrata import ErrorFuente

    registros = [registro(f"row-{indice}") for indice in range(4)]
    cliente, _ = crear_cliente(registros, limite_pagina=2, fallos={2: 500})

    with repositorio_postgres(dsn) as repositorio:
        with pytest.raises(ErrorFuente):
            ingerir(
                cliente=cliente,
                repositorio=repositorio,
                dataset=CONTRATOS,
                desde=date(2026, 8, 1),
                hasta=date(2026, 8, 2),
            )

    # La primera página entró y quedó confirmada pese a que el Ciclo murió
    # después; la segunda no entró en absoluto.
    assert _filas(dsn) == 2


# --- Novedades de esquema ---------------------------------------------------


def _novedades_registradas(dsn: str) -> dict:
    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT campo, primera_deteccion, ultima_deteccion, revisada "
            "FROM esquema_novedad WHERE dataset = 'contratos' ORDER BY campo"
        )
        return {fila[0]: fila[1:] for fila in cursor.fetchall()}


@pytest.fixture
def novedades(dsn: str):
    from vigia.schema.postgres import RepositorioNovedadesPostgres

    def borrar() -> None:
        with psycopg.connect(dsn) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("DELETE FROM esquema_novedad WHERE dataset = 'contratos'")
            conexion.commit()

    borrar()
    with psycopg.connect(dsn) as conexion:
        yield RepositorioNovedadesPostgres(conexion)
    borrar()


def test_una_novedad_nueva_queda_registrada(novedades, dsn):
    from vigia.schema.novedades import Novedad

    novedades.registrar([Novedad("contratos", "valor_reintegro", MOMENTO)])

    registradas = _novedades_registradas(dsn)
    assert registradas["valor_reintegro"] == (MOMENTO, MOMENTO, False)


def test_una_novedad_repetida_conserva_la_primera_deteccion(novedades, dsn):
    from datetime import timedelta

    from vigia.schema.novedades import Novedad

    despues = MOMENTO + timedelta(days=1)
    novedades.registrar([Novedad("contratos", "valor_reintegro", MOMENTO)])

    novedades.registrar([Novedad("contratos", "valor_reintegro", despues)])

    primera, ultima, _ = _novedades_registradas(dsn)["valor_reintegro"]
    assert (primera, ultima) == (MOMENTO, despues)


def test_el_orden_de_llegada_de_los_ciclos_no_altera_el_registro(novedades, dsn):
    from datetime import timedelta

    from vigia.schema.novedades import Novedad

    despues = MOMENTO + timedelta(days=1)
    novedades.registrar([Novedad("contratos", "valor_reintegro", despues)])

    novedades.registrar([Novedad("contratos", "valor_reintegro", MOMENTO)])

    primera, ultima, _ = _novedades_registradas(dsn)["valor_reintegro"]
    # `LEAST`/`GREATEST`: la primera solo retrocede, la última solo avanza.
    assert (primera, ultima) == (MOMENTO, despues)


def test_registrar_una_lista_vacia_no_toca_la_base(novedades, dsn):
    novedades.registrar([])

    assert _novedades_registradas(dsn) == {}


def test_la_marca_de_revisada_es_del_equipo_y_el_sistema_no_la_pisa(novedades, dsn):
    from datetime import timedelta

    from vigia.schema.novedades import Novedad

    novedades.registrar([Novedad("contratos", "valor_reintegro", MOMENTO)])
    with psycopg.connect(dsn) as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE esquema_novedad SET revisada = true WHERE campo = 'valor_reintegro'"
            )
        conexion.commit()

    novedades.registrar([Novedad("contratos", "valor_reintegro", MOMENTO + timedelta(days=1))])

    assert _novedades_registradas(dsn)["valor_reintegro"][2] is True


# --- Marca de agua y registro de Ciclo (AD-4) -------------------------------


@pytest.fixture
def estado(dsn: str):
    from vigia.ingest.estado_postgres import RepositorioEstadoPostgres

    def borrar() -> None:
        with psycopg.connect(dsn) as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("DELETE FROM ciclo WHERE dataset = 'contratos'")
                cursor.execute("DELETE FROM ingesta_marca WHERE dataset = 'contratos'")
            conexion.commit()

    borrar()
    with psycopg.connect(dsn) as conexion:
        yield RepositorioEstadoPostgres(conexion)
    borrar()


def _marca_leida(dsn: str):
    """Lee la marca desde otra conexión: lo no confirmado no se ve desde aquí."""
    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute("SELECT fecha_hecho FROM ingesta_marca WHERE dataset = 'contratos'")
        fila = cursor.fetchone()
        return fila[0] if fila else None


def _ciclos_registrados(dsn: str):
    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT estado, cursor_entrada, cursor_salida, causa FROM ciclo "
            "WHERE dataset = 'contratos' ORDER BY id"
        )
        return cursor.fetchall()


def _registro(estado_ciclo, *, salida, entrada=None, causa=None, desde=None):
    from datetime import date, timedelta

    from vigia.ingest.estado import RegistroDeCiclo

    hasta = salida or date(2026, 9, 2)
    return RegistroDeCiclo(
        dataset="contratos",
        cursor_entrada=entrada,
        cursor_salida=salida,
        desde=desde or (hasta - timedelta(days=30)),
        hasta=hasta,
        estado=estado_ciclo,
        inicio=MOMENTO,
        fin=MOMENTO,
        causa=causa,
    )


def test_un_ciclo_completo_registra_y_avanza_la_marca(estado, dsn):
    from datetime import date

    from vigia.ingest.estado import EstadoCiclo

    estado.cerrar_ciclo(_registro(EstadoCiclo.COMPLETO, salida=date(2026, 9, 2)))

    assert _marca_leida(dsn) == date(2026, 9, 2)
    assert len(_ciclos_registrados(dsn)) == 1


def test_un_ciclo_fallido_registra_y_no_avanza_la_marca(estado, dsn):
    from datetime import date

    from vigia.ingest.estado import EstadoCiclo

    estado.cerrar_ciclo(_registro(EstadoCiclo.COMPLETO, salida=date(2026, 8, 20)))

    estado.cerrar_ciclo(
        _registro(
            EstadoCiclo.FALLIDO,
            salida=None,
            entrada=date(2026, 8, 20),
            causa="ErrorFuente: la fuente respondió 500",
        )
    )

    # La marca se quedó donde estaba, leída desde otra conexión.
    assert _marca_leida(dsn) == date(2026, 8, 20)
    registrados = _ciclos_registrados(dsn)
    assert len(registrados) == 2
    assert registrados[-1][0] == "fallido"
    assert "500" in registrados[-1][3]


def test_la_marca_no_retrocede_ante_un_reproceso_viejo(estado, dsn):
    from datetime import date

    from vigia.ingest.estado import EstadoCiclo

    estado.cerrar_ciclo(_registro(EstadoCiclo.COMPLETO, salida=date(2026, 9, 2)))

    estado.cerrar_ciclo(
        _registro(EstadoCiclo.COMPLETO, salida=date(2026, 3, 1), desde=date(2026, 1, 1))
    )

    assert _marca_leida(dsn) == date(2026, 9, 2)
    # El Ciclo viejo sí queda registrado: se hizo, y consta.
    assert len(_ciclos_registrados(dsn)) == 2


def test_sin_marca_previa_se_lee_none(estado):
    assert estado.marca("contratos") is None


def test_la_marca_vuelve_con_su_zona_horaria(estado, dsn):
    from datetime import date, timezone

    from vigia.ingest.estado import EstadoCiclo

    estado.cerrar_ciclo(_registro(EstadoCiclo.COMPLETO, salida=date(2026, 9, 2)))

    marca = estado.marca("contratos")
    assert marca.fecha_hecho == date(2026, 9, 2)
    assert marca.actualizada_en.tzinfo is not None
    assert marca.actualizada_en.astimezone(timezone.utc) == MOMENTO


def test_la_base_rechaza_un_ciclo_fallido_sin_causa(estado, dsn):
    # La invariante está en el motor, no solo en Python.
    from datetime import date

    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute(
                "INSERT INTO ciclo (dataset, desde, hasta, estado, inicio, fin) "
                "VALUES ('contratos', %s, %s, 'fallido', %s, %s)",
                (date(2026, 8, 1), date(2026, 9, 2), MOMENTO, MOMENTO),
            )


def test_un_ciclo_completo_de_punta_a_punta_persiste_marca_y_registro(dsn, limpiar, crear_cliente):
    from datetime import date

    from vigia.ingest.ciclo import ejecutar_ciclo
    from vigia.ingest.estado_postgres import repositorio_estado_postgres

    with psycopg.connect(dsn) as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM ciclo WHERE dataset = 'contratos'")
            cursor.execute("DELETE FROM ingesta_marca WHERE dataset = 'contratos'")
        conexion.commit()

    contratos = [
        registro(f"row-{i}", fecha_de_firma="2026-08-15T00:00:00.000") for i in range(3)
    ]
    cliente, _ = crear_cliente(contratos)

    with repositorio_postgres(dsn) as crudo, repositorio_estado_postgres(dsn) as estado_pg:
        ciclo = ejecutar_ciclo(
            cliente=cliente,
            repositorio=crudo,
            estado=estado_pg,
            dataset=CONTRATOS,
            desde=date(2026, 8, 1),
            hasta=date(2026, 9, 2),
            ventana_dias=30,
        )

    assert ciclo.insertados == 3
    assert _filas(dsn) == 3
    assert _marca_leida(dsn) == date(2026, 9, 2)
    assert len(_ciclos_registrados(dsn)) == 1

    with psycopg.connect(dsn) as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM ciclo WHERE dataset = 'contratos'")
            cursor.execute("DELETE FROM ingesta_marca WHERE dataset = 'contratos'")
        conexion.commit()


def test_la_marca_se_confirma_en_el_orden_real_de_uso(dsn, estado):
    """Leer la marca y luego cerrar el Ciclo, sin cerrar la conexión.

    Es el orden que sigue `ejecutar_ciclo`. Si la lectura dejara una
    transacción implícita abierta, el `transaction()` de `cerrar_ciclo`
    degradaría a SAVEPOINT y nada quedaría confirmado hasta cerrar la conexión:
    un fallo posterior haría ROLLBACK y borraría el registro.
    """
    from datetime import date

    from vigia.ingest.estado import EstadoCiclo

    estado.marca("contratos")  # abre —y tiene que cerrar— su propia transacción

    estado.cerrar_ciclo(_registro(EstadoCiclo.COMPLETO, salida=date(2026, 9, 2)))

    # Leído desde otra conexión, con la primera todavía abierta.
    assert _marca_leida(dsn) == date(2026, 9, 2)
    assert len(_ciclos_registrados(dsn)) == 1


def test_cada_conteo_del_ciclo_llega_a_su_propia_columna(dsn, estado):
    """Todos los valores distintos: si dos parámetros se cruzan, se nota."""
    from datetime import date

    from vigia.ingest.estado import EstadoCiclo, RegistroDeCiclo

    estado.cerrar_ciclo(
        RegistroDeCiclo(
            dataset="contratos",
            cursor_entrada=date(2026, 8, 20),
            cursor_salida=date(2026, 9, 2),
            desde=date(2026, 7, 21),
            hasta=date(2026, 9, 2),
            estado=EstadoCiclo.COMPLETO,
            inicio=MOMENTO,
            fin=MOMENTO,
            paginas=7,
            vistos=31,
            insertados=19,
            duplicados=12,
            recuperados_por_solapamiento=5,
            en_borde_de_ventana=3,
            sin_fecha_de_hecho=2,
            novedades=("valor_reintegro", "otro_campo"),
            ventana_dias=30,
            desde_derivado=True,
        )
    )

    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT cursor_entrada, cursor_salida, desde, hasta, paginas, vistos, "
            "insertados, duplicados, recuperados_por_solapamiento, "
            "en_borde_de_ventana, sin_fecha_de_hecho, huerfanos, novedades, "
            "ventana_dias, desde_derivado FROM ciclo WHERE dataset = 'contratos'"
        )
        fila = cursor.fetchone()

    assert fila == (
        date(2026, 8, 20),
        date(2026, 9, 2),
        date(2026, 7, 21),
        date(2026, 9, 2),
        7,
        31,
        19,
        12,
        5,
        3,
        2,
        None,
        ["valor_reintegro", "otro_campo"],
        30,
        True,
    )


def test_actualizada_en_se_refresca_aunque_la_marca_no_avance(dsn, estado):
    from datetime import date, timedelta

    from vigia.ingest.estado import EstadoCiclo

    estado.cerrar_ciclo(_registro(EstadoCiclo.COMPLETO, salida=date(2026, 9, 2)))
    despues = MOMENTO + timedelta(days=1)

    # Mismo cursor de salida: la fecha no avanza, pero el Ciclo sí ocurrió.
    estado.cerrar_ciclo(
        RegistroDeCicloIgual(salida=date(2026, 9, 2), fin=despues)
    )

    marca = estado.marca("contratos")
    assert marca.fecha_hecho == date(2026, 9, 2)
    assert marca.actualizada_en == despues


def RegistroDeCicloIgual(*, salida, fin):
    from datetime import date, timedelta

    from vigia.ingest.estado import EstadoCiclo, RegistroDeCiclo

    return RegistroDeCiclo(
        dataset="contratos",
        cursor_entrada=salida,
        cursor_salida=salida,
        desde=salida - timedelta(days=30),
        hasta=salida,
        estado=EstadoCiclo.COMPLETO,
        inicio=MOMENTO,
        fin=fin,
    )


def test_la_base_rechaza_conteos_incoherentes(estado, dsn):
    from datetime import date

    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute(
                "INSERT INTO ciclo (dataset, cursor_salida, desde, hasta, estado, "
                "inicio, fin, vistos, insertados, duplicados) "
                "VALUES ('contratos', %s, %s, %s, 'completo', %s, %s, 10, 1, 1)",
                (date(2026, 9, 2), date(2026, 8, 1), date(2026, 9, 2), MOMENTO, MOMENTO),
            )


def test_la_base_rechaza_un_ciclo_completo_sin_cursor_de_salida(estado, dsn):
    from datetime import date

    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute(
                "INSERT INTO ciclo (dataset, desde, hasta, estado, inicio, fin) "
                "VALUES ('contratos', %s, %s, 'completo', %s, %s)",
                (date(2026, 8, 1), date(2026, 9, 2), MOMENTO, MOMENTO),
            )


# ----------------------------------------------- capa normalizada (1.4)


@pytest.fixture
def limpiar_normalizado(dsn: str):
    def borrar() -> None:
        with psycopg.connect(dsn) as conexion:
            with conexion.cursor() as cursor:
                # `contrato` primero: tiene clave foránea contra `proceso`.
                cursor.execute("DELETE FROM contrato")
                cursor.execute("DELETE FROM proceso")
                cursor.execute("DELETE FROM crudo_registro")
            conexion.commit()

    borrar()
    yield
    borrar()


def _sembrar_crudo(dsn: str, dataset: str, filas: list[dict]) -> None:
    from psycopg.types.json import Jsonb

    from vigia.crudo.modelo import RegistroCrudo

    momento = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        for indice, contenido in enumerate(filas):
            registro = RegistroCrudo.desde_respuesta(
                dataset=dataset,
                contenido={":id": f"{dataset}-{indice}", **contenido},
                consultado_en=momento,
                campos_identidad=DATASETS[dataset].campos_identidad,
            )
            cursor.execute(
                "INSERT INTO crudo_registro VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (
                    registro.dataset,
                    registro.id_fila_fuente,
                    registro.hash_contenido,
                    Jsonb(dict(registro.contenido)),
                    registro.consultado_en,
                ),
            )
        conexion.commit()


def _normalizar(dsn: str):
    """Corre la tubería REAL, la misma que `python -m vigia.normalizado`.

    Antes esta función replicaba los pasos a mano, y por eso no guardaba
    proveedores cuando llegó la 1.5: una copia de la tubería en las pruebas se
    queda atrás en cuanto la de verdad cambia. Ahora llama a `ejecutar`.
    """
    from vigia.normalizado.__main__ import ejecutar

    momento = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    return ejecutar(dsn, momento=momento).resumen


def test_el_cruce_completo_funciona_contra_el_motor_real(dsn, limpiar_normalizado):
    _sembrar_crudo(
        dsn,
        "procesos",
        [
            {
                "id_del_proceso": "CO1.REQ.3544146",
                "id_adjudicacion": "CO1.AWD.unico",
                "id_del_portafolio": "CO1.BDOS.3452554",
                "referencia_del_proceso": "CPS-3548-2022",
            }
        ]
        # El proceso de 460 lotes: 21 filas iguales salvo el adjudicatario.
        #
        # Cada una trae su `id_adjudicacion`, como en la fuente real: desde el
        # cambio de llave del 2026-09-04 ESE es el segundo componente de la
        # identidad de la fila cruda. Sin él las 21 serían la misma fila y la
        # capa cruda se quedaría con una sola —lo que esta prueba detectó el
        # día del cambio—.
        + [
            {
                "id_del_proceso": "CO1.REQ.10772032",
                "id_adjudicacion": f"CO1.AWD.{i}",
                "id_del_portafolio": "CO1.BDOS.10494164",
                "nombre_del_proveedor": f"ADJUDICATARIO {i}",
            }
            for i in range(21)
        ],
    )
    _sembrar_crudo(
        dsn,
        "contratos",
        [
            {"id_contrato": "C-enlazado", "proceso_de_compra": "CO1.BDOS.3452554"},
            {"id_contrato": "C-huerfano", "proceso_de_compra": "CO1.BDOS.nadie"},
            {"id_contrato": "C-sin-llave"},
        ],
    )

    resumen = _normalizar(dsn)

    assert resumen.procesos_leidos == 22
    assert resumen.procesos_normalizados == 2
    assert resumen.procesos_colapsados == 20
    assert resumen.enlazados == 1
    assert resumen.huerfanos == 1
    assert resumen.sin_llave_de_cruce == 1

    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT id_del_proceso FROM contrato WHERE id_contrato = 'C-enlazado'"
        )
        assert cursor.fetchone()[0] == "CO1.REQ.3544146"
        # El huérfano se conserva y es consultable: FR-2 prohíbe descartarlo.
        cursor.execute(
            "SELECT count(*) FROM contrato "
            "WHERE id_del_proceso IS NULL AND proceso_de_compra IS NOT NULL"
        )
        assert cursor.fetchone()[0] == 1


def test_normalizar_dos_veces_deja_la_misma_base(dsn, limpiar_normalizado):
    # La capa normalizada es una lectura derivada, no un registro histórico:
    # rehacerla desde el mismo crudo tiene que dar exactamente lo mismo.
    _sembrar_crudo(
        dsn,
        "procesos",
        [{"id_del_proceso": "CO1.REQ.1", "id_del_portafolio": "CO1.BDOS.1"}],
    )
    _sembrar_crudo(
        dsn, "contratos", [{"id_contrato": "C-1", "proceso_de_compra": "CO1.BDOS.1"}]
    )

    primero = _normalizar(dsn)
    segundo = _normalizar(dsn)

    assert primero == segundo
    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM contrato")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM proceso")
        assert cursor.fetchone()[0] == 1


def test_solo_se_normaliza_la_version_mas_reciente_del_crudo(dsn, limpiar_normalizado):
    # La capa cruda guarda TODAS las versiones. Normalizar la vieja sobre la
    # nueva dejaría la capa normalizada mostrando el pasado.
    from psycopg.types.json import Jsonb

    from vigia.crudo.modelo import RegistroCrudo

    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        for dia, valor in [(1, "100"), (2, "999")]:
            registro = RegistroCrudo.desde_respuesta(
                dataset="contratos",
                contenido={
                    ":id": "misma-fila",
                    "id_contrato": "C-1",
                    "valor_del_contrato": valor,
                },
                consultado_en=datetime(2026, 9, dia, tzinfo=timezone.utc),
                campos_identidad=CONTRATOS.campos_identidad,
            )
            cursor.execute(
                "INSERT INTO crudo_registro VALUES (%s,%s,%s,%s,%s)",
                (
                    registro.dataset,
                    registro.id_fila_fuente,
                    registro.hash_contenido,
                    Jsonb(dict(registro.contenido)),
                    registro.consultado_en,
                ),
            )
        conexion.commit()

    resumen = _normalizar(dsn)

    assert resumen.contratos_normalizados == 1
    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute("SELECT valor FROM contrato WHERE id_contrato = 'C-1'")
        assert cursor.fetchone()[0] == 999


def test_la_base_rechaza_un_enlace_sin_llave_de_cruce(dsn, limpiar_normalizado):
    # La invariante no se confía a Python: la impone el motor.
    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "INSERT INTO proceso (id_del_proceso, id_fila_fuente, hash_contenido, "
            "normalizado_en) VALUES ('CO1.REQ.1','f','h',now())"
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute(
                "INSERT INTO contrato (id_contrato, proceso_de_compra, id_del_proceso,"
                " id_fila_fuente, hash_contenido, normalizado_en) "
                "VALUES ('C-1', NULL, 'CO1.REQ.1', 'f', 'h', now())"
            )


def test_la_base_rechaza_un_contrato_enlazado_a_un_proceso_inexistente(
    dsn, limpiar_normalizado
):
    # Clave foránea: un enlace a un Proceso que no está es un enlace inventado.
    with psycopg.connect(dsn) as conexion, conexion.cursor() as cursor:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            cursor.execute(
                "INSERT INTO contrato (id_contrato, proceso_de_compra, id_del_proceso,"
                " id_fila_fuente, hash_contenido, normalizado_en) "
                "VALUES ('C-1', 'CO1.BDOS.1', 'CO1.REQ.fantasma', 'f', 'h', now())"
            )


# ---------------------------------------------------------------------------
# Migración 005: la capa cruda pasa a llave de negocio.
# `sprint-change-proposal-2026-09-04.md`. Estas pruebas van contra el motor
# real porque lo que se está probando ES el motor colapsando por llave
# primaria; un doble en memoria probaría el doble.
# ---------------------------------------------------------------------------


@pytest.fixture
def rellave_limpia(dsn):
    """Deja las tablas de la 005 vacías antes y después."""
    from vigia.crudo import rellave as _rellave

    def _limpiar():
        with psycopg.connect(dsn) as cx, cx.cursor() as cur:
            cur.execute("TRUNCATE crudo_registro, crudo_registro_rellave")
            cx.commit()

    _limpiar()
    yield _rellave
    _limpiar()


def _fila_cruda(cur, dataset, id_socrata, contenido, momento):
    """Escribe una fila como la escribía la llave VIEJA: identidad = `:id`."""
    import hashlib as _h
    import json as _j

    blob = _j.dumps(contenido, sort_keys=True, ensure_ascii=False)
    cur.execute(
        "INSERT INTO crudo_registro VALUES (%s, %s, %s, %s, %s)",
        (dataset, id_socrata, _h.sha256(blob.encode()).hexdigest(), blob, momento),
    )


def test_el_traslado_colapsa_las_copias_que_solo_cambian_en_la_plataforma(dsn, rellave_limpia):
    # El caso real: el mismo contrato reingerido con `:id` nuevo. Medido el
    # 2026-09-03 sobre 24 685 contratos.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        for k, sufijo in enumerate(("aaa", "zzz")):
            _fila_cruda(cur, "contratos", sufijo, {
                ":id": sufijo, ":updated_at": f"2026-09-03T1{k}:00:00.000", ":version": str(k),
                "id_contrato": "CO1.PCCNTR.1", "estado_contrato": "Aprobado",
            }, MOMENTO)
        cx.commit()

    with psycopg.connect(dsn) as cx:
        resumen = rellave_limpia.trasladar(cx, dsn_lectura=dsn, avisar=False)
        cx.commit()

    assert resumen.leidas == 2
    assert resumen.escritas == 1
    assert resumen.colapsadas == 1


def test_el_traslado_conserva_las_versiones_que_si_cambiaron(dsn, rellave_limpia):
    # De 300 contratos duplicados medidos, 17 traían un cambio real. Colapsar
    # esos sería perder dato que la fuente sí entregó.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        for sufijo, estado in (("aaa", "Aprobado"), ("zzz", "Modificado")):
            _fila_cruda(cur, "contratos", sufijo, {
                ":id": sufijo, "id_contrato": "CO1.PCCNTR.1", "estado_contrato": estado,
            }, MOMENTO)
        cx.commit()

    with psycopg.connect(dsn) as cx:
        resumen = rellave_limpia.trasladar(cx, dsn_lectura=dsn, avisar=False)
        cx.commit()

    assert resumen.escritas == 2
    assert resumen.colapsadas == 0


def test_el_traslado_no_colapsa_las_adjudicaciones_de_un_multilote(dsn, rellave_limpia):
    # `procesos` trae una fila por ADJUDICACIÓN. Identificar solo por
    # `id_del_proceso` habría fundido los tres lotes en uno.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        for lote in range(3):
            for copia in ("a", "b"):
                _fila_cruda(cur, "procesos", f"p{lote}{copia}", {
                    ":id": f"p{lote}{copia}", ":updated_at": copia,
                    "id_del_proceso": "CO1.REQ.7", "id_adjudicacion": f"ADJ{lote}",
                }, MOMENTO)
        cx.commit()

    with psycopg.connect(dsn) as cx:
        resumen = rellave_limpia.trasladar(cx, dsn_lectura=dsn, avisar=False)
        cx.commit()
        with cx.cursor() as cur:
            cur.execute(
                "SELECT count(DISTINCT id_fila_fuente) FROM crudo_registro_rellave "
                "WHERE dataset = 'procesos'"
            )
            adjudicaciones = cur.fetchone()[0]

    assert resumen.leidas == 6
    assert resumen.escritas == 3
    assert adjudicaciones == 3


def test_el_traslado_conserva_lo_que_no_tiene_identidad_de_negocio(dsn, rellave_limpia):
    # Filas escritas bajo la llave vieja sin `id_contrato`. Tirarlas sería
    # perder serie histórica; la capa normalizada ya sabe descartarlas.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        _fila_cruda(cur, "contratos", "huerf", {":id": "huerf", "nit_entidad": "899999027"}, MOMENTO)
        cx.commit()

    with psycopg.connect(dsn) as cx:
        resumen = rellave_limpia.trasladar(cx, dsn_lectura=dsn, avisar=False)
        cx.commit()

    assert resumen.sin_identidad == 1
    assert resumen.escritas == 1
    assert resumen.colapsadas == 0


def test_el_contenido_trasladado_sigue_trayendo_los_campos_de_plataforma(dsn, rellave_limpia):
    # La capa cruda guarda lo que llegó. Lo que cambia es sobre qué se calcula
    # la identidad, no qué se almacena.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        _fila_cruda(cur, "contratos", "aaa", {
            ":id": "aaa", ":version": "3", "id_contrato": "CO1.PCCNTR.1",
        }, MOMENTO)
        cx.commit()

    with psycopg.connect(dsn) as cx:
        rellave_limpia.trasladar(cx, dsn_lectura=dsn, avisar=False)
        cx.commit()
        with cx.cursor() as cur:
            cur.execute("SELECT contenido FROM crudo_registro_rellave")
            contenido = cur.fetchone()[0]

    assert contenido[":id"] == "aaa"
    assert contenido[":version"] == "3"


def test_reingerir_despues_del_traslado_ya_no_duplica(dsn, rellave_limpia):
    # La prueba que cierra el círculo: tras el traslado, una fila que llega de
    # nuevo con `:id` distinto choca contra la llave primaria, que es lo que
    # llevaba semanas sin pasar.
    from vigia.crudo.modelo import RegistroCrudo as _RC

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        _fila_cruda(cur, "contratos", "aaa", {
            ":id": "aaa", "id_contrato": "CO1.PCCNTR.1", "estado_contrato": "Aprobado",
        }, MOMENTO)
        cx.commit()

    with psycopg.connect(dsn) as cx:
        rellave_limpia.trasladar(cx, dsn_lectura=dsn, avisar=False)
        cx.commit()
        # La misma fila, republicada con otro `:id` y otro `:updated_at`.
        otra_vez = _RC.desde_respuesta(
            "contratos",
            {":id": "zzz", ":updated_at": "2026-09-03T17:00:00.000",
             "id_contrato": "CO1.PCCNTR.1", "estado_contrato": "Aprobado"},
            MOMENTO,
            campos_identidad=CONTRATOS.campos_identidad,
        )
        with cx.cursor() as cur:
            cur.execute(
                "INSERT INTO crudo_registro_rellave VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING id_fila_fuente",
                (otra_vez.dataset, otra_vez.id_fila_fuente, otra_vez.hash_contenido,
                 psycopg.types.json.Jsonb(dict(otra_vez.contenido)), otra_vez.consultado_en),
            )
            insertadas = cur.fetchall()
            cur.execute("SELECT count(*) FROM crudo_registro_rellave")
            total = cur.fetchone()[0]
        cx.commit()

    assert insertadas == []
    assert total == 1


def test_el_traslado_no_se_cuelga_al_mezclar_copy_con_el_cursor_de_lectura(dsn, rellave_limpia):
    # Regresión del 2026-09-04. La primera versión usaba UNA sola conexión para
    # el `COPY` de escritura y el cursor con nombre de lectura. Un `COPY` toma
    # el control del protocolo de la conexión mientras dura, así que intercalar
    # un `FETCH` por el mismo cable la dejaba colgada: dieciocho minutos sin una
    # línea de salida sobre las 407 000 filas reales, sin forma de distinguir
    # «va lento» de «se colgó».
    #
    # Basta con que esta prueba TERMINE. Que además cuadren los números es la
    # comprobación de que el arreglo no rompió el traslado.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        for i in range(50):
            for sufijo in ("aaa", "zzz"):
                _fila_cruda(cur, "contratos", f"{sufijo}{i}", {
                    ":id": f"{sufijo}{i}", ":updated_at": sufijo,
                    "id_contrato": f"CO1.PCCNTR.{i}", "estado_contrato": "Aprobado",
                }, MOMENTO)
        cx.commit()

    with psycopg.connect(dsn) as cx:
        resumen = rellave_limpia.trasladar(cx, dsn_lectura=dsn, avisar=False)
        cx.commit()

    assert resumen.leidas == 100
    assert resumen.escritas == 50
    assert resumen.colapsadas == 50


def test_la_comprobacion_detecta_una_identidad_perdida(dsn, rellave_limpia):
    # La puerta que decide si se intercambia. Se fabrica el caso malo a mano:
    # dos filas de procesos con la misma identidad de negocio en el destino
    # cuando el origen tenía dos distintas.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        for lote in range(2):
            _fila_cruda(cur, "procesos", f"p{lote}", {
                ":id": f"p{lote}", "id_del_proceso": "CO1.REQ.7",
                "id_adjudicacion": f"ADJ{lote}",
            }, MOMENTO)
        cx.commit()

    with psycopg.connect(dsn) as cx:
        rellave_limpia.trasladar(cx, dsn_lectura=dsn, avisar=False)
        cx.commit()
        # Se borra una a mano para simular la pérdida.
        with cx.cursor() as cur:
            cur.execute(
                "DELETE FROM crudo_registro_rellave WHERE id_fila_fuente = %s",
                ("CO1.REQ.7|ADJ1",),
            )
        cx.commit()

        malas = [c for c in rellave_limpia.comprobar(cx) if not c.cuadra]
        assert [c.dataset for c in malas] == ["procesos"]

        with pytest.raises(rellave_limpia.TrasladoNoCuadra, match="procesos"):
            rellave_limpia.intercambiar(cx)


def test_la_comprobacion_pasa_cuando_el_traslado_esta_completo(dsn, rellave_limpia):
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        for lote in range(3):
            for copia in ("a", "b"):
                _fila_cruda(cur, "procesos", f"p{lote}{copia}", {
                    ":id": f"p{lote}{copia}", ":updated_at": copia,
                    "id_del_proceso": "CO1.REQ.7", "id_adjudicacion": f"ADJ{lote}",
                }, MOMENTO)
        cx.commit()

    with psycopg.connect(dsn) as cx:
        rellave_limpia.trasladar(cx, dsn_lectura=dsn, avisar=False)
        cx.commit()
        assert all(c.cuadra for c in rellave_limpia.comprobar(cx))


# ---------------------------------------------------------------------------
# Historia 1.5: identidad de proveedor contra el motor real.
# ---------------------------------------------------------------------------


@pytest.fixture
def limpiar_proveedores(dsn):
    def _limpiar():
        with psycopg.connect(dsn) as cx, cx.cursor() as cur:
            cur.execute(
                "TRUNCATE crudo_registro, contrato, proceso, "
                "proveedor_variante, proveedor CASCADE"
            )
            cx.commit()

    _limpiar()
    yield
    _limpiar()


def _sembrar_contratos(dsn, contenidos):
    from vigia.crudo.modelo import RegistroCrudo

    momento = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        for contenido in contenidos:
            registro = RegistroCrudo.desde_respuesta(
                dataset="contratos",
                contenido=contenido,
                consultado_en=momento,
                campos_identidad=CONTRATOS.campos_identidad,
            )
            cur.execute(
                "INSERT INTO crudo_registro VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    registro.dataset, registro.id_fila_fuente, registro.hash_contenido,
                    psycopg.types.json.Jsonb(dict(registro.contenido)), registro.consultado_en,
                ),
            )
        cx.commit()


def _fila(id_contrato, documento, tipo="NIT", nombre="ACME"):
    return {
        "id_contrato": id_contrato,
        "documento_proveedor": documento,
        "tipodocproveedor": tipo,
        "proveedor_adjudicado": nombre,
        "fecha_de_firma": "2026-08-27T00:00:00.000",
    }


def test_el_mismo_documento_escrito_de_tres_formas_es_un_solo_proveedor(dsn, limpiar_proveedores):
    _sembrar_contratos(dsn, [
        _fila("C-1", "900.123.456", nombre="CONSTRUCTORA ANDINA S.A.S."),
        _fila("C-2", "900123456", nombre="Constructora Andina SAS"),
        _fila("C-3", "900 123 456", nombre="CONSTRUCTORA ANDINA S.A.S."),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT numero, contratos, variantes, nombre_principal FROM proveedor")
        filas = cur.fetchall()

    assert filas == [("900123456", 3, 2, "CONSTRUCTORA ANDINA S.A.S.")]


def test_las_variantes_de_nombre_quedan_consultables(dsn, limpiar_proveedores):
    # Segundo criterio de aceptación, literal: «las variantes de nombre quedan
    # registradas y consultables».
    _sembrar_contratos(dsn, [
        _fila("C-1", "900123456", nombre="CONSTRUCTORA ANDINA S.A.S."),
        _fila("C-2", "900123456", nombre="Constructora Andina SAS"),
        _fila("C-3", "900123456", nombre="CONSTRUCTORA ANDINA S.A.S."),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute(
            "SELECT nombre, contratos FROM proveedor_variante "
            "WHERE numero = '900123456' ORDER BY contratos DESC, nombre"
        )
        variantes = cur.fetchall()

    assert variantes == [
        ("CONSTRUCTORA ANDINA S.A.S.", 2),
        ("CONSTRUCTORA ANDINA SAS", 1),
    ]


def test_el_nit_con_y_sin_digito_de_verificacion_es_el_mismo_proveedor(dsn, limpiar_proveedores):
    _sembrar_contratos(dsn, [
        _fila("C-1", "860000189-3", nombre="BAVARIA S.A."),
        _fila("C-2", "860000189", nombre="BAVARIA S.A."),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT numero, contratos FROM proveedor")
        assert cur.fetchall() == [("860000189", 2)]


def test_las_uniones_temporales_no_se_funden_en_un_proveedor_falso(dsn, limpiar_proveedores):
    # El fallo que esta historia evita: 175 836 contratos del histórico traen
    # «No Definido» como documento. Agruparlos crearía el contratista más
    # concentrado de Colombia, y falso entero.
    _sembrar_contratos(dsn, [
        _fila("C-1", "No Definido", nombre="UT NUTRIENDO EL PAE 2026"),
        _fila("C-2", "No Definido", nombre="UT NOC 2022"),
        _fila("C-3", "No Definido", nombre="CONSORCIO INTER-IPES"),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT count(*) FROM proveedor")
        assert cur.fetchone()[0] == 0
        # Pero los contratos NO se pierden: siguen ahí, sin proveedor.
        cur.execute("SELECT count(*) FROM contrato WHERE proveedor_tipo IS NULL")
        assert cur.fetchone()[0] == 3


def test_un_nit_y_una_cedula_con_los_mismos_digitos_no_se_funden(dsn, limpiar_proveedores):
    _sembrar_contratos(dsn, [
        _fila("C-1", "900123456", tipo="NIT", nombre="EMPRESA"),
        _fila("C-2", "900123456", tipo="Cédula de Ciudadanía", nombre="PERSONA"),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT count(*) FROM proveedor")
        assert cur.fetchone()[0] == 2


def test_normalizar_dos_veces_deja_los_mismos_proveedores(dsn, limpiar_proveedores):
    _sembrar_contratos(dsn, [
        _fila("C-1", "900123456", nombre="ACME"),
        _fila("C-2", "900.123.456", nombre="Acme SAS"),
    ])

    _normalizar(dsn)
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT tipo_documento, numero, contratos, variantes FROM proveedor")
        primera = cur.fetchall()
        cur.execute("SELECT nombre, contratos FROM proveedor_variante ORDER BY nombre")
        variantes_primera = cur.fetchall()

    _normalizar(dsn)
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT tipo_documento, numero, contratos, variantes FROM proveedor")
        assert cur.fetchall() == primera
        cur.execute("SELECT nombre, contratos FROM proveedor_variante ORDER BY nombre")
        assert cur.fetchall() == variantes_primera


def test_la_base_rechaza_media_identidad_de_proveedor(dsn, limpiar_proveedores):
    # Misma barrera que el enlace a Proceso de la 1.4: media identidad no
    # existe, y la base tiene que impedirlo aunque el código falle.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO contrato (id_contrato, proveedor_tipo, "
                "id_fila_fuente, hash_contenido, normalizado_en) "
                "VALUES ('C-X', 'NIT', 'f', 'h', now())"
            )


# ----------------------------- uniones temporales y consorcios (1.5b) -------


def _fila_grupo(id_contrato, nombre, documento="No Definido", es_grupo="Si", valor=None):
    fila = _fila(id_contrato, documento, tipo="No Definido", nombre=nombre)
    fila["es_grupo"] = es_grupo
    if valor is not None:
        fila["valor_del_contrato"] = str(valor)
    return fila


def test_una_union_temporal_sin_documento_ya_no_desaparece(dsn, limpiar_proveedores):
    # Medido el 2026-09-04: de los 175 836 contratos con documento «No
    # Definido», los 15 291 que son contratos de verdad vienen marcados
    # `es_grupo = 'Si'`. Antes de la 1.5b esos quedaban invisibles.
    _sembrar_contratos(dsn, [
        _fila_grupo("C-1", "UT NUTRIENDO EL PAE 2026", valor=5000),
        _fila_grupo("C-2", "UT NOC 2022", valor=3000),
        _fila_grupo("C-3", "CONSORCIO INTER-IPES", valor=2000),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        # Se cuentan: tres identidades, todas marcadas provisionales.
        cur.execute("SELECT count(*) FROM proveedor WHERE provisional")
        assert cur.fetchone()[0] == 3
        # Ninguno se quedó sin identidad.
        cur.execute("SELECT count(*) FROM contrato WHERE proveedor_tipo IS NULL")
        assert cur.fetchone()[0] == 0
        # Y se pueden sumar, que es de lo que se trataba.
        cur.execute("SELECT sum(valor) FROM contrato WHERE proveedor_provisional")
        assert cur.fetchone()[0] == 10000


def test_ninguna_union_temporal_concentra_por_ser_provisional(dsn, limpiar_proveedores):
    # La garantía estructural: una identidad provisional lleva el número de su
    # propio contrato, así que nunca puede sumar dos.
    _sembrar_contratos(dsn, [
        _fila_grupo("C-1", "UNION TEMPORAL SALUD 2024"),
        _fila_grupo("C-2", "UNION TEMPORAL SALUD 2024"),
        _fila_grupo("C-3", "UNION TEMPORAL SALUD 2024"),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT max(contratos) FROM proveedor WHERE provisional")
        assert cur.fetchone()[0] == 1


def test_un_borrador_sin_grupo_sigue_sin_identidad(dsn, limpiar_proveedores):
    # Son 160 543 en el histórico: papeles que nunca adjudicaron a nadie.
    _sembrar_contratos(dsn, [
        _fila_grupo("C-1", "Sin Descripcion", es_grupo="No"),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT count(*) FROM proveedor")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT proveedor_provisional FROM contrato WHERE id_contrato='C-1'")
        # NULL, no false: no es que tenga identidad real, es que no tiene.
        assert cur.fetchone()[0] is None


def test_la_marca_de_la_base_y_la_del_codigo_no_pueden_separarse(dsn, limpiar_proveedores):
    # La columna es GENERADA a partir de un literal en la migración 007, y el
    # código usa una constante. Si alguien cambia una y no la otra, la base
    # diría una cosa y el reporte otra. Esta prueba lo impide.
    _sembrar_contratos(dsn, [
        _fila_grupo("C-1", "UT ALGO"),
        _fila("C-2", "900123456", nombre="ACME"),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute(
            "SELECT proveedor_tipo FROM contrato WHERE proveedor_provisional"
        )
        assert cur.fetchone()[0] == TIPO_GRUPO_PROVISIONAL
        cur.execute(
            "SELECT count(*) FROM contrato WHERE proveedor_provisional IS FALSE"
        )
        assert cur.fetchone()[0] == 1


# --------------------------------- territorio y orden administrativo (1.6) --


def _fila_territorio(id_contrato, departamento, orden="Territorial", ciudad="Cali"):
    fila = _fila(id_contrato, "900123456", nombre="ACME")
    fila["departamento"] = departamento
    fila["ciudad"] = ciudad
    fila["orden"] = orden
    return fila


def test_bogota_recibe_su_codigo_divipola(dsn, limpiar_proveedores):
    # El fallo silencioso que la 1.6 evita: el DANE escribe «BOGOTA, D.C.» y
    # el SECOP «Distrito Capital de Bogota». Cruzar por nombre deja sin
    # territorio al 16 % de los contratos del pais, y no avisa.
    _sembrar_contratos(dsn, [
        _fila_territorio("C-1", "Distrito Capital de Bogotá"),
        _fila_territorio("C-2", "San Andrés, Providencia y Santa Catalina"),
        _fila_territorio("C-3", "Valle del Cauca"),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute(
            "SELECT id_contrato, departamento_codigo, departamento_nombre "
            "FROM contrato ORDER BY id_contrato"
        )
        assert cur.fetchall() == [
            ("C-1", "11", "BOGOTA, D.C."),
            ("C-2", "88", "ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA"),
            ("C-3", "76", "VALLE DEL CAUCA"),
        ]


def test_una_corporacion_autonoma_no_se_cuenta_como_nacional(dsn, limpiar_proveedores):
    # Son 2 224 contratos en agosto de 2026 y 1 800 en 2019: no caben en una
    # bandera booleana.
    _sembrar_contratos(dsn, [
        _fila_territorio("C-1", "Boyacá", orden="Corporación Autónoma"),
        _fila_territorio("C-2", "Boyacá", orden="Nacional"),
        _fila_territorio("C-3", "Boyacá", orden="Territorial"),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT orden, count(*) FROM contrato GROUP BY orden ORDER BY orden")
        assert cur.fetchall() == [
            ("CORPORACION AUTONOMA", 1), ("NACIONAL", 1), ("TERRITORIAL", 1),
        ]


def test_un_departamento_no_definido_se_queda_sin_codigo_y_se_puede_contar(
    dsn, limpiar_proveedores
):
    _sembrar_contratos(dsn, [
        _fila_territorio("C-1", "No Definido"),
        _fila_territorio("C-2", "Antioquia"),
    ])

    _normalizar(dsn)

    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT count(*) FROM contrato WHERE departamento_codigo IS NULL")
        assert cur.fetchone()[0] == 1
        # El nombre que trajo la fuente NO se pierde: es lo unico con lo que
        # se podra diagnosticar por que no resolvio.
        cur.execute("SELECT departamento_nombre FROM contrato WHERE id_contrato='C-1'")
        assert cur.fetchone()[0] == "NO DEFINIDO"


def test_la_base_rechaza_un_orden_que_nadie_midio(dsn, limpiar_proveedores):
    # Una cuarta categoria que entre por descuido seria una categoria nueva
    # sin que nadie se entere.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO contrato (id_contrato, orden, id_fila_fuente,"
                " hash_contenido, normalizado_en) VALUES ('X','MUNICIPAL','f','h', now())"
            )


def test_la_base_rechaza_un_codigo_que_no_es_divipola(dsn, limpiar_proveedores):
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO contrato (id_contrato, departamento_codigo,"
                " departamento_nombre, id_fila_fuente, hash_contenido, normalizado_en)"
                " VALUES ('X','5','ANTIOQUIA','f','h', now())"
            )


def test_la_base_rechaza_media_identidad_de_territorio(dsn, limpiar_proveedores):
    # Misma barrera que el enlace a Proceso de la 1.4 y el proveedor de la 1.5.
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO contrato (id_contrato, departamento_codigo,"
                " id_fila_fuente, hash_contenido, normalizado_en)"
                " VALUES ('X','05','f','h', now())"
            )
