"""Cómo se escribe el documento de un contratista en una página.

POR QUÉ EXISTE ESTE MÓDULO, Y ES UNA HISTORIA CORTA. El 2026-09-11 le expliqué
al usuario que la lista de revisión era segura porque nunca se publica: está en
`.gitignore`, no la lee el generador del sitio, y el publicador aborta si
encuentra un documento. Todo eso es cierto y está comprobado.

**Y entonces él copió veintitrés cédulas de esa página y las pegó en un chat.**

No hizo nada raro: quiso enseñarme lo que veía. Pero con eso quedó claro que el
modelo de amenaza estaba mal planteado. El archivo no se filtra por publicarse
—eso está cerrado— **se filtra por ser legible**: se pega en un correo, se
manda por WhatsApp, se le hace una captura, se comparte la carpeta.

Contra eso no sirve ninguna barrera de publicación. Solo sirve que el número no
esté escrito en la página.

QUÉ SE ENMASCARA Y QUÉ NO. Se enmascara el documento de una **persona
natural** —cédula, extranjería, pasaporte, NUIP, PEP— y no el **NIT**, que
identifica a una empresa. No es una distinción de comodidad: el NIT es un
identificador comercial que la empresa usa en su factura y en su fachada; la
cédula es el número con el que se abre la vida entera de una persona.

QUÉ NO SE PIERDE. El trabajo que la página permite hacer no necesita el
número: para ir a mirar un contrato en SECOP se usa el `id_contrato`, que sigue
completo. Y para reconocer a la misma persona en dos filas basta con que las
dos se vean igual, que es lo que hace el enmascarado. El número completo sigue
en la base, a una consulta de distancia, para quien lo necesite de verdad.
"""

from __future__ import annotations

#: Tipos de documento que identifican a una PERSONA NATURAL. Se comparan sin
#: tildes y en mayúsculas porque la fuente escribe «CEDULA», «Cédula» y
#: «CÉDULA DE CIUDADANÍA» en el mismo dataset.
DE_PERSONA = (
    "CEDULA DE CIUDADANIA",
    "CEDULA DE EXTRANJERIA",
    "TARJETA DE IDENTIDAD",
    "PASAPORTE",
    "NUIP",
    "PERMISO ESPECIAL DE PERMANENCIA",
    "PERMISO POR PROTECCION TEMPORAL",
    "REGISTRO CIVIL",
)

#: Cuántos dígitos finales se dejan ver. Tres bastan para distinguir dos filas
#: de un vistazo y no alcanzan para reconstruir el número: con tres dígitos
#: quedan un millón de cédulas posibles en Colombia.
VISIBLES = 3

RELLENO = "•"


def _sin_tildes(texto: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def es_de_persona(tipo) -> bool:
    """Si el tipo de documento es el de una persona natural."""
    if not tipo:
        return False
    t = _sin_tildes(str(tipo)).upper().strip()
    return any(t.startswith(p) or p in t for p in DE_PERSONA)


def escribir(tipo, numero, *, completo: bool = False) -> str:
    """El documento tal como debe verse en una página.

    `completo=True` lo deja entero. Existe para el caso en que alguien de
    verdad necesite el número —una denuncia formal, un cruce con otra fuente—
    y tenga que ser una decisión consciente: se pide con una bandera en la
    línea de comandos, no es lo que sale por defecto.
    """
    tipo_txt = "" if tipo is None else str(tipo).strip()
    num = "" if numero is None else str(numero).strip()
    if not num:
        return tipo_txt or "—"
    if completo or not es_de_persona(tipo_txt):
        return f"{tipo_txt} {num}".strip()

    # Un número tan corto que enmascararlo no esconde nada se esconde entero:
    # dejar «•12» sería peor que no hacer nada, porque parece protegido.
    if len(num) <= VISIBLES + 1:
        visible = RELLENO * len(num)
    else:
        visible = RELLENO * (len(num) - VISIBLES) + num[-VISIBLES:]
    return f"{tipo_txt} {visible}".strip()


#: Un documento de PERSONA NATURAL escrito entero: la etiqueta del tipo y, a
#: poca distancia, una cadena larga de dígitos.
#:
#: Este patrón es el que vigila lo que se publica cuando la página SÍ puede
#: llevar NIT. La comprobación general —«ninguna cadena de 6 a 12 dígitos»—
#: sirve para el boletín, que no lleva ningún identificador; en el Panel y en
#: la lista de revisión ahogaría todos los NIT, que son justo lo que hay que
#: publicar.
PATRON_PERSONA = (
    r"(?:C[EÉ]DULA|PASAPORTE|NUIP|TARJETA\s+DE\s+IDENTIDAD|REGISTRO\s+CIVIL|"
    r"PERMISO\s+(?:ESPECIAL|POR))[^0-9]{0,40}(\d{5,})"
)


def persona_sin_enmascarar(texto: str) -> list[str]:
    """Los documentos de persona natural que quedaron escritos enteros.

    Lista vacía = ninguno se escapó. Es la comprobación que se le hace a una
    página antes de publicarla cuando esa página lleva NIT: el NIT identifica
    a una empresa y va completo, la cédula no.
    """
    import re

    return re.findall(PATRON_PERSONA, _sin_tildes(texto).upper())
