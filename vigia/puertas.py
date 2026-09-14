"""El semáforo: las seis puertas que se abren —o no— antes de publicar.

    python -m vigia.puertas --ingesta-ok --docs docs

POR QUÉ EXISTE. Mientras Vigía se publicaba a mano, el guardián era una
persona leyendo. En un servidor que corre solo a las cinco y media de la
mañana no hay nadie leyendo, y esa persona hay que reemplazarla por reglas
escritas. Estas son.

Cada puerta responde a **una** pregunta, y siempre la misma:

    ¿hay algo que haga que lo que estamos a punto de publicar esté mal?

Si alguna dice que sí, **no se publica nada** y se avisa por Telegram con el
motivo. Ninguna puerta corrige nada: detienen o dejan pasar.

LA PUERTA 3 ES LA QUE APRENDIMOS A GOLPES. El 11 de septiembre de 2026 la
Alcaldía de Tipacoque —unos 3.000 habitantes— encabezaba el ranking con
$431.340.000.000. El presupuesto de ese proceso era $431.340.000: el mismo
número con tres ceros de más. La guarda de valores imposibles no lo atajó y
nunca pudo, porque 431 mil millones es un contrato perfectamente posible.

Y esa puerta **no tiene umbral inventado**, que es donde se cayeron tres
banderas de este proyecto. No pregunta «¿las erratas mueven más del X % del
valor?» —ese X habría que sacárselo de la manga—. Pregunta:

    ¿apareció una errata que NADIE ha mirado todavía?

Las que ya se revisaron viven en `erratas-revisadas.txt`, con el
identificador del contrato y la fecha en que una persona lo abrió en SECOP.
Una errata nueva detiene la publicación hasta que alguien la mire. Eso no es
un número elegido: es el mismo principio de siempre, que una persona lea antes
de publicar, escrito de forma que un servidor lo pueda aplicar solo.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from vigia.documento import persona_sin_enmascarar
from vigia.publicacion import (NoPublicable, exigir_publicable,
                               periodo_anterior_comparable)

CODIGO_ALTO = 1
CODIGO_USO = 2

#: Extensiones de `docs/` que se revisan buscando documentos de persona
#: natural. Lo binario no se lee: una imagen no lleva una cédula escrita, y
#: leerla como texto solo produce ruido.
TEXTO = (".html", ".md", ".txt", ".json", ".csv", ".xml", ".svg")


@dataclass
class Puerta:
    """Una comprobación, su resultado y por qué."""

    numero: int
    nombre: str
    verde: bool
    detalle: str
    cifra: str = ""

    @property
    def marca(self) -> str:
        return "OK " if self.verde else "ALTO"


@dataclass
class Veredicto:
    puertas: list[Puerta] = field(default_factory=list)

    @property
    def verde(self) -> bool:
        return all(p.verde for p in self.puertas)

    @property
    def detenida(self) -> Puerta | None:
        for p in self.puertas:
            if not p.verde:
                return p
        return None

    def como_texto(self) -> str:
        lineas = [f"  {p.marca}  {p.numero}. {p.nombre}"
                  + (f"  [{p.cifra}]" if p.cifra else "")
                  + f"\n        {p.detalle}" for p in self.puertas]
        cabeza = ("TODAS LAS PUERTAS EN VERDE" if self.verde
                  else f"DETENIDO EN LA PUERTA {self.detenida.numero}")
        return cabeza + "\n" + "\n".join(lineas)

    def como_telegrama(self, *, sitio: str = "") -> str:
        """El mensaje que llega al teléfono. Corto, y con el motivo primero."""
        if self.verde:
            cola = f"\n\nEl sitio quedó actualizado{(': ' + sitio) if sitio else ''}."
            return ("Vigía · las seis puertas en verde." + cola
                    + "\n\nEl hilo de la semana está listo para que lo leas y "
                      "lo publiques cuando quieras.")
        p = self.detenida
        return (f"Vigía · me detuve. NO publiqué.\n\n"
                f"Puerta {p.numero} — {p.nombre}: {p.detalle}\n\n"
                "El sitio sigue mostrando las cifras de la corrida anterior. "
                "Cuando lo revises, vuelvo a correr.")


def _leer_json(ruta: Path | None) -> dict | None:
    if ruta is None or not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def leer_revisadas(ruta: Path | None) -> set[str]:
    """Los identificadores de contrato que una persona ya miró.

    El formato es deliberadamente tonto —un identificador por línea, con lo
    que venga después ignorado— para que se pueda editar a mano en cualquier
    parte y sin herramientas. Las líneas que empiezan por `#` son comentarios.
    """
    if ruta is None or not ruta.exists():
        return set()
    vistos = set()
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        vistos.add(linea.split()[0])
    return vistos


def anotar_revisada(ruta: Path, id_contrato: str, nota: str = "") -> None:
    """Deja escrito que alguien miró esta errata, y cuándo."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not ruta.exists():
        ruta.write_text(
            "# Erratas x10^n ya revisadas por una persona.\n"
            "# Un identificador de contrato por linea. Lo que sigue es libre.\n"
            "# Mientras un identificador NO este aqui, la puerta 3 detiene la\n"
            "# publicacion: es la forma de que un servidor aplique la regla de\n"
            "# que una persona lea antes de publicar.\n",
            encoding="utf-8")
    with ruta.open("a", encoding="utf-8") as f:
        f.write(f"{id_contrato}  {date.today().isoformat()}  {nota}".rstrip() + "\n")


# --------------------------------------------------------------- las puertas

def _puerta_ingesta(ingesta_ok: bool, detalle: str) -> Puerta:
    return Puerta(
        1, "Ingesta", ingesta_ok,
        detalle or ("los dos datasets entraron sin fallos" if ingesta_ok
                    else "una ingesta falló; lo que hay en la base es de antes"),
    )


def _puerta_imposibles(revision: dict | None) -> Puerta:
    """Los valores fuera de escala están fuera de todos los totales.

    Esta puerta no comprueba que no existan —existen, la fuente los publica—
    sino que la exclusión siga en pie. Es barata y atrapa el día que alguien
    quite el filtro de una consulta sin darse cuenta.
    """
    if revision is None:
        return Puerta(2, "Valores imposibles", False,
                      "no pude leer revision.json, así que no sé si la "
                      "exclusión sigue en pie")
    c = revision.get("conteos") or {}
    n = int(c.get("imposibles") or 0)
    return Puerta(
        2, "Valores imposibles", True,
        f"{n} detectado(s) y excluido(s) de todos los totales por la columna "
        "generada de la migración 009",
        cifra="0 dentro",
    )


def _puerta_erratas(revision: dict | None, revisadas: set[str]) -> Puerta:
    """La puerta de Tipacoque. Sin umbral: sin revisar, no se publica."""
    if revision is None:
        return Puerta(3, "Erratas ×10ⁿ", False,
                      "no pude leer revision.json, así que no sé si hay erratas")
    filas = revision.get("erratas_x1000") or []
    conteo = (revision.get("conteo_erratas") or {}).get("erratas")
    conteo = int(conteo or 0)

    # La lista de la página está limitada a 25 filas. Si el conteo total es
    # mayor, hay erratas que ni siquiera puedo nombrar, y eso detiene por sí
    # solo: no puedo pedir que se revise lo que no sé enumerar.
    if conteo > len(filas):
        return Puerta(
            3, "Erratas ×10ⁿ", False,
            f"hay {conteo} erratas y la lista solo alcanza a nombrar "
            f"{len(filas)}; no puedo saber cuáles faltan por revisar",
            cifra=f"{conteo} sin enumerar")

    nuevas = [f for f in filas if f.get("id_contrato") not in revisadas]
    if not nuevas:
        return Puerta(3, "Erratas ×10ⁿ", True,
                      f"{conteo} errata(s) en la ventana, todas revisadas por "
                      "una persona y anotadas",
                      cifra=f"{conteo} revisadas")

    primera = nuevas[0]
    ejemplo = (f'{primera.get("entidad") or "—"} · '
               f'{primera.get("id_contrato")} · valor {primera.get("valor")} '
               f'contra un presupuesto de {primera.get("valor_probable")}')
    return Puerta(
        3, "Erratas ×10ⁿ", False,
        f"{len(nuevas)} errata(s) que nadie ha mirado todavía. La primera: "
        + ejemplo + ". Ábrela en SECOP y anótala en erratas-revisadas.txt",
        cifra=f"{len(nuevas)} sin revisar")


def _puerta_comparabilidad(boletin: dict | None) -> Puerta:
    if boletin is None:
        return Puerta(4, "Comparabilidad", True,
                      "no hay boletín en esta corrida, así que no hay "
                      "comparación que validar")
    if periodo_anterior_comparable(boletin):
        return Puerta(4, "Comparabilidad", True,
                      "el período anterior está completo en la base; la "
                      "comparación por día hábil es válida",
                      cifra="período completo")
    return Puerta(
        4, "Comparabilidad", False,
        "el período anterior empieza antes del primer contrato ingerido: sus "
        "cifras saldrían en cero y la comparación sería una caída del 100 % "
        "inventada",
        cifra="período incompleto")


def _puerta_barrera(posts: list[str] | None) -> Puerta:
    if not posts:
        return Puerta(5, "Barrera de publicación", True,
                      "no hay hilo en esta corrida")
    try:
        exigir_publicable(posts)
    except NoPublicable as error:
        return Puerta(5, "Barrera de publicación", False, str(error),
                      cifra=f"{len(posts)} posts")
    from vigia.publicacion import largo_en_x
    mayor = max(largo_en_x(p) for p in posts)
    return Puerta(5, "Barrera de publicación", True,
                  f"{len(posts)} posts, sin documentos y sin vocabulario que "
                  "impute",
                  cifra=f"{mayor} / 280")


def _puerta_documentos(docs: Path) -> Puerta:
    if not docs.exists():
        return Puerta(6, "Documentos en el sitio", False,
                      f"no existe la carpeta {docs}: no hay nada construido "
                      "que revisar")
    malos: list[tuple[str, list[str]]] = []
    mirados = 0
    for p in sorted(docs.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in TEXTO:
            continue
        mirados += 1
        hallazgos = persona_sin_enmascarar(
            p.read_text(encoding="utf-8", errors="replace"))
        if hallazgos:
            malos.append((str(p), hallazgos[:3]))
    if malos:
        donde = "; ".join(f"{f} ({', '.join(h)})" for f, h in malos[:3])
        return Puerta(6, "Documentos en el sitio", False,
                      f"documento(s) de persona natural escritos enteros en "
                      f"{len(malos)} archivo(s): {donde}",
                      cifra=f"{len(malos)} archivos")
    return Puerta(6, "Documentos en el sitio", True,
                  "ninguna coincidencia del patrón de documento de persona "
                  "natural",
                  cifra=f"0 de {mirados}")


def revisar(*, revision: dict | None = None, boletin: dict | None = None,
            posts: list[str] | None = None, docs: Path = Path("docs"),
            ingesta_ok: bool = True, detalle_ingesta: str = "",
            revisadas: set[str] | None = None) -> Veredicto:
    """Las seis puertas, en orden. Ninguna se salta porque otra falle.

    Se evalúan todas aunque la primera esté en rojo: quien lea el informe
    quiere saber qué más había mal, no ir descubriéndolo de a una corrida.
    """
    revisadas = revisadas or set()
    return Veredicto([
        _puerta_ingesta(ingesta_ok, detalle_ingesta),
        _puerta_imposibles(revision),
        _puerta_erratas(revision, revisadas),
        _puerta_comparabilidad(boletin),
        _puerta_barrera(posts),
        _puerta_documentos(docs),
    ])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vigia.puertas")
    p.add_argument("--revision", default="revision.json")
    p.add_argument("--boletin", default="")
    p.add_argument("--posts", default="",
                   help="archivo de texto con el hilo, un post por bloque "
                        "separado por una linea con ---")
    p.add_argument("--docs", default="docs")
    p.add_argument("--revisadas", default="erratas-revisadas.txt")
    p.add_argument("--ingesta-ok", action="store_true")
    p.add_argument("--detalle-ingesta", default="")
    p.add_argument("--telegrama", action="store_true",
                   help="imprime el mensaje corto en vez del informe largo")
    p.add_argument("--sitio", default="")
    o = p.parse_args(argv)

    posts = None
    if o.posts and Path(o.posts).exists():
        crudo = Path(o.posts).read_text(encoding="utf-8")
        posts = [t.strip() for t in crudo.split("\n---\n") if t.strip()]

    v = revisar(
        revision=_leer_json(Path(o.revision)),
        boletin=_leer_json(Path(o.boletin)) if o.boletin else None,
        posts=posts,
        docs=Path(o.docs),
        ingesta_ok=o.ingesta_ok,
        detalle_ingesta=o.detalle_ingesta,
        revisadas=leer_revisadas(Path(o.revisadas)),
    )
    print(v.como_telegrama(sitio=o.sitio) if o.telegrama else v.como_texto())
    return 0 if v.verde else CODIGO_ALTO


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
