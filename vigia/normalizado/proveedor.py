"""Identidad canónica de Proveedor (historia 1.5).

El mismo contratista aparece en el SECOP con el documento escrito de varias
formas y con la razón social escrita de varias más. Sin reducirlo a una
identidad, «concentración por proveedor» cuenta a uno como tres y no detecta
nada.

LO QUE SE MIDIÓ ANTES DE DISEÑAR (datos.gov.co, dataset `jbjy-vk9h`,
2026-09-04, sobre los ~6,02 millones de contratos del histórico nacional):

- **El 82,4 % de los contratos son con personas naturales**: 4 929 133 con
  Cédula de Ciudadanía frente a 900 513 con NIT. El proveedor típico del SECOP
  no es una empresa, es una persona.
- **175 836 contratos traen la cadena literal «No Definido» como documento.**
  No es un número mal escrito: es un centinela.
- De los documentos de tipo NIT, el 90 % mide exactamente 9 caracteres —el NIT
  colombiano sin dígito de verificación—. Los de 11 caracteres, que a primera
  vista parecían `NNNNNNNNN-D`, resultaron ser todos la cadena «No Definido»,
  que mide 11.

EL ERROR QUE ESTO EVITA. Canonizar «a lo bruto» —quitar lo que no sea letra o
número y pasar a mayúsculas— convertiría esos 175 836 contratos en un único
proveedor `NODEFINIDO`, que aparecería al instante como el contratista más
concentrado de Colombia. Una alerta de primera magnitud, y falsa entera.

QUÉ SON EN REALIDAD ESOS 175 836 (medido el 2026-09-04, después de haberlo
afirmado sin medirlo — ver la corrección en `deferred-work.md`):

| Estado del contrato        | Contratos |
|----------------------------|-----------|
| Borrador                   |    91 448 |
| Cancelado                  |    69 095 |
| **subtotal: no es contrato** | **160 543** (91,3 %) |
| Modificado, terminado, En ejecución, Cerrado, Aprobado, Suspendido, … | **15 293** (8,7 %) |

Los 160 543 primeros **no son contratos sin proveedor: son registros que nunca
llegaron a tener proveedor**, porque el borrador no se adjudicó y el cancelado
se murió antes. Contarlos como «hueco de vigilancia» infla el problema diez
veces con papeles que no existen en el mundo.

Y de los 15 293 que sí son contratos, **15 291 —el 99,99 %— traen
`es_grupo = 'Si'`**: son Uniones Temporales y Consorcios. Ahí sí, y solo ahí,
está el hueco real.

Para dimensionarlo: los contratos de grupo son 39 767 en el histórico, y
25 866 de ellos **sí traen NIT** —una unión temporal en Colombia tiene NIT
propio— y por tanto ya se agrupan bien. El hueco no es «las uniones
temporales»: es la parte de ellas a la que la entidad no le diligenció el
documento.

QUÉ SE HACE CON ELLOS. No quedar fuera del conteo. Ver
`identidad_del_contrato` y `TIPO_GRUPO_PROVISIONAL` más abajo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Mapping

#: Campos de Contratos que traen la identidad del proveedor.
CAMPO_TIPO_DOCUMENTO = "tipodocproveedor"
CAMPO_DOCUMENTO = "documento_proveedor"
CAMPO_NOMBRE = "proveedor_adjudicado"

#: Campo con el que la fuente marca que el adjudicatario es una Unión Temporal
#: o un Consorcio (un «grupo» de proveedores, en el lenguaje del SECOP).
CAMPO_ES_GRUPO = "es_grupo"
VALOR_ES_GRUPO = "SI"

#: El identificador del contrato. Es lo que le presta el número a la identidad
#: provisional de un grupo sin documento.
CAMPO_ID_CONTRATO = "id_contrato"

#: Tipo de documento reservado para la identidad provisional de un grupo.
#:
#: No es un tipo de documento de la DIAN ni de la fuente, y por eso no puede
#: chocar con ninguno: es una marca de que **esta identidad identifica a un
#: contrato, no a un contratista**. Se lee tal cual en los reportes, a
#: propósito, para que nadie la confunda con una identidad de verdad.
TIPO_GRUPO_PROVISIONAL = "UNION TEMPORAL O CONSORCIO SIN DOCUMENTO"

#: Longitud del NIT colombiano sin dígito de verificación.
LARGO_NIT = 9

#: Con qué empieza un NIT de persona JURÍDICA en Colombia.
#:
#: No es folclore: se midió. De 25 documentos de tipo NIT y diez dígitos
#: tomados de la fuente el 2026-09-04, los **16 que empiezan por 8 o 9
#: verificaron su dígito de verificación — los 16 de 16**. De los 9 que
#: empiezan por 1, solo verificó 1: exactamente lo que da el azar (una de cada
#: once). Es decir, esos nueve no son NIT con DV: son cédulas de diez dígitos
#: mal etiquetadas como NIT, y quitarles el último dígito las convertiría en
#: otra persona.
PRIMEROS_DIGITOS_NIT_JURIDICO = ("8", "9")

#: Pesos del algoritmo del dígito de verificación del NIT (DIAN), en el orden
#: en que se aplican: el primero al dígito de MÁS A LA DERECHA.
#:
#: El orden importa y es fácil equivocarlo. La primera versión de este módulo
#: los tenía al revés y ninguna verificación cuadraba.
_PESOS_DV = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)

_NO_ALFANUMERICO = re.compile(r"[^0-9A-Za-z]")


class DocumentoNoUtilizable(ValueError):
    """El documento no sirve como identidad y el contrato no puede agruparse.

    No es un error del programa: es un hecho sobre el dato. El contrato se
    conserva y se cuenta aparte, igual que los huérfanos de la 1.4.
    """


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def normalizar_texto(valor: object) -> str | None:
    """Texto en mayúsculas, sin tildes ni espacios de más, o `None`."""
    if not isinstance(valor, str):
        return None
    limpio = _sin_tildes(valor).upper()
    limpio = " ".join(limpio.split())
    return limpio or None


def digito_de_verificacion(nit: str) -> int | None:
    """El DV que le corresponde a un NIT según el algoritmo de la DIAN.

    Devuelve `None` si el valor no es una cadena de dígitos utilizable. El
    algoritmo recorre el número de derecha a izquierda multiplicando por una
    tabla de pesos fija; el resto entre 11 decide el dígito.
    """
    if not nit.isdigit() or not 1 <= len(nit) <= len(_PESOS_DV):
        return None
    suma = sum(
        int(digito) * peso
        for digito, peso in zip(reversed(nit), _PESOS_DV)
    )
    resto = suma % 11
    return resto if resto < 2 else 11 - resto


def es_nit(tipo_normalizado: str | None) -> bool:
    """Si el tipo de documento declarado es un NIT.

    Importa porque la regla del dígito de verificación **solo** se puede
    aplicar a NIT. Una cédula de diez dígitos cuyo último dígito coincida por
    azar con el DV de los nueve anteriores —una de cada once— perdería un
    dígito y se fundiría con otra persona.
    """
    return tipo_normalizado is not None and tipo_normalizado.startswith("NIT")


@dataclass(frozen=True)
class IdentidadProveedor:
    """Lo que agrupa a un proveedor: el tipo de documento y su número canónico.

    El tipo forma parte de la identidad a propósito. Un NIT `900123456` y una
    cédula `900123456` son dos entidades distintas del mundo, y fundirlas por
    compartir dígitos inventaría una concentración que no existe.
    """

    tipo: str
    numero: str

    def __post_init__(self) -> None:
        if not self.tipo or not self.numero:
            raise ValueError("una identidad de proveedor no puede ir vacía")

    @property
    def clave(self) -> str:
        return f"{self.tipo}|{self.numero}"

    @property
    def provisional(self) -> bool:
        """Identifica a un contrato, no a un contratista.

        Una identidad provisional **no puede concentrar nada**: por
        construcción hay exactamente una por contrato. Sirve para que el
        contrato se cuente, se sume y se vea; no para acusar a nadie. La 4.3
        tiene que excluirla de «concentración por proveedor» y, a la vez,
        reportar cuánto vale, que es justo lo contrario de esconderla.
        """
        return self.tipo == TIPO_GRUPO_PROVISIONAL


def canonizar_documento(
    documento: object, *, tipo: object = None
) -> IdentidadProveedor:
    """Reduce documento y tipo a una identidad única, o levanta.

    Las tres reglas, en orden:

    1. **Se quitan puntos, guiones y espacios**, y se pasa a mayúsculas. Es el
       primer criterio de aceptación de la historia.
    2. **Un documento sin un solo dígito no es un documento.** Es lo que
       descarta «No Definido», «NO APLICA», «N/A» y compañía sin tener que
       mantener una lista de centinelas que siempre se queda corta. Fue la
       medición de los 175 836 contratos la que hizo evidente que hacía falta.
    3. **Solo si el tipo es NIT, el número empieza por 8 o 9, y el décimo
       dígito es el DV de los nueve anteriores**, se le quita el DV.

       Las tres condiciones juntas, y no menos. El tipo, porque en una cédula
       la coincidencia del DV es azar. El rango, porque la fuente etiqueta como
       «NIT» muchas cédulas de diez dígitos que empiezan por 1, y a una de cada
       once le cuadraría el DV por casualidad: se le quitaría un dígito y
       pasaría a ser otra persona.

       Queda un caso sin cubrir a sabiendas: el NIT de una persona natural cuya
       cédula empieza por 1. Ese se quedará con su DV y, si en otro contrato
       aparece sin él, contará como dos proveedores. **Es el fallo que se
       elige.** Separar de más subestima una concentración; unir de más la
       inventa, y una alerta inventada es exactamente lo que este proyecto no
       se puede permitir.
    """
    tipo_normalizado = normalizar_texto(tipo) or "SIN TIPO"
    crudo = normalizar_texto(documento)
    if crudo is None:
        raise DocumentoNoUtilizable("el contrato no trae documento de proveedor")

    numero = _NO_ALFANUMERICO.sub("", crudo)
    if not numero:
        raise DocumentoNoUtilizable(f"documento sin contenido utilizable: {crudo!r}")
    if not any(c.isdigit() for c in numero):
        raise DocumentoNoUtilizable(
            f"el documento {crudo!r} no tiene ni un dígito: es un centinela de "
            "la fuente, no una identidad"
        )
    if len(set(numero)) == 1:
        # UN SOLO CARÁCTER REPETIDO NO ES UN DOCUMENTO. `000000000`, `0`,
        # `11111111`: son la forma que toma «no lo sé» cuando el formulario
        # exige dígitos y la regla anterior —«que tenga al menos un dígito»—
        # los deja pasar.
        #
        # Lo encontró el Panel, no una prueba: en la ventana del 2026-09-05
        # el documento `000000000` había fundido TRES consorcios distintos en
        # un solo proveedor, con tres razones sociales. Tres, no trescientos,
        # porque la ventana es de ocho días; con el histórico nacional sería
        # exactamente el `NODEFINIDO` que este módulo existe para evitar,
        # entrando por la puerta de al lado.
        #
        # Ningún NIT ni cédula real de Colombia es un dígito repetido, así que
        # el riesgo de separar a alguien de verdad es nulo, y el de fundir a
        # varios era real y ya estaba ocurriendo.
        raise DocumentoNoUtilizable(
            f"el documento {crudo!r} es un solo carácter repetido: es un "
            "centinela de la fuente, no una identidad"
        )

    if (
        es_nit(tipo_normalizado)
        and len(numero) == LARGO_NIT + 1
        and numero.isdigit()
        and numero.startswith(PRIMEROS_DIGITOS_NIT_JURIDICO)
    ):
        base, ultimo = numero[:LARGO_NIT], numero[LARGO_NIT]
        if digito_de_verificacion(base) == int(ultimo):
            numero = base

    return IdentidadProveedor(tipo=tipo_normalizado, numero=numero)


def es_grupo(contenido: Mapping[str, object]) -> bool:
    """Si la fuente marca el adjudicatario como Unión Temporal o Consorcio."""
    return normalizar_texto(contenido.get(CAMPO_ES_GRUPO)) == VALOR_ES_GRUPO


def identidad_del_contrato(
    contenido: Mapping[str, object],
) -> IdentidadProveedor:
    """La identidad del proveedor de un contrato, provisional si hace falta.

    Primero se intenta la identidad de verdad, por documento. Si el documento
    no sirve **y la fuente marca el adjudicatario como grupo**, el contrato
    recibe una identidad provisional propia, con el número del contrato.

    POR QUÉ ASÍ, Y NO DE OTRAS DOS FORMAS QUE PARECEN MEJORES.

    *Fundir todas las uniones sin documento en un solo proveedor* es el error
    que el módulo entero existe para no cometer: crearía el contratista más
    concentrado de Colombia, y sería falso.

    *Agruparlas por el nombre* —«UNION TEMPORAL ALIMENTAR 2024»— es tentador,
    porque el nombre es lo único que queda. Pero el nombre lo teclea cada
    entidad, no es único en el país, y dos uniones distintas con el mismo
    nombre se fundirían en una concentración inventada. La regla del proyecto
    no admite eso: **separar de más subestima una concentración; unir de más la
    inventa, y una alerta inventada es exactamente lo que este proyecto no se
    puede permitir.** El nombre igual queda registrado como variante, así que
    la historia que sí quiera juntarlas tendrá con qué, y con evidencia.

    Una identidad por contrato, en cambio, no puede equivocarse en ninguna de
    las dos direcciones: no funde nada, y no deja nada fuera del conteo.

    Levanta `DocumentoNoUtilizable` cuando el documento no sirve y **tampoco**
    es un grupo. Ese caso son, casi enteros, los 160 543 borradores y
    cancelados que nunca llegaron a tener proveedor. Darles identidad sería
    inventarles un contratista a papeles que no adjudicaron a nadie.
    """
    try:
        return canonizar_documento(
            contenido.get(CAMPO_DOCUMENTO),
            tipo=contenido.get(CAMPO_TIPO_DOCUMENTO),
        )
    except DocumentoNoUtilizable:
        if not es_grupo(contenido):
            raise
        numero = normalizar_texto(contenido.get(CAMPO_ID_CONTRATO))
        if numero is None:
            raise
        return IdentidadProveedor(tipo=TIPO_GRUPO_PROVISIONAL, numero=numero)


@dataclass
class Proveedor:
    """Un proveedor agrupado, con todas sus formas de escribir el nombre.

    Las variantes NO se descartan: el criterio de aceptación pide que queden
    registradas y consultables, y con razón. Un mismo documento que aparece con
    tres razones sociales distintas es en sí mismo una señal —puede ser un
    cambio de nombre legítimo, o puede ser otra cosa— y el Expediente de la
    épica 2 tendrá que mostrarlas.
    """

    identidad: IdentidadProveedor
    variantes: dict[str, int] = field(default_factory=dict)
    contratos: int = 0

    def registrar(self, nombre: object) -> None:
        self.contratos += 1
        limpio = normalizar_texto(nombre)
        if limpio is None:
            return
        self.variantes[limpio] = self.variantes.get(limpio, 0) + 1

    @property
    def nombre_principal(self) -> str | None:
        """La forma más frecuente. En empate, la primera en orden alfabético.

        Se desempata de forma determinista a propósito: si el nombre que se
        muestra cambiara entre dos corridas sobre los mismos datos, cualquier
        reporte dejaría de ser reproducible.
        """
        if not self.variantes:
            return None
        return min(self.variantes.items(), key=lambda par: (-par[1], par[0]))[0]

    @property
    def cuantas_variantes(self) -> int:
        return len(self.variantes)

    @property
    def provisional(self) -> bool:
        return self.identidad.provisional


@dataclass(frozen=True)
class ResumenProveedores:
    """Lo que dejó una agrupación. Todos los conteos son verificables."""

    contratos_leidos: int
    contratos_agrupados: int
    sin_documento_utilizable: int
    proveedores: int
    con_varias_variantes: int
    #: De los agrupados, los que solo tienen identidad provisional de grupo.
    #: Se cuentan aparte porque están vigilados a medias: se ven y se suman,
    #: pero no se les puede medir concentración.
    contratos_provisionales: int = 0
    proveedores_provisionales: int = 0

    def __post_init__(self) -> None:
        for nombre, valor in vars(self).items():
            if valor < 0:
                raise ValueError(f"{nombre} no puede ser negativo: {valor}")
        if self.contratos_agrupados + self.sin_documento_utilizable != self.contratos_leidos:
            raise ValueError(
                f"conteos incoherentes: {self.contratos_agrupados} agrupados + "
                f"{self.sin_documento_utilizable} sin documento != "
                f"{self.contratos_leidos} leídos"
            )
        if self.proveedores > self.contratos_agrupados:
            raise ValueError(
                f"{self.proveedores} proveedores para {self.contratos_agrupados} "
                "contratos: agrupar no puede crear proveedores"
            )
        if self.contratos_provisionales > self.contratos_agrupados:
            raise ValueError(
                f"{self.contratos_provisionales} provisionales no caben en "
                f"{self.contratos_agrupados} agrupados"
            )
        # Una identidad provisional se construye con el número del contrato,
        # así que no puede haber más identidades que contratos. Puede haber
        # menos: si la misma fila entra dos veces, las dos caen en la misma.
        if self.proveedores_provisionales > self.contratos_provisionales:
            raise ValueError(
                f"{self.proveedores_provisionales} identidades provisionales "
                f"para {self.contratos_provisionales} contratos: imposible, "
                "cada una lleva el número de su contrato"
            )
        if self.proveedores_provisionales > self.proveedores:
            raise ValueError(
                f"{self.proveedores_provisionales} provisionales no caben en "
                f"{self.proveedores} proveedores"
            )

    @property
    def proporcion_sin_documento(self) -> float | None:
        """Sobre el total leído. `None` si no se leyó nada — no cero."""
        if self.contratos_leidos == 0:
            return None
        return self.sin_documento_utilizable / self.contratos_leidos

    @property
    def contratos_con_identidad_real(self) -> int:
        """Los que sí se pueden vigilar por concentración de proveedor."""
        return self.contratos_agrupados - self.contratos_provisionales

    @property
    def proporcion_fuera_de_concentracion(self) -> float | None:
        """Qué parte del total NO puede vigilar «concentración por proveedor».

        Suma los que no tienen identidad y los que solo la tienen provisional,
        porque para esa Regla los dos son igual de invisibles. Es el número que
        hay que mirar antes de creerse un ranking de contratistas.
        """
        if self.contratos_leidos == 0:
            return None
        fuera = self.sin_documento_utilizable + self.contratos_provisionales
        return fuera / self.contratos_leidos


def agrupar(
    contenidos: Iterable[Mapping[str, object]],
) -> tuple[dict[str, Proveedor], ResumenProveedores]:
    """Agrupa contratos por identidad de proveedor.

    Devuelve el índice por clave y el resumen. Un contrato cuyo documento no
    sirve NO se descarta del mundo: no entra al índice, pero se cuenta, igual
    que los huérfanos de la 1.4. Esconderlo dejaría el porcentaje de cobertura
    sin forma de medirse.
    """
    proveedores: dict[str, Proveedor] = {}
    leidos = 0
    sin_documento = 0
    provisionales = 0

    for contenido in contenidos:
        leidos += 1
        try:
            identidad = identidad_del_contrato(contenido)
        except DocumentoNoUtilizable:
            sin_documento += 1
            continue
        if identidad.provisional:
            provisionales += 1
        proveedor = proveedores.get(identidad.clave)
        if proveedor is None:
            proveedor = Proveedor(identidad=identidad)
            proveedores[identidad.clave] = proveedor
        proveedor.registrar(contenido.get(CAMPO_NOMBRE))

    resumen = ResumenProveedores(
        contratos_leidos=leidos,
        contratos_agrupados=leidos - sin_documento,
        sin_documento_utilizable=sin_documento,
        proveedores=len(proveedores),
        con_varias_variantes=sum(
            1 for p in proveedores.values() if p.cuantas_variantes > 1
        ),
        contratos_provisionales=provisionales,
        proveedores_provisionales=sum(
            1 for p in proveedores.values() if p.provisional
        ),
    )
    return proveedores, resumen
