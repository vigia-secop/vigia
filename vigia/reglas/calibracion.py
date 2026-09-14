"""Modo calibración sobre un recorte (historia 2.5).

PARA QUÉ. Para poder equivocarse barato. Una Regla nueva se prueba sobre un
pedazo del país antes de soltarla sobre el país entero, y sus Alertas **no
entran a la cola general**: se quedan en el resultado de la calibración, donde
se cuentan, se miran y se tiran si no sirven.

POR QUÉ NO ES UN LUJO NI UN PASO POSTERIOR. La medición de la 2.4 lo dejó a la
vista: el 54,5 % de los procesos adjudicados del país tiene exactamente una
respuesta. Una bandera de «oferente único» sin filtro de modalidad habría
metido 5 415 alertas en la cola el primer día. Nadie revisa 5 415 alertas;
lo que pasa es que se deja de revisar la cola, y con eso se pierde el producto
entero. **La credibilidad de la cuenta se quema una sola vez.**

TRES DISTINCIONES QUE ESTE MÓDULO SOSTIENE, Y QUE SON EL PUNTO:

1. **Un recorte sin resultados NO es un fallo.** Que una Regla no encienda
   sobre Boyacá puede significar que ahí no pasa, o que el umbral está muy
   alto. Las dos son información. Lo que no puede es confundirse con «la
   ingesta se cayó», porque entonces nadie sabe si mirar el dato o el sistema.

2. **Un recorte sin registros que evaluar es otra cosa distinta.** Si el
   recorte quedó vacío —un departamento sin contratación esa semana, un filtro
   mal escrito—, no hay nada que calibrar y decirlo así evita concluir «la
   Regla no encuentra nada» a partir de no haber mirado nada.

3. **Promover a `activa` es un acto explícito.** No se promueve sola por haber
   corrido, ni por tener una tasa bonita. La decisión la toma una persona, y
   el sistema solo se asegura de que haya con qué tomarla.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, Sequence

from vigia.reglas.modelo import (
    ACTIVA, CALIBRACION, Alerta, Regla, TransicionNoPermitida, VersionDeRegla,
)

#: Cuántas Alertas se guardan para mirar con los ojos. No son todas a
#: propósito: una muestra que hay que leer entera no se lee.
MUESTRA_POR_DEFECTO = 25


class RecorteVacio(RuntimeError):
    """El recorte no trajo ni un registro que evaluar.

    Es distinto de «no encendió»: aquí no hubo nada que mirar. Confundirlos
    haría concluir que una Regla no encuentra nada cuando lo que pasó es que
    no se le puso nada delante.
    """


@dataclass(frozen=True)
class Recorte:
    """El pedazo sobre el que se calibra, con su nombre y su razón.

    `motivo` no es documentación de cortesía: seis meses después, la pregunta
    que decide si una calibración vale es «¿sobre qué se calibró y por qué ese
    pedazo?». Un recorte sin motivo no se puede defender ni repetir.
    """

    nombre: str
    motivo: str
    filtros: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.nombre:
            raise ValueError("un recorte necesita nombre")
        if not self.motivo:
            raise ValueError(
                f"el recorte {self.nombre!r} no dice por qué se eligió: sin eso "
                "la calibración no se puede repetir ni defender"
            )
        object.__setattr__(self, "filtros", dict(self.filtros))


@dataclass(frozen=True)
class ResultadoCalibracion:
    """Lo que dejó una corrida de calibración. Todo verificable.

    NO trae las Alertas listas para publicar: trae los conteos, la distribución
    y una muestra. Es deliberado — el propósito es decidir si la Regla sirve,
    no publicar lo que produjo.
    """

    regla_codigo: str
    regla_version: int
    recorte: Recorte
    evaluados: int
    encendidas: int
    distribucion: Mapping[str, int]
    muestra: Sequence[Alerta]
    corrida_en: datetime

    def __post_init__(self) -> None:
        if self.evaluados < 0 or self.encendidas < 0:
            raise ValueError("los conteos de una calibración no pueden ser negativos")
        if self.encendidas > self.evaluados:
            raise ValueError(
                f"{self.encendidas} alertas sobre {self.evaluados} registros: "
                "una Regla no puede encender más veces que las que se evaluó"
            )
        object.__setattr__(self, "distribucion", dict(self.distribucion))
        object.__setattr__(self, "muestra", tuple(self.muestra))

    @property
    def tasa(self) -> float | None:
        """Qué proporción del recorte encendió. `None` si no se evaluó nada."""
        if self.evaluados == 0:
            return None
        return self.encendidas / self.evaluados

    @property
    def sin_resultados(self) -> bool:
        """Se evaluó y no encendió nada. NO es un fallo: es un resultado."""
        return self.evaluados > 0 and self.encendidas == 0

    @property
    def identidades_unicas(self) -> int:
        """Cuántas Alertas distintas hay en la muestra.

        Si fuera menor que el tamaño de la muestra, la identidad determinista
        de la 2.2 estaría rota y la cola se llenaría de repetidas.
        """
        return len({a.identidad for a in self.muestra})

    def resumen(self) -> str:
        """Una línea para leer en una consola, sin adornos ni conclusiones."""
        if self.evaluados == 0:
            return f"{self.recorte.nombre}: el recorte no trajo registros que evaluar."
        if self.sin_resultados:
            return (
                f"{self.recorte.nombre}: {self.evaluados} registros evaluados, "
                "ninguno encendió. Recorte sin resultados — no es un fallo."
            )
        porcentaje = f"{100 * self.tasa:.1f}".replace(".", ",")
        return (
            f"{self.recorte.nombre}: {self.encendidas} de {self.evaluados} "
            f"encendieron ({porcentaje} %)."
        )


def calibrar(
    registros: Iterable[Mapping[str, Any]], *,
    regla: Regla,
    version: VersionDeRegla,
    recorte: Recorte,
    evaluador: Callable[..., Alerta | None],
    consultado_en: datetime,
    momento: datetime,
    dimension: str | None = None,
    tamano_muestra: int = MUESTRA_POR_DEFECTO,
) -> ResultadoCalibracion:
    """Corre una Regla sobre un recorte SIN mandar nada a la cola general.

    Las Alertas producidas se quedan aquí dentro. Es la diferencia entre probar
    y publicar, y el módulo entero existe para que esa diferencia sea
    estructural y no una promesa.

    `dimension` es el campo por el que se agrupa la distribución —modalidad,
    departamento, entidad—. Sin distribución, una tasa global esconde que la
    Regla enciende sobre una sola cosa.
    """
    if regla.estado != CALIBRACION:
        raise TransicionNoPermitida(
            f"{regla.codigo!r} está en «{regla.estado}»: solo se calibra una "
            "Regla en estado «calibracion», para que no se pruebe sin querer "
            "algo que ya está activo"
        )

    evaluados = 0
    encendidas: list[Alerta] = []
    distribucion: dict[str, int] = {}

    for contenido in registros:
        evaluados += 1
        alerta = evaluador(
            contenido, regla=regla, version=version,
            consultado_en=consultado_en, momento=momento,
        )
        if alerta is None:
            continue
        encendidas.append(alerta)
        if dimension:
            clave = str(contenido.get(dimension) or "(sin dato)")
            distribucion[clave] = distribucion.get(clave, 0) + 1

    if evaluados == 0:
        raise RecorteVacio(
            f"el recorte {recorte.nombre!r} no trajo ni un registro. No es que "
            "la Regla no encontrara nada: es que no se le puso nada delante."
        )

    # La muestra sale del principio y del final por valor de identidad, no al
    # azar: así dos calibraciones sobre los mismos datos muestran lo mismo y se
    # pueden comparar. Una muestra aleatoria haría irrepetible la revisión.
    ordenadas = sorted(encendidas, key=lambda a: a.identidad)
    muestra = ordenadas[:tamano_muestra]

    regla.corrio_en_calibracion = True

    return ResultadoCalibracion(
        regla_codigo=regla.codigo,
        regla_version=version.version,
        recorte=recorte,
        evaluados=evaluados,
        encendidas=len(encendidas),
        distribucion=distribucion,
        muestra=muestra,
        corrida_en=momento,
    )


def promover(regla: Regla, resultado: ResultadoCalibracion | None) -> None:
    """Sube una Regla a `activa`. Exige una calibración de esta misma Regla.

    Se pide el resultado —y no solo la bandera `corrio_en_calibracion`— para
    que activar sea un acto con la evidencia en la mano. Quien la promueve
    tiene que haber tenido delante el número.
    """
    if resultado is None:
        raise TransicionNoPermitida(
            f"{regla.codigo!r} no se activa sin una calibración delante"
        )
    if resultado.regla_codigo != regla.codigo:
        raise TransicionNoPermitida(
            f"la calibración es de {resultado.regla_codigo!r}, no de {regla.codigo!r}"
        )
    if resultado.evaluados == 0:
        raise TransicionNoPermitida(
            "la calibración no evaluó ningún registro: no hay con qué decidir"
        )
    regla.mover_a(ACTIVA)
