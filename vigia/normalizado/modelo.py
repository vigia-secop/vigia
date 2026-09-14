"""Contratos y Procesos tipados, derivados de la capa cruda.

Convertir es leer valores de un JSONB donde **todo llega como texto** y donde
las claves nulas sencillamente no aparecen. Ninguna conversión levanta por un
valor ilegible: se guarda `None` y el registro entra igual. La capa normalizada
no juzga la calidad del dato, la expone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from vigia.crudo.modelo import RegistroCrudo
from vigia.normalizado.territorio import Territorio, desde_contenido as territorio_de
from vigia.normalizado.proveedor import (
    DocumentoNoUtilizable,
    CAMPO_NOMBRE,
    TIPO_GRUPO_PROVISIONAL,
    identidad_del_contrato,
    normalizar_texto,
)

#: Campo de Contratos que porta la llave de cruce. El nombre engaña: NO
#: contiene un `id_del_proceso`, contiene un `id_del_portafolio`. Medido el
#: 2026-09-03; ver `sprint-change-proposal-2026-09-03.md`.
CAMPO_LLAVE_CONTRATO = "proceso_de_compra"

#: Campo de Procesos contra el que se cruza. Mismo espacio `CO1.BDOS.`.
CAMPO_LLAVE_PROCESO = "id_del_portafolio"


class RegistroSinIdentidadNormalizada(ValueError):
    """El registro crudo no trae el identificador que la capa normalizada usa
    como llave primaria.

    No es tolerable: sin él, dos versiones del mismo contrato entrarían como
    filas distintas y los conteos de cualquier Regla saldrían inflados.
    """


def _texto(contenido: Mapping[str, Any], campo: str) -> str | None:
    """El valor del campo como texto limpio, o `None` si no sirve.

    Una cadena vacía o de solo espacios se trata como ausente: la fuente usa
    ambas cosas para lo mismo, y distinguirlas aquí solo mueve el problema
    aguas abajo.
    """
    valor = contenido.get(campo)
    if not isinstance(valor, str):
        return None
    limpio = valor.strip()
    return limpio or None


def _fecha(contenido: Mapping[str, Any], campo: str) -> date | None:
    """El día de una marca de tiempo flotante de Socrata (`2026-08-01T00:00:00.000`).

    Sin zona horaria: se lee en la del publicador. Aquí solo interesa el día.
    """
    crudo = _texto(contenido, campo)
    if crudo is None:
        return None
    try:
        return date.fromisoformat(crudo[:10])
    except ValueError:
        return None


def _decimal(contenido: Mapping[str, Any], campo: str) -> Decimal | None:
    """Un valor monetario. Llega como texto y puede traer basura."""
    crudo = _texto(contenido, campo)
    if crudo is None:
        return None
    try:
        return Decimal(crudo)
    except (InvalidOperation, ValueError):
        return None


def _booleano(contenido: Mapping[str, Any], campo: str) -> bool | None:
    """Un sí/no del SECOP, que llega como «Si» o «No» en español."""
    crudo = _texto(contenido, campo)
    if crudo is None:
        return None
    normalizado = crudo.casefold()
    if normalizado in {"si", "sí", "true", "t", "1"}:
        return True
    if normalizado in {"no", "false", "f", "0"}:
        return False
    return None


@dataclass(frozen=True)
class ProcesoNormalizado:
    """Un Proceso de contratación, tipado.

    Su identidad es `id_del_proceso`, que **no es llave primaria en la
    fuente**: el dataset trae una fila por adjudicación. Deduplicar es
    responsabilidad de quien normaliza, no de esta clase.
    """

    id_del_proceso: str
    id_del_portafolio: str | None
    referencia: str | None
    nit_entidad: str | None
    nombre_entidad: str | None
    fecha_de_publicacion: date | None
    modalidad: str | None
    estado: str | None
    adjudicado: bool | None
    id_fila_fuente: str
    hash_contenido: str
    normalizado_en: datetime

    @classmethod
    def desde_crudo(
        cls, registro: RegistroCrudo, *, momento: datetime
    ) -> "ProcesoNormalizado":
        contenido = registro.contenido
        identificador = _texto(contenido, "id_del_proceso")
        if identificador is None:
            raise RegistroSinIdentidadNormalizada(
                f"el proceso {registro.id_fila_fuente!r} no trae `id_del_proceso`"
            )
        return cls(
            id_del_proceso=identificador,
            id_del_portafolio=_texto(contenido, CAMPO_LLAVE_PROCESO),
            referencia=_texto(contenido, "referencia_del_proceso"),
            nit_entidad=_texto(contenido, "nit_entidad"),
            nombre_entidad=_texto(contenido, "entidad"),
            fecha_de_publicacion=_fecha(contenido, "fecha_de_publicacion_del"),
            modalidad=_texto(contenido, "modalidad_de_contratacion"),
            estado=_texto(contenido, "estado_del_procedimiento"),
            adjudicado=_booleano(contenido, "adjudicado"),
            id_fila_fuente=registro.id_fila_fuente,
            hash_contenido=registro.hash_contenido,
            normalizado_en=momento,
        )


@dataclass(frozen=True)
class ContratoNormalizado:
    """Un Contrato, tipado, con su llave de cruce y el Proceso que encontró.

    `id_del_proceso` en `None` con `proceso_de_compra` poblado es un
    **huérfano**: se conserva y es consultable. Nunca se descarta.
    """

    id_contrato: str
    proceso_de_compra: str | None
    id_del_proceso: str | None
    referencia: str | None
    nit_entidad: str | None
    nombre_entidad: str | None
    valor: Decimal | None
    fecha_de_firma: date | None
    estado: str | None
    #: Identidad canónica del proveedor, o `None` cuando el documento que trae
    #: la fuente no sirve para identificar a nadie —un centinela como
    #: «No Definido»— y el adjudicatario tampoco viene marcado como grupo.
    #: Medido: ese caso son casi enteramente borradores y cancelados, papeles
    #: que nunca adjudicaron a nadie. Cuando sí es un grupo (Unión Temporal o
    #: Consorcio) el contrato recibe identidad PROVISIONAL, propia y marcada,
    #: para que se cuente en vez de desaparecer. El contrato se conserva igual
    #: en los dos casos.
    proveedor_tipo: str | None
    proveedor_numero: str | None
    #: La razón social tal como la escribió la entidad, normalizada solo en
    #: mayúsculas y espacios. Viaja con el contrato porque el Expediente de la
    #: épica 2 la necesita y porque permite agrupar sin releer el crudo.
    proveedor_nombre: str | None
    #: Orden administrativo declarado: NACIONAL, TERRITORIAL o
    #: CORPORACION AUTONOMA. `None` cuando la fuente no lo dice, que NO es lo
    #: mismo que territorial. Separar los órdenes es lo que permite mirar el
    #: corte del 7 de agosto de 2026 sin confundir el cambio de gobierno
    #: nacional con el ritmo de alcaldías y gobernaciones, que no cambiaron.
    orden: str | None
    #: Código DIVIPOLA de departamento, o `None`. El nombre acompaña siempre
    #: al código; el municipio va con nombre y sin código a propósito.
    departamento_codigo: str | None
    departamento_nombre: str | None
    municipio_nombre: str | None
    id_fila_fuente: str
    hash_contenido: str
    normalizado_en: datetime

    def __post_init__(self) -> None:
        if self.id_del_proceso is not None and self.proceso_de_compra is None:
            raise ValueError(
                f"el contrato {self.id_contrato!r} tiene proceso enlazado sin "
                "llave de cruce: el enlace se inventó en alguna parte"
            )

    @property
    def huerfano(self) -> bool:
        """Trae llave de cruce pero no encontró Proceso."""
        return self.proceso_de_compra is not None and self.id_del_proceso is None

    @property
    def sin_proveedor(self) -> bool:
        """No se le pudo dar identidad de proveedor, ni siquiera provisional.

        Es la población que «concentración por proveedor» (4.3) no puede
        vigilar, así que tiene que ser medible y no quedar escondida.
        """
        return self.proveedor_tipo is None

    @property
    def proveedor_provisional(self) -> bool:
        """Su proveedor es una Unión Temporal o Consorcio todavía sin nombre.

        El contrato se cuenta y se suma —no queda volando—, pero su identidad
        vale para un solo contrato, así que la 4.3 no puede medirle
        concentración. Se reporta aparte precisamente por eso.
        """
        return self.proveedor_tipo == TIPO_GRUPO_PROVISIONAL

    @property
    def sin_territorio(self) -> bool:
        """No se le pudo poner código de departamento.

        Es la población que ninguna Regla con corte territorial puede mirar.
        Medido en la fuente: el 1,4 % trae «No Definido» como departamento.
        """
        return self.departamento_codigo is None

    @property
    def sin_llave_de_cruce(self) -> bool:
        """Ni siquiera trae la llave. Es un fallo distinto al de ser huérfano.

        Contarlos juntos esconde este, que es el modo de fallo que vació a
        `ultima_actualizacion`: un campo declarado en el esquema que llega
        sistemáticamente vacío.
        """
        return self.proceso_de_compra is None

    @classmethod
    def desde_crudo(
        cls, registro: RegistroCrudo, *, momento: datetime
    ) -> "ContratoNormalizado":
        contenido = registro.contenido
        identificador = _texto(contenido, "id_contrato")
        if identificador is None:
            raise RegistroSinIdentidadNormalizada(
                f"el contrato {registro.id_fila_fuente!r} no trae `id_contrato`"
            )
        # La identidad del proveedor se resuelve aquí porque solo hace falta
        # esta fila. Un documento inservible no es un error: es un hecho sobre
        # el dato, y el contrato entra igual sin proveedor.
        try:
            proveedor = identidad_del_contrato(contenido)
        except DocumentoNoUtilizable:
            proveedor = None

        territorio = territorio_de(contenido)

        return cls(
            id_contrato=identificador,
            proceso_de_compra=_texto(contenido, CAMPO_LLAVE_CONTRATO),
            # El enlace no se resuelve aquí: esta clase solo sabe leer una
            # fila. Cruzar exige el universo de Procesos, y eso es del módulo
            # `cruce`.
            id_del_proceso=None,
            referencia=_texto(contenido, "referencia_del_contrato"),
            nit_entidad=_texto(contenido, "nit_entidad"),
            nombre_entidad=_texto(contenido, "nombre_entidad"),
            valor=_decimal(contenido, "valor_del_contrato"),
            fecha_de_firma=_fecha(contenido, "fecha_de_firma"),
            estado=_texto(contenido, "estado_contrato"),
            proveedor_tipo=proveedor.tipo if proveedor else None,
            proveedor_numero=proveedor.numero if proveedor else None,
            proveedor_nombre=normalizar_texto(contenido.get(CAMPO_NOMBRE)),
            orden=territorio.orden,
            departamento_codigo=territorio.departamento_codigo,
            departamento_nombre=territorio.departamento_nombre,
            municipio_nombre=territorio.municipio_nombre,
            id_fila_fuente=registro.id_fila_fuente,
            hash_contenido=registro.hash_contenido,
            normalizado_en=momento,
        )

    def enlazado_a(self, id_del_proceso: str) -> "ContratoNormalizado":
        """Copia con el Proceso resuelto."""
        return ContratoNormalizado(
            id_contrato=self.id_contrato,
            proceso_de_compra=self.proceso_de_compra,
            id_del_proceso=id_del_proceso,
            referencia=self.referencia,
            nit_entidad=self.nit_entidad,
            nombre_entidad=self.nombre_entidad,
            valor=self.valor,
            fecha_de_firma=self.fecha_de_firma,
            estado=self.estado,
            proveedor_tipo=self.proveedor_tipo,
            proveedor_numero=self.proveedor_numero,
            proveedor_nombre=self.proveedor_nombre,
            orden=self.orden,
            departamento_codigo=self.departamento_codigo,
            departamento_nombre=self.departamento_nombre,
            municipio_nombre=self.municipio_nombre,
            id_fila_fuente=self.id_fila_fuente,
            hash_contenido=self.hash_contenido,
            normalizado_en=self.normalizado_en,
        )
