"""Vocabulario prohibido (historia 2.6).

POR QUÉ EXISTE. Vigía produce **indicadores estadísticos**, no imputaciones.
Un contrato con una señal no es un contrato irregular: es un contrato que vale
la pena mirar. La diferencia no es de cortesía —es lo que separa a este
proyecto de una máquina de difamar, y lo que hace que un funcionario señalado
por error tenga con qué defenderse.

Esa distinción se erosiona sola. No por mala fe: por prisa, por un titular más
llamativo, por un `print` escrito a las once de la noche. Por eso la barrera
es una prueba que falla, no una norma en un documento que nadie relee.

QUÉ SE REVISA. El texto que ve una persona: lo que imprimen los comandos, lo
que dice el Panel, los nombres y descripciones de las Reglas, los mensajes de
las Alertas. No se revisan los comentarios del código ni este propio módulo:
ahí las palabras aparecen para explicar por qué están prohibidas.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Las cuatro que la historia nombra, más las formas de la misma raíz.
#:
#: La lista es corta a propósito. No pretende cubrir todas las maneras de
#: acusar a alguien —eso es imposible— sino atajar las cuatro que aparecen
#: solas cuando uno escribe rápido sobre contratación pública.
PROHIBIDAS = (
    "irregular", "irregulares", "irregularidad", "irregularidades",  # vocabulario-permitido
    "corrupto", "corrupta", "corruptos", "corruptas", "corrupcion",  # vocabulario-permitido
    "fraude", "fraudes", "fraudulento", "fraudulenta",  # vocabulario-permitido
    "ilegal", "ilegales", "ilegalidad",  # vocabulario-permitido
    "delito", "delitos", "delictivo",  # vocabulario-permitido
    "culpable", "culpables",  # vocabulario-permitido
)

#: La nota que acompaña a toda exportación de Alertas. No es un descargo
#: legal escondido en letra pequeña: es la frase que dice qué es esto.
NOTA_DE_EXPORTACION = (
    "Los indicadores de este documento son estadísticos. Señalan contratos "
    "que vale la pena revisar y NO constituyen imputación, denuncia ni "
    "afirmación de que exista una conducta contraria a la ley."
)

_PATRON = re.compile(
    r"\b(" + "|".join(sorted(PROHIBIDAS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

#: Marca de una línea que habla DE las palabras prohibidas en vez de usarlas.
#: Sin esto, este módulo y sus pruebas se acusarían a sí mismos.
EXENCION = "vocabulario-permitido"


def _sin_tildes(texto: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def revisar(texto: str) -> list[str]:
    """Las palabras prohibidas que aparecen en un texto, en orden."""
    return [m.group(0) for m in _PATRON.finditer(_sin_tildes(texto))]


def limpio(texto: str) -> bool:
    return not revisar(texto)


def _cadenas_de_cara_al_usuario(fuente: str) -> list[tuple[int, str]]:
    """Las cadenas de un módulo que llegan a los ojos de una persona.

    Se recorre el ÁRBOL DE SINTAXIS, no las líneas. La diferencia importa:
    un docstring y un comentario explican por qué estas palabras están
    prohibidas —y para explicarlo hay que nombrarlas—, mientras que una cadena
    que se imprime o se escribe en la página es texto que alguien va a leer
    como una afirmación sobre un contrato real.

    Buscar por líneas obligaría a escribir la documentación con rodeos, que es
    justo lo contrario de lo que hace falta: la razón tiene que estar dicha con
    todas sus letras al lado de la regla.
    """
    import ast

    arbol = ast.parse(fuente)
    docstrings = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            cuerpo = getattr(nodo, "body", [])
            if (cuerpo and isinstance(cuerpo[0], ast.Expr)
                    and isinstance(cuerpo[0].value, ast.Constant)
                    and isinstance(cuerpo[0].value.value, str)):
                docstrings.add(id(cuerpo[0].value))

    cadenas = []
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                and id(nodo) not in docstrings):
            cadenas.append((nodo.lineno, nodo.value))
    return cadenas


def revisar_archivo(ruta: Path) -> list[tuple[int, str, str]]:
    """Hallazgos en un archivo: (línea, palabra, texto de la cadena)."""
    fuente = ruta.read_text(encoding="utf-8")
    lineas = fuente.splitlines()
    hallazgos = []
    for numero, cadena in _cadenas_de_cara_al_usuario(fuente):
        linea = lineas[numero - 1] if numero <= len(lineas) else ""
        if EXENCION in linea:
            continue
        for palabra in revisar(cadena):
            hallazgos.append((numero, palabra, cadena.strip()[:90]))
    return hallazgos
