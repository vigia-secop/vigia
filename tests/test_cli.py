"""Invocación por línea de comandos."""

from __future__ import annotations

from contextlib import contextmanager

import httpx
import pytest

from tests.conftest import FuenteFalsa, registro
from vigia import __main__ as cli
from vigia.crudo.memoria import RepositorioEnMemoria
from vigia.ingest.estado import RepositorioEstadoEnMemoria
from vigia.schema.novedades import RepositorioNovedadesEnMemoria

ARGUMENTOS_BASE = ["--dataset", "contratos", "--desde", "2026-08-01", "--hasta", "2026-08-02"]


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    for variable in (
        "VIGIA_DSN",
        "VIGIA_LIMITE_PAGINA",
        "VIGIA_DOMINIO_SOCRATA",
        "VIGIA_TOKEN_SOCRATA",
        "VIGIA_VENTANA_DIAS",
    ):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def postgres_falso(monkeypatch):
    """Sustituye los tres almacenes de la corrida real por dobles en memoria."""

    def instalar(crudo=None, novedades=None, estado=None, dsn="postgresql://prueba"):
        almacenes = {
            "repositorio_postgres": RepositorioEnMemoria() if crudo is None else crudo,
            "repositorio_novedades_postgres": (
                RepositorioNovedadesEnMemoria() if novedades is None else novedades
            ),
            "repositorio_estado_postgres": (
                RepositorioEstadoEnMemoria() if estado is None else estado
            ),
        }
        for nombre, doble in almacenes.items():
            @contextmanager
            def entregar(_dsn, _doble=doble):
                yield _doble

            monkeypatch.setattr(cli, nombre, entregar)
        monkeypatch.setenv("VIGIA_DSN", dsn)
        return (
            almacenes["repositorio_postgres"],
            almacenes["repositorio_novedades_postgres"],
            almacenes["repositorio_estado_postgres"],
        )

    return instalar


@pytest.fixture
def fuente_falsa(monkeypatch):
    """Sustituye el cliente HTTP real por uno atado a una FuenteFalsa."""

    def instalar(registros, **opciones):
        fuente = FuenteFalsa(registros, **opciones)
        monkeypatch.setattr(
            cli,
            "crear_cliente_http",
            lambda **_: httpx.Client(transport=httpx.MockTransport(fuente)),
        )
        return fuente

    return instalar


def test_dry_run_recorre_la_fuente_sin_tocar_la_base(fuente_falsa, capsys):
    fuente = fuente_falsa([registro(f"row-{indice}") for indice in range(3)])

    codigo = cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "dry-run" in salida
    assert "vistos=3" in salida
    # No inventa cuántos serían nuevos: eso solo lo sabe la base.
    assert "insertados" not in salida
    assert len(fuente.peticiones) == 1


def test_la_corrida_real_escribe_por_el_repositorio_de_postgres(
    fuente_falsa, postgres_falso, capsys
):
    # Sin esta prueba, invertir la rama de --dry-run dejaría la suite en verde
    # mientras ninguna ingesta escribe una sola fila.
    fuente_falsa([registro(f"row-{indice}") for indice in range(3)])
    almacen, _, _ = postgres_falso()

    codigo = cli.main(ARGUMENTOS_BASE)

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "dry-run" not in salida
    assert "insertados=3" in salida
    assert len(almacen) == 3


def test_el_dominio_del_entorno_es_el_que_se_consulta(fuente_falsa, monkeypatch):
    fuente = fuente_falsa([registro("row-1")])
    monkeypatch.setenv("VIGIA_DOMINIO_SOCRATA", "https://espejo.ejemplo")

    cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    assert fuente.peticiones[0].url.host == "espejo.ejemplo"


def test_el_limite_de_pagina_de_la_bandera_llega_a_la_peticion(fuente_falsa):
    fuente = fuente_falsa([registro(f"row-{indice}") for indice in range(3)])

    cli.main([*ARGUMENTOS_BASE, "--dry-run", "--limite-pagina", "2"])

    assert fuente.limites[0] == 2
    assert fuente.offsets == [0, 2]


def test_el_limite_de_pagina_del_entorno_llega_a_la_peticion(fuente_falsa, monkeypatch):
    fuente = fuente_falsa([registro("row-1")])
    monkeypatch.setenv("VIGIA_LIMITE_PAGINA", "7")

    cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    assert fuente.limites[0] == 7


def test_la_bandera_gana_sobre_el_entorno(fuente_falsa, monkeypatch):
    fuente = fuente_falsa([registro("row-1")])
    monkeypatch.setenv("VIGIA_LIMITE_PAGINA", "7")

    cli.main([*ARGUMENTOS_BASE, "--dry-run", "--limite-pagina", "3"])

    assert fuente.limites[0] == 3


def test_un_limite_de_pagina_invalido_es_error_de_uso(fuente_falsa, capsys):
    fuente_falsa([registro("row-1")])

    with pytest.raises(SystemExit) as salida:
        cli.main([*ARGUMENTOS_BASE, "--dry-run", "--limite-pagina", "0"])

    assert salida.value.code == 2


def test_un_limite_de_pagina_no_numerico_en_el_entorno_es_error_de_uso(
    fuente_falsa, monkeypatch, capsys
):
    fuente_falsa([registro("row-1")])
    monkeypatch.setenv("VIGIA_LIMITE_PAGINA", "mil")

    with pytest.raises(SystemExit) as salida:
        cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    assert salida.value.code == 2
    assert "VIGIA_LIMITE_PAGINA" in capsys.readouterr().err


def test_un_limite_de_pagina_sobre_el_tope_de_socrata_es_error_de_uso(fuente_falsa, capsys):
    fuente_falsa([registro("row-1")])

    codigo = cli.main([*ARGUMENTOS_BASE, "--dry-run", "--limite-pagina", "100000"])

    assert codigo == 2
    assert "limite_pagina" in capsys.readouterr().err


def test_sin_dsn_y_sin_dry_run_no_arranca(capsys):
    codigo = cli.main(ARGUMENTOS_BASE)

    assert codigo == 2
    assert "VIGIA_DSN" in capsys.readouterr().err


def test_un_rango_invertido_termina_en_error_de_uso(fuente_falsa, capsys):
    fuente = fuente_falsa([registro("row-1")])

    codigo = cli.main(
        ["--dataset", "contratos", "--desde", "2026-08-05", "--hasta", "2026-08-01", "--dry-run"]
    )

    assert codigo == 2
    assert "rango inválido" in capsys.readouterr().err
    assert fuente.peticiones == []


def test_un_fallo_de_la_fuente_termina_en_error_de_ejecucion(fuente_falsa, capsys):
    fuente_falsa([registro("row-1")], fallos={0: 503})

    codigo = cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    assert codigo == 1
    assert "503" in capsys.readouterr().err


def test_un_registro_sin_identidad_termina_en_error_de_ejecucion(fuente_falsa, capsys):
    # Sin captura explícita esto salía como traza de excepción.
    fuente_falsa(
        [registro("row-1")],
        respuesta_cruda=lambda _offset: httpx.Response(200, json=[{"nit_entidad": "899999027"}]),
    )

    codigo = cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    assert codigo == 1
    # El error nombra el campo de NEGOCIO que falta, no el `:id` de la
    # plataforma: desde el 2026-09-04 la identidad es `id_contrato`.
    assert "id_contrato" in capsys.readouterr().err


def test_un_fallo_del_almacen_termina_en_error_de_ejecucion(fuente_falsa, monkeypatch, capsys):
    from vigia.crudo.repositorio import ErrorAlmacen

    fuente_falsa([registro("row-1")])

    @contextmanager
    def repositorio_roto(_dsn):
        raise ErrorAlmacen("no se pudo conectar a la base de datos: puerto cerrado")
        yield  # pragma: no cover

    monkeypatch.setattr(cli, "repositorio_postgres", repositorio_roto)
    monkeypatch.setenv("VIGIA_DSN", "postgresql://prueba")

    codigo = cli.main(ARGUMENTOS_BASE)

    assert codigo == 1
    assert "puerto cerrado" in capsys.readouterr().err
    


def test_un_dataset_desconocido_se_rechaza():
    with pytest.raises(SystemExit):
        cli.main(["--dataset", "tvec", "--desde", "2026-08-01", "--hasta", "2026-08-02"])


def test_una_fecha_mal_escrita_se_rechaza():
    with pytest.raises(SystemExit):
        cli.main(["--dataset", "contratos", "--desde", "01-08-2026", "--hasta", "2026-08-02"])


def test_un_cambio_de_esquema_detiene_la_corrida(fuente_falsa, capsys):
    from tests.conftest import CAMPOS_CONTRATOS

    fuente = fuente_falsa(
        [registro("row-1")], columnas=CAMPOS_CONTRATOS - {"valor_del_contrato"}
    )

    codigo = cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    error = capsys.readouterr().err
    assert codigo == 1
    assert "cambió de forma" in error
    assert "valor_del_contrato" in error
    # No se pidió un solo registro.
    assert fuente.peticiones == []


def test_sin_esquema_capturado_no_arranca(fuente_falsa, monkeypatch, capsys):
    from vigia.schema.definiciones import EsquemaEsperadoAusente

    fuente_falsa([registro("row-1")])

    def sin_esquema(_dataset):
        raise EsquemaEsperadoAusente("no hay esquema esperado capturado en X; captúralo con ...")

    monkeypatch.setattr(cli.EsquemaEsperado, "para", staticmethod(sin_esquema))

    codigo = cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    assert codigo == 2
    assert "captúralo" in capsys.readouterr().err


def test_una_novedad_de_una_corrida_real_llega_al_repositorio(
    fuente_falsa, postgres_falso, capsys
):
    from tests.conftest import CAMPOS_CONTRATOS

    fuente_falsa([registro("row-1")], columnas=set(CAMPOS_CONTRATOS) | {"valor_reintegro"})
    _, anotadas, _ = postgres_falso()

    codigo = cli.main(ARGUMENTOS_BASE)

    assert codigo == 0
    assert ("contratos", "valor_reintegro") in anotadas.registradas()
    assert "valor_reintegro" in capsys.readouterr().out


def test_en_dry_run_las_novedades_se_reportan_y_se_avisa_que_no_se_guardan(
    fuente_falsa, capsys
):
    from tests.conftest import CAMPOS_CONTRATOS

    fuente_falsa([registro("row-1")], columnas=set(CAMPOS_CONTRATOS) | {"valor_reintegro"})

    codigo = cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "valor_reintegro" in salida
    assert "no quedan registrados" in salida


def test_un_fallo_al_anotar_una_novedad_no_tumba_la_corrida(
    fuente_falsa, postgres_falso, capsys
):
    from tests.conftest import CAMPOS_CONTRATOS
    from vigia.crudo.repositorio import ErrorAlmacen

    fuente_falsa([registro("row-1")], columnas=set(CAMPOS_CONTRATOS) | {"valor_reintegro"})

    class Roto:
        def registrar(self, novedades):
            raise ErrorAlmacen("la tabla esquema_novedad no existe: falta la migración 002")

    postgres_falso(novedades=Roto())

    codigo = cli.main(ARGUMENTOS_BASE)

    # Un campo nuevo no detiene nada, ni siquiera cuando no se puede anotar.
    assert codigo == 0
    assert "insertados=1" in capsys.readouterr().out


def test_un_esquema_esperado_de_otro_dataset_es_error_de_uso(fuente_falsa, monkeypatch, capsys):
    from tests.conftest import CAMPOS_CONTRATOS
    from vigia.schema.definiciones import EsquemaEsperado

    fuente_falsa([registro("row-1")])
    otro = EsquemaEsperado(
        dataset="procesos",
        id_socrata="p6dx-8zbt",
        capturado_en=__import__("datetime").date(2026, 9, 2),
        procedencia="x",
        campos=frozenset(CAMPOS_CONTRATOS),
    )
    monkeypatch.setattr(cli.EsquemaEsperado, "para", staticmethod(lambda *_a, **_k: otro))

    codigo = cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    assert codigo == 2
    assert "inconsistente" in capsys.readouterr().err


def test_el_primer_ciclo_sin_desde_es_error_de_uso(fuente_falsa, postgres_falso, capsys):
    fuente_falsa([registro("row-1")])
    postgres_falso()

    codigo = cli.main(["--dataset", "contratos"])

    assert codigo == 2
    assert "--desde" in capsys.readouterr().err


def test_el_ciclo_incremental_arranca_de_la_marca_menos_la_ventana(
    fuente_falsa, postgres_falso
):
    from datetime import date, datetime, timezone

    from vigia.ingest.estado import MarcaDeAgua, RepositorioEstadoEnMemoria

    fuente = fuente_falsa([registro("row-1")])
    memoria_estado = RepositorioEstadoEnMemoria()
    memoria_estado._marcas["contratos"] = MarcaDeAgua(
        "contratos", date(2026, 8, 20), datetime(2026, 9, 2, tzinfo=timezone.utc)
    )
    postgres_falso(estado=memoria_estado)

    codigo = cli.main(["--dataset", "contratos", "--hasta", "2026-09-02", "--ventana-dias", "10"])

    assert codigo == 0
    assert "2026-08-10" in fuente.peticiones[0].url.params["$where"]


def test_la_ventana_por_defecto_deja_margen_sobre_el_retraso_observado():
    """Cuarenta y cinco días, y el número tiene una razón escrita.

    OJO, LA RAZÓN NO ES LA QUE PRIMERO SE DIO. Se subió de 30 a 45 creyendo
    que se perdían contratos publicados tarde. Medido el 2026-09-20: de los
    contratos que entraron con más de 30 días, NUEVOS DE VERDAD había cero.
    La ventana de 30 no perdía contratos.

    Lo que sí hace la de 45 es ver las MODIFICACIONES del SECOP a contratos
    de entre 31 y 46 días —9.123 en una sola corrida— que con 30 no se
    habrían visto nunca en su versión nueva. La historia completa está en el
    comentario de `VENTANA_DIAS_POR_DEFECTO`.

    Esta prueba no defiende el 45. Defiende que bajarlo sea una decisión y
    no un descuido: quien lo cambie tiene que venir aquí y explicar por qué.
    """
    from vigia.__main__ import VENTANA_DIAS_POR_DEFECTO

    assert VENTANA_DIAS_POR_DEFECTO >= 45


def test_la_ventana_del_entorno_llega_al_ciclo(fuente_falsa, postgres_falso, monkeypatch):
    from datetime import date, datetime, timezone

    from vigia.ingest.estado import MarcaDeAgua, RepositorioEstadoEnMemoria

    fuente = fuente_falsa([registro("row-1")])
    memoria_estado = RepositorioEstadoEnMemoria()
    memoria_estado._marcas["contratos"] = MarcaDeAgua(
        "contratos", date(2026, 8, 20), datetime(2026, 9, 2, tzinfo=timezone.utc)
    )
    postgres_falso(estado=memoria_estado)
    monkeypatch.setenv("VIGIA_VENTANA_DIAS", "5")

    cli.main(["--dataset", "contratos", "--hasta", "2026-09-02"])

    assert "2026-08-15" in fuente.peticiones[0].url.params["$where"]


def test_una_ventana_no_numerica_en_el_entorno_es_error_de_uso(
    fuente_falsa, postgres_falso, monkeypatch, capsys
):
    fuente_falsa([registro("row-1")])
    postgres_falso()
    monkeypatch.setenv("VIGIA_VENTANA_DIAS", "muchos")

    with pytest.raises(SystemExit) as salida:
        cli.main([*ARGUMENTOS_BASE])

    assert salida.value.code == 2
    assert "VIGIA_VENTANA_DIAS" in capsys.readouterr().err


def test_la_senal_de_ventana_corta_se_imprime(fuente_falsa, postgres_falso, capsys):
    from datetime import date, datetime, timezone

    from vigia.ingest.estado import MarcaDeAgua, RepositorioEstadoEnMemoria

    # Marca en el 31 de agosto, ventana de 30 días: el borde es el 1 de agosto.
    #
    # LA VENTANA VA ESCRITA AQUI Y NO SE HEREDA DEL VALOR POR DEFECTO. Esta
    # prueba es sobre la SEÑAL, no sobre cuántos días trae el proyecto de
    # fábrica: el 2026-09-20 el defecto pasó de 30 a 45 y esta prueba se cayó
    # sin que la señal tuviera nada malo. Una prueba que se rompe cuando
    # cambia algo que no está probando es una prueba que miente.
    fuente_falsa([registro("row-1", fecha_de_firma="2026-08-01T00:00:00.000")])
    memoria_estado = RepositorioEstadoEnMemoria()
    memoria_estado._marcas["contratos"] = MarcaDeAgua(
        "contratos", date(2026, 8, 31), datetime(2026, 9, 2, tzinfo=timezone.utc)
    )
    postgres_falso(estado=memoria_estado)

    codigo = cli.main(
        ["--dataset", "contratos", "--hasta", "2026-09-02", "--ventana-dias", "30"]
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "VENTANA CORTA" in salida
    assert "--ventana-dias" in salida


def test_un_cambio_en_el_borde_se_informa_sin_gritar_ventana_corta(
    fuente_falsa, postgres_falso, capsys
):
    """Lo que la pantalla dijo el 2026-09-20 y lo que debió decir.

    Dijo «VENTANA CORTA: 1506 registro(s) nuevo(s) … antes de perder algo».
    Eran 1.506 contratos que ya teníamos y que el SECOP modificó. Esa frase,
    leída por una persona, lleva a ensanchar la ventana por miedo a perder
    datos, que es lo que pasó. Lo cierto se dice distinto y sin la palabra
    «perder».
    """
    from datetime import date, datetime, timezone

    from vigia.crudo.memoria import RepositorioEnMemoria
    from vigia.crudo.modelo import RegistroCrudo
    from vigia.ingest.datasets import CONTRATOS
    from vigia.ingest.estado import MarcaDeAgua, RepositorioEstadoEnMemoria

    crudo = RepositorioEnMemoria()
    crudo.guardar_pagina([RegistroCrudo.desde_respuesta(
        "contratos",
        registro("row-1", fecha_de_firma="2026-08-01T00:00:00.000",
                 valor_del_contrato="1000"),
        datetime(2026, 8, 20, tzinfo=timezone.utc),
        campos_identidad=CONTRATOS.campos_identidad,
    )])
    fuente_falsa([registro("row-1", fecha_de_firma="2026-08-01T00:00:00.000",
                           valor_del_contrato="1")])
    memoria_estado = RepositorioEstadoEnMemoria()
    memoria_estado._marcas["contratos"] = MarcaDeAgua(
        "contratos", date(2026, 8, 31), datetime(2026, 9, 2, tzinfo=timezone.utc)
    )
    postgres_falso(crudo=crudo, estado=memoria_estado)

    codigo = cli.main(
        ["--dataset", "contratos", "--hasta", "2026-09-02", "--ventana-dias", "30"]
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "VENTANA CORTA" not in salida
    assert "1 registro(s) que ya teníamos y la fuente modificó" in salida
    assert "No se perdía nada" in salida


def test_el_resumen_muestra_el_avance_de_la_marca(fuente_falsa, postgres_falso, capsys):
    fuente_falsa([registro("row-1", fecha_de_firma="2026-08-15T00:00:00.000")])
    postgres_falso()

    cli.main(ARGUMENTOS_BASE)

    assert "marca=—→2026-08-02" in capsys.readouterr().out


def test_un_ciclo_fallido_deja_registro_y_no_avanza_la_marca(
    fuente_falsa, postgres_falso, capsys
):
    from vigia.ingest.estado import EstadoCiclo, RepositorioEstadoEnMemoria

    fuente_falsa([registro("row-1")], fallos={0: 500})
    memoria_estado = RepositorioEstadoEnMemoria()
    postgres_falso(estado=memoria_estado)

    codigo = cli.main(ARGUMENTOS_BASE)

    assert codigo == 1
    assert memoria_estado.marca("contratos") is None
    assert memoria_estado.ciclos[-1].estado == EstadoCiclo.FALLIDO
    assert "500" in memoria_estado.ciclos[-1].causa


def test_un_hasta_futuro_se_rechaza(fuente_falsa, postgres_falso, capsys):
    # Un --hasta futuro fija la marca en el futuro y, como nunca retrocede,
    # atasca el dataset sin salida por línea de comandos.
    from datetime import timedelta

    from vigia.tiempo import hoy_en_colombia

    fuente_falsa([registro("row-1")])
    postgres_falso()
    manana = (hoy_en_colombia() + timedelta(days=1)).isoformat()

    with pytest.raises(SystemExit) as salida:
        cli.main(["--dataset", "contratos", "--desde", "2026-08-01", "--hasta", manana])

    assert salida.value.code == 2
    assert "no puede ser futura" in capsys.readouterr().err


def test_el_resumen_reporta_recuperados_y_sin_fecha(fuente_falsa, postgres_falso, capsys):
    from datetime import date, datetime, timezone

    from vigia.ingest.estado import RepositorioEstadoEnMemoria

    # Firmado antes de la marca: entra tarde y cuenta como recuperado.
    fuente_falsa([registro("row-1", fecha_de_firma="2026-08-10T00:00:00.000")])
    memoria_estado = RepositorioEstadoEnMemoria()
    memoria_estado.fijar_marca(
        "contratos", date(2026, 8, 20), datetime(2026, 9, 2, tzinfo=timezone.utc)
    )
    postgres_falso(estado=memoria_estado)

    cli.main(["--dataset", "contratos", "--hasta", "2026-09-02", "--ventana-dias", "30"])

    salida = capsys.readouterr().out
    assert "Recuperados por el solapamiento: 1" in salida
    assert "se habrían perdido sin ventana" in salida


def test_en_dry_run_la_marca_no_se_toca(fuente_falsa, monkeypatch, capsys):
    from vigia.ingest.estado import RepositorioEstadoEnMemoria

    fuente_falsa([registro("row-1")])
    memoria_estado = RepositorioEstadoEnMemoria()
    monkeypatch.setattr(
        cli, "RepositorioEstadoEnMemoria", lambda: memoria_estado
    )

    codigo = cli.main([*ARGUMENTOS_BASE, "--dry-run"])

    assert codigo == 0
    # El Ciclo en seco se registra en un estado que se tira al salir; nada
    # persiste, y la corrida lo dice.
    assert "nada se escribió" in capsys.readouterr().out


def test_la_pantalla_avisa_cuando_la_fuente_cambio_todo():
    """El 2026-09-22 pasó sin que la pantalla dijera nada.

    La ingesta de contratos vio 139.172 registros y los insertó todos: cero
    duplicados. En el resumen eso se leía como una línea más de números. La
    causa era un cambio de formato de la fuente, inofensivo para el dato pero
    no para el disco; la otra causa posible —que hubieran cambiado las cifras—
    habría sido grave. Cualquiera de las dos tiene que saltar a la vista.
    """
    from datetime import date, datetime, timezone

    from vigia.ingest.estado import EstadoCiclo, RegistroDeCiclo

    momento = datetime(2026, 9, 22, 14, tzinfo=timezone.utc)
    registro_ciclo = RegistroDeCiclo(
        dataset="contratos",
        cursor_entrada=date(2026, 9, 20),
        cursor_salida=date(2026, 9, 22),
        desde=date(2026, 8, 8),
        hasta=date(2026, 9, 22),
        estado=EstadoCiclo.COMPLETO,
        inicio=momento,
        fin=momento,
        vistos=139_172,
        insertados=139_172,
        duplicados=0,
        desde_derivado=True,
    )

    salida = cli._describir(registro_ciclo)

    assert "LA FUENTE CAMBIÓ TODO" in salida
    assert "EJECUTAR-VERIFICAR-FORMATO.bat" in salida


def test_una_corrida_normal_no_saca_ese_aviso():
    from datetime import date, datetime, timezone

    from vigia.ingest.estado import EstadoCiclo, RegistroDeCiclo

    momento = datetime(2026, 9, 20, 14, tzinfo=timezone.utc)
    registro_ciclo = RegistroDeCiclo(
        dataset="contratos",
        cursor_entrada=date(2026, 9, 19),
        cursor_salida=date(2026, 9, 20),
        desde=date(2026, 8, 6),
        hasta=date(2026, 9, 20),
        estado=EstadoCiclo.COMPLETO,
        inicio=momento,
        fin=momento,
        vistos=144_889,
        insertados=20_544,
        duplicados=124_345,
        desde_derivado=True,
    )

    assert "LA FUENTE CAMBIÓ TODO" not in cli._describir(registro_ciclo)
