"""El Ciclo de ingesta: de la fuente a la capa cruda.

Un Ciclo es, en los términos del glosario, una ejecución completa de ingesta.
`ingerir` recorre un rango explícito; `ejecutar_ciclo` lo envuelve con la marca
de agua, la ventana de solapamiento y el registro que exige AD-4.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Protocol

from vigia.crudo.modelo import RegistroCrudo
from vigia.crudo.repositorio import RepositorioCrudo
from vigia.ingest.datasets import DatasetSecop
from vigia.ingest.estado import EstadoCiclo, RegistroDeCiclo, RepositorioEstado
from vigia.ingest.socrata import ClienteSocrata

registro_log = logging.getLogger(__name__)


class RangoInvalido(ValueError):
    """El rango pedido no describe un intervalo recorrible."""


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ResumenCiclo:
    """Lo que hizo un Ciclo. Un Ciclo vacío es un resultado válido."""

    dataset: str
    desde: date
    hasta: date
    paginas: int
    vistos: int
    insertados: int
    duplicados: int
    inicio: datetime
    fin: datetime
    #: Campos que la fuente declara y el esquema esperado no. No detienen el
    #: Ciclo, pero tienen que llegar a los ojos de alguien.
    novedades: tuple[str, ...] = ()
    #: Registros nuevos anteriores a la marca previa: los que se habrían
    #: perdido sin ventana de solapamiento.
    recuperados_por_solapamiento: int = 0
    #: Registros NUNCA VISTOS en el día más viejo de la ventana. Si no es
    #: cero, la ventana se está quedando corta y hay que ensancharla antes de
    #: perder algo. Solo cuenta identidades nuevas: ver `cambiados_en_borde`.
    en_borde_de_ventana: int = 0
    #: Registros que YA TENÍAMOS y que la fuente modificó, en el día más viejo
    #: de la ventana. No es una alarma —no se pierde nada—, pero dice cuántas
    #: modificaciones se habrían dejado de ver con una ventana más corta.
    cambiados_en_borde: int = 0
    #: Registros cuya fecha de hecho no se pudo leer del contenido.
    sin_fecha_de_hecho: int = 0
    #: La marca con la que arrancó el Ciclo. `None` en el primero del dataset.
    cursor_entrada: date | None = None

    @property
    def vacio(self) -> bool:
        """No encontró registros. Distinto de haber fallado: un fallo levanta.

        Un Ciclo que falla nunca produce un ResumenCiclo — la excepción sube y
        no hay resumen que consultar. Que este objeto exista ya significa que
        el recorrido terminó.
        """
        return self.vistos == 0

    def __str__(self) -> str:
        estado = "vacío" if self.vacio else "con registros"
        duracion = (self.fin - self.inicio).total_seconds()
        linea = (
            f"Ciclo {estado} · dataset={self.dataset} "
            f"rango={self.desde.isoformat()}..{self.hasta.isoformat()} "
            f"páginas={self.paginas} vistos={self.vistos} "
            f"insertados={self.insertados} duplicados={self.duplicados} "
            f"duración={duracion:.1f}s"
        )
        # El reporte que ve el operador lo arma `vigia.__main__._describir`
        # sobre el RegistroDeCiclo. Aquí solo la línea base, para logs y
        # depuración: dos formateadores que hay que mantener en sincronía es
        # una forma segura de que diverjan.
        if self.novedades:
            linea += (
                f"\nCampos nuevos en la fuente, sin revisar ({len(self.novedades)}): "
                f"{', '.join(self.novedades)}"
            )
        return linea


def filtro_por_rango(dataset: DatasetSecop, desde: date, hasta: date) -> str:
    """Cláusula ``$where`` que acota el dataset al rango, con ambos extremos incluidos.

    El extremo derecho se expresa como «menor que el día siguiente» para que
    incluya el día completo de ``hasta`` sin depender de la hora que traiga
    cada registro.

    Las fechas de estos datasets son marcas de tiempo flotantes: no llevan zona
    horaria y se leen en la del publicador, es decir hora de Colombia. El rango
    se interpreta en esos mismos términos, no en UTC. `consultado_en`, en
    cambio, sí es UTC: es un instante nuestro, no una fecha de la fuente.
    """
    if desde > hasta:
        raise RangoInvalido(
            f"el rango está invertido: desde={desde.isoformat()} "
            f"es posterior a hasta={hasta.isoformat()}"
        )
    if hasta >= date.max:
        raise RangoInvalido(f"hasta está fuera de rango: {hasta.isoformat()}")

    limite_superior = hasta + timedelta(days=1)
    campo = dataset.campo_fecha_rango
    return (
        f"{campo} >= '{desde.isoformat()}T00:00:00.000' "
        f"AND {campo} < '{limite_superior.isoformat()}T00:00:00.000'"
    )


class ResultadoConNovedades(Protocol):
    novedades: tuple[str, ...]


class Validador(Protocol):
    """Lo que el Ciclo necesita de la validación de esquema."""

    def validar(self, dataset: DatasetSecop) -> ResultadoConNovedades:
        ...


def ingerir(
    *,
    cliente: ClienteSocrata,
    repositorio: RepositorioCrudo,
    dataset: DatasetSecop,
    desde: date,
    hasta: date,
    validador: Validador | None = None,
    marca_previa: date | None = None,
    desde_derivado: bool = False,
    reloj: Callable[[], datetime] = _ahora_utc,
) -> ResumenCiclo:
    """Recorre el dataset en el rango dado y guarda todo en la capa cruda.

    El rango se valida antes de la primera petición: un rango invertido no
    debe costar ni una llamada a la fuente. Con `validador`, el esquema del
    dataset se comprueba también antes de traer nada: si la fuente cambió de
    forma, el Ciclo se detiene sin haber escrito una sola fila.

    Si el Ciclo aborta, lo recorrido hasta ese punto queda registrado en el
    log antes de que la excepción suba. Una ingesta de horas que falla en la
    última página no debe dejar al operador sin saber qué alcanzó a entrar.
    """
    filtro = filtro_por_rango(dataset, desde, hasta)
    # El reloj arranca antes de validar: la consulta de metadatos es parte del
    # Ciclo y puede tardar hasta el tiempo de espera del cliente. Excluirla
    # haría que la duración reportada mintiera justo cuando la fuente va lenta.
    inicio = reloj()
    novedades: tuple[str, ...] = ()
    if validador is not None:
        novedades = tuple(validador.validar(dataset).novedades)

    paginas = 0
    vistos = 0
    insertados = 0
    duplicados = 0
    recuperados = 0
    en_borde = 0
    cambiados_en_borde = 0
    sin_fecha = 0

    try:
        for pagina in cliente.paginas(dataset, filtro=filtro):
            registros = [
                RegistroCrudo.desde_respuesta(
                    dataset=dataset.nombre,
                    contenido=contenido,
                    consultado_en=pagina.consultado_en,
                    campos_identidad=dataset.campos_identidad,
                )
                for contenido in pagina.registros
            ]
            resultado = repositorio.guardar_pagina(registros)
            # El contador avanza solo cuando la página quedó confirmada: lo que
            # se reporta al abortar tiene que ser lo que de verdad entró.
            paginas += 1
            vistos += len(registros)
            insertados += resultado.insertados
            duplicados += resultado.duplicados

            # Las señales se calculan solo sobre lo que de verdad entró: un
            # duplicado en el borde de la ventana es exactamente lo que se
            # espera ver, y contarlo volvería la alarma inútil. `contadas`
            # evita que una llave repetida dentro de la misma página —que el
            # repositorio cuenta como una sola inserción— infle los conteos.
            contadas: set[tuple[str, str]] = set()
            for registro in registros:
                llave = registro.llave[1:]
                if llave in contadas or llave not in resultado.insertadas:
                    continue
                contadas.add(llave)
                fecha = fecha_de_hecho(dataset, registro.contenido)
                if fecha is None:
                    sin_fecha += 1
                    continue
                if marca_previa is not None and fecha < marca_previa:
                    recuperados += 1
                if desde_derivado and fecha == desde:
                    # EL BORDE SE PARTE EN DOS, Y LA ALARMA SOLO MIRA UNA MITAD.
                    #
                    # Un registro que nunca habíamos visto, en el día más viejo
                    # de la ventana, es un aviso de verdad: si hubiera llegado
                    # un día después, se perdía. Uno que ya teníamos y que
                    # cambió no se perdía de nada — solo se ve la versión
                    # nueva. El 2026-09-20 la alarma dijo 1.506 y eran, los
                    # 1.506, de la segunda clase.
                    if registro.id_fila_fuente in resultado.ids_nuevos:
                        en_borde += 1
                    else:
                        cambiados_en_borde += 1
            registro_log.info(
                "página %d confirmada · dataset=%s $offset=%d vistos=%d insertados=%d",
                paginas,
                dataset.nombre,
                pagina.offset,
                len(registros),
                resultado.insertados,
            )
    except Exception:
        registro_log.error(
            "Ciclo interrumpido · dataset=%s páginas confirmadas=%d "
            "vistos=%d insertados=%d duplicados=%d",
            dataset.nombre,
            paginas,
            vistos,
            insertados,
            duplicados,
        )
        raise

    return ResumenCiclo(
        dataset=dataset.nombre,
        desde=desde,
        hasta=hasta,
        paginas=paginas,
        vistos=vistos,
        insertados=insertados,
        duplicados=duplicados,
        inicio=inicio,
        fin=reloj(),
        novedades=novedades,
        recuperados_por_solapamiento=recuperados,
        en_borde_de_ventana=en_borde,
        cambiados_en_borde=cambiados_en_borde,
        sin_fecha_de_hecho=sin_fecha,
        cursor_entrada=marca_previa,
    )


def fecha_de_hecho(dataset: DatasetSecop, contenido: Mapping[str, Any]) -> date | None:
    """La fecha del hecho que trae el registro, o `None` si no se puede leer.

    Socrata devuelve estas fechas como marcas de tiempo flotantes
    (`2026-08-01T00:00:00.000`). No lleva zona: se lee en la del publicador,
    hora de Colombia. Aquí solo interesa el día.

    Devuelve `None` en vez de levantar: un registro sin fecha legible se
    ingiere igual —la capa cruda no juzga— y se cuenta aparte.
    """
    valor = contenido.get(dataset.campo_fecha_rango)
    if not isinstance(valor, str):
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def ejecutar_ciclo(
    *,
    cliente: ClienteSocrata,
    repositorio: RepositorioCrudo,
    estado: RepositorioEstado,
    dataset: DatasetSecop,
    hasta: date,
    ventana_dias: int,
    desde: date | None = None,
    validador: "Validador | None" = None,
    reloj: Callable[[], datetime] = _ahora_utc,
) -> RegistroDeCiclo:
    """Un Ciclo completo: leer la marca, ingerir, y cerrarlo pase lo que pase.

    La marca se retrocede una ventana de solapamiento antes de consultar,
    porque el SECOP publica con retraso: un contrato firmado el día 1 puede
    aparecer el día 12. Volver a leerlo no cuesta filas —la capa cruda lo
    deduplica— pero no leerlo lo pierde para siempre.

    La marca solo avanza si el Ciclo terminó completo. Un Ciclo que aborta deja
    un registro `fallido` con su causa y la marca donde estaba, para que el
    siguiente reanude sin huecos.
    """
    if ventana_dias < 0:
        raise RangoInvalido(f"la ventana no puede ser negativa; se recibió {ventana_dias}")

    inicio = reloj()
    marca = estado.marca(dataset.nombre)
    cursor_entrada = marca.fecha_hecho if marca is not None else None
    desde_derivado = desde is None

    if desde is None:
        if marca is None:
            # Sin marca no hay Ciclo que registrar: nunca llegó a intentarse
            # nada, y el alcance del histórico no se inventa solo.
            raise RangoInvalido(
                f"el dataset {dataset.nombre!r} no tiene marca de agua todavía. "
                f"El primer Ciclo se acota a mano: pasa --desde con la fecha desde la "
                f"que quieres traer el histórico."
            )
        assert cursor_entrada is not None
        if ventana_dias > (cursor_entrada - date.min).days:
            raise RangoInvalido(
                f"la ventana de {ventana_dias} días se sale del calendario desde la "
                f"marca {cursor_entrada.isoformat()}"
            )
        desde = cursor_entrada - timedelta(days=ventana_dias)

    def registrar_fallo(error: BaseException) -> None:
        """Deja constancia del intento, aunque el almacén también esté mal."""
        try:
            estado.cerrar_ciclo(
                RegistroDeCiclo(
                    dataset=dataset.nombre,
                    cursor_entrada=cursor_entrada,
                    cursor_salida=None,
                    desde=desde,
                    hasta=hasta,
                    estado=EstadoCiclo.FALLIDO,
                    inicio=inicio,
                    fin=reloj(),
                    causa=f"{type(error).__name__}: {error}",
                    ventana_dias=ventana_dias,
                    desde_derivado=desde_derivado,
                )
            )
        except Exception:
            # Perder el registro no debe además ocultar la causa original: la
            # excepción que sube tiene que seguir siendo la que detuvo el Ciclo.
            registro_log.exception(
                "no se pudo registrar el Ciclo fallido de %s", dataset.nombre
            )

    if desde > hasta:
        # Una marca por delante del rango es un fallo operativo recurrente —un
        # `--hasta` futuro mal tecleado atasca el dataset— y tiene que verse en
        # la tabla `ciclo`, que es donde AD-4 espera que se vea.
        error = RangoInvalido(
            f"el rango está invertido: desde={desde.isoformat()} "
            f"es posterior a hasta={hasta.isoformat()}"
            + (
                f" (la marca de {dataset.nombre!r} está en "
                f"{cursor_entrada.isoformat()})"
                if desde_derivado and cursor_entrada is not None
                else ""
            )
        )
        registrar_fallo(error)
        raise error

    try:
        resumen = ingerir(
            cliente=cliente,
            repositorio=repositorio,
            dataset=dataset,
            desde=desde,
            hasta=hasta,
            validador=validador,
            marca_previa=cursor_entrada,
            desde_derivado=desde_derivado,
            reloj=reloj,
        )
    except BaseException as error:
        # `BaseException` y no `Exception`: un Ctrl-C a mitad de una ingesta de
        # horas también tiene que dejar rastro.
        registrar_fallo(error)
        raise

    registro = RegistroDeCiclo(
        dataset=dataset.nombre,
        cursor_entrada=cursor_entrada,
        cursor_salida=hasta,
        desde=desde,
        hasta=hasta,
        estado=EstadoCiclo.COMPLETO,
        # El intervalo se mide desde antes de leer la marca: el Ciclo empezó
        # ahí, y los caminos de éxito y de fallo tienen que medir lo mismo.
        inicio=inicio,
        fin=resumen.fin,
        paginas=resumen.paginas,
        vistos=resumen.vistos,
        insertados=resumen.insertados,
        duplicados=resumen.duplicados,
        recuperados_por_solapamiento=resumen.recuperados_por_solapamiento,
        en_borde_de_ventana=resumen.en_borde_de_ventana,
        cambiados_en_borde=resumen.cambiados_en_borde,
        sin_fecha_de_hecho=resumen.sin_fecha_de_hecho,
        novedades=resumen.novedades,
        ventana_dias=ventana_dias,
        desde_derivado=desde_derivado,
    )
    estado.cerrar_ciclo(registro)
    return registro
