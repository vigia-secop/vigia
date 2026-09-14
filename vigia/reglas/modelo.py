"""Reglas versionadas, Alertas con identidad y Expedientes (historias 2.1-2.3).

TRES INVARIANTES, Y NINGUNO ES DECORATIVO.

**Una Regla no se edita: se versiona.** Cambiar un umbral crea una versión
nueva y deja intacta la anterior. Sin eso, una Alerta emitida el martes no se
puede explicar el jueves, porque el umbral que la disparó ya no existe en
ninguna parte. Y explicar una Alerta meses después es literalmente el trabajo.

**Una Alerta tiene identidad determinista.** El mismo registro, la misma
versión de Regla y los mismos valores disparadores producen SIEMPRE el mismo
identificador. Reprocesar no duplica. Es la misma lección que costó la
migración 005: si la identidad depende de algo que cambia entre corridas
—una hora, un contador, un `:id` de la plataforma— no es identidad.

**Sin Expediente completo no hay Alerta.** No es una validación de formulario:
es la diferencia entre una afirmación defendible y una acusación sin papeles.
Si falta un campo, la emisión falla y la Alerta no se crea. Es preferible una
Alerta que no salió a una Alerta que no se puede sostener.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping

#: Los cuatro estados de una Regla. El orden es el del ciclo de vida.
BORRADOR = "borrador"
CALIBRACION = "calibracion"
ACTIVA = "activa"
RETIRADA = "retirada"

ESTADOS = (BORRADOR, CALIBRACION, ACTIVA, RETIRADA)

#: Transiciones permitidas. Lo que no está aquí no se puede hacer.
#:
#: `borrador -> activa` NO está, y es el corazón de la 2.5: una Regla que
#: nunca corrió sobre un recorte no se suelta al país. Inundar la cola con una
#: bandera sin calibrar quema la credibilidad de la cuenta una sola vez.
TRANSICIONES = {
    BORRADOR: {CALIBRACION, RETIRADA},
    CALIBRACION: {ACTIVA, BORRADOR, RETIRADA},
    ACTIVA: {RETIRADA, CALIBRACION},
    RETIRADA: set(),
}


class TransicionNoPermitida(ValueError):
    """Se intentó mover una Regla a un estado al que no puede ir desde donde está."""


class ExpedienteIncompleto(ValueError):
    """Falta sustento. La Alerta no se crea.

    No es un error de programación que haya que tolerar: es la barrera que
    impide que exista una afirmación sin con qué defenderla.
    """


class ReglaNoModificable(ValueError):
    """Se intentó cambiar una versión ya emitida. Las versiones son inmutables."""


def _canonizar(valor: Any) -> Any:
    """Deja un valor en una forma comparable y estable entre corridas.

    Los `Decimal` y las fechas se escriben como texto porque su repr cambia
    con el tipo que los cargó —el mismo valor leído de JSON y de PostgreSQL no
    es el mismo objeto—, y la identidad no puede depender de eso.
    """
    if isinstance(valor, Mapping):
        return {str(k): _canonizar(valor[k]) for k in sorted(valor, key=str)}
    if isinstance(valor, (list, tuple)):
        return [_canonizar(v) for v in valor]
    if isinstance(valor, Decimal):
        return format(valor.normalize(), "f")
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, bool) or valor is None:
        return valor
    if isinstance(valor, (int, float, str)):
        return valor
    return str(valor)


def _huella(contenido: Any) -> str:
    return hashlib.sha256(
        json.dumps(_canonizar(contenido), sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class TopeNormativo:
    """Un valor que manda la norma, no el código: una cuantía por modalidad.

    Lleva `vigente_desde` porque las cuantías cambian con la ley y con el
    presupuesto anual. Un tope sin fecha convierte cualquier serie histórica
    en algo incomparable: la misma Regla, el mismo umbral, y resultados que no
    se pueden poner uno al lado del otro.
    """

    concepto: str
    ambito: str
    valor: Decimal
    unidad: str
    vigente_desde: date
    fuente: str

    def __post_init__(self) -> None:
        if not self.concepto or not self.ambito:
            raise ValueError("un tope normativo necesita concepto y ámbito")
        if not self.fuente:
            raise ValueError(
                f"el tope {self.concepto!r} no dice de dónde sale: sin fuente "
                "citable no se puede defender el número"
            )

    @property
    def clave(self) -> str:
        return f"{self.concepto}|{self.ambito}"


@dataclass(frozen=True)
class VersionDeRegla:
    """Una versión concreta de una Regla, con sus umbrales congelados.

    Es inmutable a propósito. Cambiar un umbral no modifica esta: crea otra.
    """

    codigo: str
    version: int
    umbrales: Mapping[str, Any]
    creada_en: datetime
    nota: str = ""

    def __post_init__(self) -> None:
        if not self.codigo:
            raise ValueError("una versión de Regla necesita el código de su Regla")
        if self.version < 1:
            raise ValueError(f"versión inválida: {self.version}")
        if not self.umbrales:
            raise ValueError(
                f"la versión {self.version} de {self.codigo!r} no tiene umbrales: "
                "una Regla sin umbral no se puede calibrar ni explicar"
            )
        # Una vista de solo lectura, no una copia mutable. `frozen=True`
        # impide reasignar el atributo pero no tocar el diccionario por dentro,
        # y una versión cuyos umbrales se pueden editar no está congelada:
        # sería exactamente el agujero que la 2.1 existe para tapar.
        object.__setattr__(self, "umbrales", MappingProxyType(dict(self.umbrales)))

    @property
    def huella(self) -> str:
        """Identifica a la VERSIÓN por sus umbrales, no por su número.

        Así, dos versiones con los mismos umbrales dan la misma huella y se
        puede detectar que un «cambio» no cambió nada.
        """
        return _huella({"codigo": self.codigo, "umbrales": self.umbrales})

    @property
    def etiqueta(self) -> str:
        return f"{self.codigo}@v{self.version}"


@dataclass
class Regla:
    """Una Regla con su historia de versiones y su estado.

    Los umbrales viven en las versiones, no aquí: preguntarle a la Regla por
    «su» umbral sin decir qué versión sería justo la ambigüedad que esta
    historia existe para quitar.
    """

    codigo: str
    nombre: str
    descripcion: str
    estado: str = BORRADOR
    versiones: list[VersionDeRegla] = field(default_factory=list)
    #: Si alguna vez corrió en calibración. La 2.5 lo exige para activar.
    corrio_en_calibracion: bool = False

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS:
            raise ValueError(f"estado desconocido: {self.estado!r}")
        if not self.codigo or not self.nombre:
            raise ValueError("una Regla necesita código y nombre")

    @property
    def vigente(self) -> VersionDeRegla:
        if not self.versiones:
            raise ValueError(f"la Regla {self.codigo!r} no tiene ninguna versión")
        return self.versiones[-1]

    def version(self, numero: int) -> VersionDeRegla:
        """Una versión por su número. Las viejas se conservan y se consultan."""
        for v in self.versiones:
            if v.version == numero:
                return v
        raise KeyError(f"{self.codigo!r} no tiene versión {numero}")

    def nueva_version(
        self, umbrales: Mapping[str, Any], *, momento: datetime, nota: str = ""
    ) -> VersionDeRegla:
        """Congela unos umbrales nuevos. NUNCA toca las versiones anteriores."""
        siguiente = VersionDeRegla(
            codigo=self.codigo,
            version=len(self.versiones) + 1,
            umbrales=umbrales,
            creada_en=momento,
            nota=nota,
        )
        if self.versiones and self.versiones[-1].huella == siguiente.huella:
            raise ReglaNoModificable(
                f"los umbrales de {self.codigo!r} son idénticos a los de la "
                f"versión {self.versiones[-1].version}: no hay nada que versionar"
            )
        self.versiones.append(siguiente)
        return siguiente

    def mover_a(self, destino: str) -> None:
        if destino not in ESTADOS:
            raise ValueError(f"estado desconocido: {destino!r}")
        if destino not in TRANSICIONES[self.estado]:
            raise TransicionNoPermitida(
                f"{self.codigo!r} no puede pasar de «{self.estado}» a «{destino}»"
            )
        if destino == ACTIVA and not self.corrio_en_calibracion:
            raise TransicionNoPermitida(
                f"{self.codigo!r} no ha corrido nunca en calibración. Activarla "
                "sería soltar al país una bandera que nadie ha visto funcionar."
            )
        if destino == CALIBRACION and not self.versiones:
            raise TransicionNoPermitida(
                f"{self.codigo!r} no tiene umbrales que calibrar"
            )
        self.estado = destino


@dataclass(frozen=True)
class Expediente:
    """El sustento de una Alerta. Sin él completo, la Alerta no existe.

    Cada campo responde a una pregunta que alguien va a hacer meses después:
    de dónde salió el dato, qué Regla y con qué umbral, qué valores concretos
    lo dispararon, y cuándo se consultó la fuente.
    """

    id_registro_fuente: str
    dataset: str
    regla_codigo: str
    regla_version: int
    umbral_aplicado: Mapping[str, Any]
    valores_disparadores: Mapping[str, Any]
    consultado_en: datetime
    #: El enlace público del proceso en el SECOP, cuando la fuente lo trae.
    #: No es obligatorio porque no todos los registros lo tienen; cuando está,
    #: es lo que permite a cualquiera ir a ver el expediente original.
    url_proceso: str | None = None

    def __post_init__(self) -> None:
        faltan = [
            nombre for nombre in (
                "id_registro_fuente", "dataset", "regla_codigo",
                "umbral_aplicado", "valores_disparadores", "consultado_en",
            ) if not getattr(self, nombre)
        ]
        if self.regla_version is None or self.regla_version < 1:
            faltan.append("regla_version")
        if faltan:
            raise ExpedienteIncompleto(
                "el expediente no se puede sostener, le falta: "
                + ", ".join(sorted(faltan))
            )
        object.__setattr__(self, "umbral_aplicado",
                           MappingProxyType(dict(self.umbral_aplicado)))
        object.__setattr__(self, "valores_disparadores",
                           MappingProxyType(dict(self.valores_disparadores)))

    @property
    def completo(self) -> bool:
        return True  # si existe, está completo: `__post_init__` no admite otra cosa


@dataclass(frozen=True)
class Alerta:
    """Un indicador estadístico con su sustento. NO es una acusación.

    Su identificador se deriva del contenido, así que reprocesar el mismo
    ciclo no crea una segunda.
    """

    expediente: Expediente
    emitida_en: datetime

    @property
    def identidad(self) -> str:
        """Determinista: mismo registro + misma versión + mismos valores.

        `emitida_en` NO entra. Es lo que permite reprocesar sin ensuciar la
        cola, y es exactamente el error que la capa cruda cometió con el `:id`
        de Socrata: una identidad que cambia entre corridas no identifica.
        """
        e = self.expediente
        return _huella({
            "registro": e.id_registro_fuente,
            "dataset": e.dataset,
            "regla": e.regla_codigo,
            "version": e.regla_version,
            "disparadores": e.valores_disparadores,
        })

    @property
    def etiqueta(self) -> str:
        return f"{self.expediente.regla_codigo}@v{self.expediente.regla_version}"


def emitir(
    regla: Regla, version: VersionDeRegla, *,
    id_registro_fuente: str,
    dataset: str,
    valores_disparadores: Mapping[str, Any],
    consultado_en: datetime,
    momento: datetime,
    url_proceso: str | None = None,
) -> Alerta:
    """Crea una Alerta con su Expediente, o levanta.

    Que el Expediente se construya AQUÍ y no lo pase quien llama es
    deliberado: así ninguna Regla puede emitir sin sustento por descuido.
    """
    if version.codigo != regla.codigo:
        raise ValueError(
            f"la versión es de {version.codigo!r} y la Regla es {regla.codigo!r}"
        )
    expediente = Expediente(
        id_registro_fuente=id_registro_fuente,
        dataset=dataset,
        regla_codigo=regla.codigo,
        regla_version=version.version,
        umbral_aplicado=version.umbrales,
        valores_disparadores=valores_disparadores,
        consultado_en=consultado_en,
        url_proceso=url_proceso,
    )
    return Alerta(expediente=expediente, emitida_en=momento)
