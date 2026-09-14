"""Lo que se puede publicar, y lo que no sale de este computador.

POR QUÉ ESTE MÓDULO EXISTE. Hasta hoy todo lo que producía Vigía se quedaba en
el escritorio de una persona. Un boletín no: **se publica en internet y no se
puede despublicar.** Un borrado en X no borra las capturas, ni las citas, ni la
memoria del que lo leyó.

Eso cambia el cálculo de los errores. Un número mal en el Panel se corrige en
la siguiente corrida y no le pasa nada a nadie. El mismo número mal en un
boletín ya circuló, y si al lado iba el nombre de una persona, esa persona
tiene un problema que nosotros le creamos.

LAS TRES BARRERAS, en orden de gravedad:

1. **Ningún documento de identidad.** Una cédula publicada en internet es un
   dato personal difundido sin autorización — Ley 1581 de 2012. No hay versión
   buena de esto: no depende del contexto ni de la intención.

   Y no es hipotético: la lista de revisión de este mismo proyecto muestra hoy
   cédulas de personas naturales contratistas. **Ahí está bien** —es una
   herramienta de trabajo en un escritorio, y el dato es público en SECOP—;
   en un boletín no.

2. **Ningún vocabulario de imputación.** Reutiliza la prueba de la historia
   2.6, que ya recorre el código. En Colombia la injuria y la calumnia son
   delito, no solo un pleito civil: publicar que alguien obró mal sin poder
   probarlo tiene consecuencias penales para quien lo publica.

3. **La nota de qué es esto**, en el propio texto y no en un enlace. Un hilo se
   lee suelto: el tercer post circula sin el primero.

LO QUE **NO** PROHÍBE, Y POR QUÉ. No prohíbe nombrar entidades estatales: el
INVIAS y una alcaldía son órganos públicos, su contratación es pública por
mandato legal, y una entidad no tiene honra que herir en el sentido en que la
tiene una persona. Lo que hace daño no es nombrar: es afirmar.

ESTE MÓDULO NO SUSTITUYE UN CONCEPTO JURÍDICO. La épica 5 lo tiene como
dependencia bloqueante desde el principio, y sigue estándolo. Esto es el piso
mínimo mecánico, no el permiso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


from vigia.reglas.lenguaje import revisar as _palabras_prohibidas

#: Límite de un post en X. Un enlace cuenta como 23 caracteres pase lo que
#: pase, así que el conteo real no es `len()`.
LIMITE_POST = 280
LARGO_DE_UN_ENLACE = 23

#: La nota que todo boletín lleva escrita, no enlazada.
NOTA = (
    "Cifras de SECOP, fuente oficial. Son estadística descriptiva: no "
    "señalan a nadie ni afirman que exista una conducta contraria a la ley."
)

#: Secuencias largas de dígitos: cédulas, NIT, teléfonos. Se permiten los
#: números con separador de miles (1.234.567) porque son cifras de dinero, y
#: los años. Lo que se ataja es el dígito corrido de 6 a 12 posiciones, que es
#: la forma de un documento de identidad colombiano.
_DOCUMENTO = re.compile(r"(?<!\d)\d{6,12}(?!\d)")


_ENLACE = re.compile(r"https?://\S+")


class NoPublicable(Exception):
    """El texto no sale de aquí. El mensaje dice exactamente por qué."""


@dataclass(frozen=True)
class Reparo:
    post: int
    motivo: str
    fragmento: str


def largo_en_x(texto: str) -> int:
    """Los caracteres que X le cuenta a un post.

    Un enlace ocupa 23 pase lo que pase, corto o largo. Contar con `len()`
    haría que un post con un enlace largo se viera dentro del límite aquí y
    rebotara al publicarlo, que es justo cuando ya no hay tiempo de arreglarlo.
    """
    sin_enlaces = _ENLACE.sub("", texto)
    cuantos = len(_ENLACE.findall(texto))
    return len(sin_enlaces) + cuantos * LARGO_DE_UN_ENLACE


def revisar(posts: list[str]) -> list[Reparo]:
    """Todos los reparos de un hilo. Lista vacía = se puede publicar."""
    reparos: list[Reparo] = []
    for i, post in enumerate(posts, start=1):
        for hallazgo in _DOCUMENTO.findall(post):
            reparos.append(Reparo(i, "parece un documento de identidad", hallazgo))
        # Se usa el buscador de la historia 2.6 y no uno propio: aquel quita
        # las tildes antes de comparar. Una copia sin esa línea dejaba pasar
        # «corrupción» —la forma en que de verdad se escribe la palabra— y eso
        # es todo lo que hace falta para que la barrera no sirva.
        for hallazgo in _palabras_prohibidas(post):
            reparos.append(Reparo(i, "vocabulario de imputacion", hallazgo))
        largo = largo_en_x(post)
        if largo > LIMITE_POST:
            reparos.append(
                Reparo(i, f"se pasa del limite ({largo} de {LIMITE_POST})",
                       post[-40:]))
        if not post.strip():
            reparos.append(Reparo(i, "post vacio", ""))

    texto = "\n".join(posts)
    if NOTA[:40] not in texto:
        reparos.append(Reparo(0, "al hilo le falta la nota de que es esto", ""))
    return reparos


def exigir_publicable(posts: list[str]) -> None:
    """Levanta si hay un solo reparo. No devuelve nada: o pasa, o no sale.

    Se levanta en vez de devolver un booleano a propósito. Un `if` se puede
    olvidar; una excepción, no. Es la misma decisión que la historia 2.3 tomó
    con el Expediente: **es preferible un boletín que no salió a uno que no se
    puede sostener.**
    """
    reparos = revisar(posts)
    if not reparos:
        return
    detalle = "\n".join(
        f"  post {r.post}: {r.motivo}" + (f" -> {r.fragmento!r}" if r.fragmento else "")
        for r in reparos
    )
    raise NoPublicable(
        f"{len(reparos)} reparo(s); este hilo NO se publica:\n{detalle}"
    )


def periodo_anterior_comparable(datos: dict) -> bool:
    """Si el período anterior está DENTRO de lo que hemos traído.

    **Es la distinción que más daño hace si se pierde.** Si el período
    anterior empieza antes del primer contrato que tenemos, sus cifras salen
    en cero — no porque el Estado no contratara, sino porque no lo hemos
    ingerido. Comparar contra eso produce una caída del 100 % que es
    literalmente mentira, y publicada con la cara de Vigía.

    Es la misma distinción que sostiene el modo calibración de la historia
    2.5: «se miró y no había» no es «no se miró».

    Cuando esto devuelve `False`, quien dibuja **se calla la comparación** en
    vez de inventarla. Callarse es un resultado; inventar no.
    """
    from datetime import date

    ct = datos.get("cobertura_temporal") or {}
    primero = ct.get("primer_contrato")
    if not primero:
        return False
    ant = (datos.get("anterior") or {}).get("desde")
    if not ant:
        return False
    return date.fromisoformat(str(ant)[:10]) >= date.fromisoformat(str(primero)[:10])
