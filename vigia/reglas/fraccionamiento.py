"""Bandera de fraccionamiento: varias mínimas cuantías que juntas pasan el tope.

QUÉ ES. Partir una compra en varios contratos pequeños para no pasar del tope
que obligaría a un proceso competitivo. Si una entidad necesita cien millones
en papelería y hace diez contratos de diez millones al mismo proveedor en el
mismo mes, cada uno cabe en mínima cuantía y ninguno tuvo que competir.

POR QUÉ ESTA Y NO OTRA. Las tres banderas anteriores murieron por lo mismo: el
umbral había que inventarlo. Ésta tiene un tope que **existe en el mundo** —el
de la mínima cuantía, que la ley fija según el presupuesto de cada entidad— y
que además no hace falta que nosotros lo sepamos:

    El tope de cada entidad se lee en su propia conducta: es la mínima cuantía
    más cara que esa entidad firma.

Sale de los datos y se recalcula solo cada año.

**UNA CORRECCIÓN AL PÁRRAFO ANTERIOR, QUE ESCRIBÍ MAL LA PRIMERA VEZ.** Decía
que el tope «es distinto para cada entidad, como lo es de verdad». La primera
calibración lo desmintió: en la muestra, catorce de veinticinco entidades
tenían un techo de **~$49,02 millones**, el mismo hasta los miles. No es que
cada entidad tenga su propio tope — es que todos los municipios pequeños caen
en el mismo escalón de la ley, porque sus presupuestos caen en el mismo rango.

El método sigue en pie (el techo leído coincide con el tope legal, que es
justo lo que se quería), pero la justificación era falsa, y de esa falsedad
salió el sesgo que hubo que corregir abajo.

LO QUE SE MIDIÓ ANTES DE ESCRIBIR UNA LÍNEA (base real de Guillermo,
2026-09-19, 262.471 contratos, de los cuales **9.423 mínimas cuantías
medibles** en 1.429 entidades por $399.049 millones):

**1. ES LA PRIMERA QUE SOBREVIVE A LA PRUEBA DEL FONDO.**

| Contratos en el grupo | Grupos | % de las mínimas |
|---|---|---|
| **1 solo** | **8.020** | **85,1 %** |
| 2 a 3 | 581 | 13,2 % |
| 4 a 5 | 27 | 1,2 % |
| 6 a 10 | 6 | 0,4 % |

Contratar dos veces al mismo proveedor en el mismo mes **no es lo normal**: le
pasa al 14,9 % de las mínimas cuantías. Compárese con las que se descartaron
—oferente único describía al 54,5 % del país y adjudicar ~100 % del
presupuesto al 62,4 %—: ésas eran el fondo, y ésta no.

**2. EL TOPE SEPARA DE VERDAD.** De los 614 grupos con dos o más contratos,
281 (45,8 %) suman más que el techo de su propia entidad: 187 entidades, 683
contratos, $29.929 millones.

**3. Y HAY DÓNDE CORTAR, sin inventar el corte.** Por cuánto se pasan:

| | Grupos |
|---|---|
| hasta 1,2 veces | 73 |
| 1,2 a 2 veces | 167 |
| más de 2 veces | 41 |

Con un corte único de ×2 quedaban 41 grupos — pero ese corte resultó estar
sesgado contra los municipios pequeños, y hubo que cambiarlo por uno por
tramo (ver `TRAMOS_POR_DEFECTO`). **Con el corte por tramo quedan 27 grupos
en tres meses**, unos nueve al mes. Eso lo revisa una persona. Los 5.415 de
oferente único no, y por eso aquella no llegó nunca a la cola.

**4. LOS QUE MÁS SE PASAN TIENEN CARA.** Alcaldía de Vijes: 6 contratos al
mismo proveedor en julio, $290,9 millones contra un techo de $73,5 millones
—4,0 veces—. Agencia Logística de las Fuerzas Militares: 3 contratos, 3,0
veces. Buenaventura: 3 contratos, 2,2 veces.

LO QUE ESTA REGLA NO DICE, Y VA ESCRITO ANTES QUE LO QUE SÍ DICE:

- **Ningún contrato del grupo es ilegal por estar aquí.** Cada uno cabía en el
  tope. Lo que pasa del tope es la SUMA, que es exactamente lo que significa
  fraccionar — y también lo que puede ser una casualidad administrativa
  perfectamente honesta.
- **Mismo proveedor + misma entidad + mismo mes no es «el mismo objeto».**
  Papelería y aseo al mismo proveedor son dos compras distintas, y la fuente
  no trae el objeto en una forma que se pueda comparar. La Regla mide una
  FORMA en los datos, no una intención.
- Compras repetidas, entregas por tramos y urgencias producen esta misma forma.

EL UMBRAL NO SE FIJA AQUÍ. Se fija calibrando, y por eso la Regla nace en
`borrador` y no puede activarse sin haber corrido sobre un recorte. Lo que este
módulo aporta es que el número de partida está medido y no adivinado.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence

from vigia.reglas.modelo import Alerta, Regla, VersionDeRegla, emitir

CODIGO = "fraccionamiento"

#: Cuántos contratos tiene que haber en el grupo. Dos ya es un grupo.
CONTRATOS_MINIMOS_POR_DEFECTO = 2

#: Cuántas veces el techo tiene que pasar la suma. **Ya no se usa como corte
#: único** —ver `TRAMOS_POR_DEFECTO`— pero se conserva como respaldo para un
#: techo que no caiga en ningún tramo.
VECES_EL_TECHO_POR_DEFECTO = Decimal("2")

#: EL CORTE ES DISTINTO SEGÚN EL TAMAÑO DEL TECHO, Y ESTA ES LA CORRECCIÓN
#: MÁS IMPORTANTE QUE TIENE ESTA REGLA.
#:
#: La primera calibración (2026-09-19, 590 grupos) encendió 41 veces con un
#: corte único de ×2. Al partir el resultado por tamaño del techo apareció
#: esto:
#:
#:     techo hasta $50 M ......  35 de 276 ... 12,7 %
#:     techo $50 a $120 M .....   5 de 130 .... 3,8 %
#:     techo más de $120 M ....   1 de 184 .... 0,5 %
#:
#: **Una entidad con techo pequeño tenía veinticinco veces más probabilidad de
#: encender que una con techo grande.** Y eso no es un hallazgo sobre conducta:
#: es aritmética. Con un tope de $49 millones, tres contratos de $33 millones
#: ya pasan del doble; con un tope de $250 millones harían falta tres de $167
#: millones, que ya casi no caben en mínima cuantía.
#:
#: Como la ley fija el tope según el presupuesto de la entidad, techo pequeño
#: es **municipio pequeño**. La bandera habría publicado una lista que se lee
#: como «los municipios pobres son los que fraccionan» cuando buena parte de
#: lo que medía era «los municipios pobres tienen topes pequeños». Es el mismo
#: error que mató a las otras tres banderas, en otra forma: describir un
#: estrato por una razón aritmética y no por una de conducta.
#:
#: El arreglo: el corte de cada tramo es el percentil 95 de su propio tramo,
#: así que cada estrato aporta la misma proporción y lo que queda es ser raro
#: **entre los pares**, no ser pobre. Con esto la tasa se aplana en 4,7 % /
#: 4,6 % / 4,9 %.
#:
#: Los números salen de los datos y no de la ley, igual que el techo. Una
#: calibración nueva los vuelve a calcular y crea una versión nueva.
TRAMOS_POR_DEFECTO = (
    {"hasta": "50000000", "veces": "2.91"},
    {"hasta": "120000000", "veces": "1.95"},
    {"hasta": None, "veces": "1.42"},
)

#: Cuántas mínimas cuantías necesita la entidad para que su techo signifique
#: algo. Con dos contratos, el «techo» es el único que hay: es la misma trampa
#: aritmética que hundió la concentración por proveedor.
MINIMAS_DE_LA_ENTIDAD_POR_DEFECTO = 5

#: Cuándo el techo de una entidad deja de ser creíble. Si su contrato más caro
#: es veinte veces su propio percentil 95, ese contrato es un forastero dentro
#: de su propia conducta: la forma de un dato mal puesto, no la de una compra
#: grande. En la medición del 2026-09-19 el techo mayor del país salió en
#: $44.118.060.000, y una mínima cuantía de cuarenta y cuatro mil millones no
#: existe.
#:
#: NO SE USA NINGÚN NÚMERO DE LA LEY, a propósito: cada entidad se compara
#: consigo misma, igual que el techo.
TECHO_SOBRE_P95_MAXIMO_POR_DEFECTO = Decimal("20")


class NoSePuedeMirar(RuntimeError):
    """La entidad no se puede evaluar, y eso NO es «no encontró nada».

    La diferencia es el corazón del asunto. Una entidad con un techo imposible
    —una errata, una modalidad mal puesta— tiene un tope inalcanzable, así que
    ningún grupo suyo lo pasará nunca. Si eso se reporta como «limpia», la
    Regla está afirmando algo que no miró.

    Quien llame cuenta estas entidades y las declara: son la cobertura de la
    bandera, y una cobertura que no se declara no es cobertura.
    """


def umbrales_iniciales() -> dict[str, Any]:
    """Los umbrales con los que nace la Regla, todos medidos o declarados."""
    return {
        "contratos_minimos": CONTRATOS_MINIMOS_POR_DEFECTO,
        "veces_el_techo": str(VECES_EL_TECHO_POR_DEFECTO),
        "tramos_de_techo": [dict(t) for t in TRAMOS_POR_DEFECTO],
        "minimas_de_la_entidad": MINIMAS_DE_LA_ENTIDAD_POR_DEFECTO,
        "techo_sobre_p95_maximo": str(TECHO_SOBRE_P95_MAXIMO_POR_DEFECTO),
        "ventana": "mes calendario",
    }


def crear(momento: datetime) -> Regla:
    """La Regla recién nacida: en borrador, con su primera versión."""
    regla = Regla(
        codigo=CODIGO,
        nombre="Mínimas cuantías que juntas pasan el tope",
        descripcion=(
            "Varios contratos de mínima cuantía de la misma entidad al mismo "
            "proveedor dentro de un mes, cuya suma supera la mínima cuantía "
            "más cara que esa entidad firma. Es un indicador estadístico sobre "
            "la forma de los datos: cada contrato cabía en el tope, y la "
            "repetición puede tener explicaciones normales. Por sí solo no "
            "dice nada sobre la conducta de nadie."
        ),
    )
    regla.nueva_version(
        umbrales_iniciales(),
        momento=momento,
        nota=(
            "Semilla medida sobre 9.423 mínimas cuantías: el 85,1 % es un "
            "contrato solo, así que agruparse no es el fondo. De los 614 "
            "grupos de dos o más, 281 pasan el techo de su entidad y 41 lo "
            "pasan del doble."
        ),
    )
    return regla


def _decimal(valor: object) -> Decimal | None:
    """Un número de la base. Puede llegar como texto, como float o vacío."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return Decimal(str(valor))
    except (TypeError, ValueError, ArithmeticError):
        return None


def techo_creible(grupo: Mapping[str, Any], umbrales: Mapping[str, Any]) -> bool:
    """Si el techo de esta entidad se puede usar para medir algo.

    Un techo que es muchas veces el propio percentil 95 de la entidad no es un
    techo: es un contrato mal puesto que se coló en la modalidad. Devolver
    `False` aquí es lo que permite CONTAR las entidades que no se pueden mirar
    en vez de reportarlas como limpias.
    """
    techo = _decimal(grupo.get("techo"))
    p95 = _decimal(grupo.get("p95_entidad"))
    if techo is None or techo <= 0:
        return False
    if p95 is None or p95 <= 0:
        # Sin percentil no se puede juzgar el techo. Se prefiere no mirar a
        # mirar mal: el resultado es «no se pudo», no «está limpia».
        return False
    limite = _decimal(umbrales.get("techo_sobre_p95_maximo")) or \
        TECHO_SOBRE_P95_MAXIMO_POR_DEFECTO
    return techo / p95 < limite


def corte_para(grupo: Mapping[str, Any], umbrales: Mapping[str, Any]) -> Decimal:
    """El corte que le toca a esta entidad según el tamaño de su techo.

    Sin esto, la bandera señalaría a los municipios pequeños por tener topes
    pequeños. Con esto, señala a quien es raro **entre sus pares**.
    """
    tramos = umbrales.get("tramos_de_techo") or []
    techo = _decimal(grupo.get("techo")) or Decimal(0)
    for tramo in tramos:
        limite = tramo.get("hasta")
        if limite is None or techo < Decimal(str(limite)):
            return _decimal(tramo.get("veces")) or VECES_EL_TECHO_POR_DEFECTO
    return _decimal(umbrales.get("veces_el_techo")) or VECES_EL_TECHO_POR_DEFECTO


def veces_que_pasa(grupo: Mapping[str, Any]) -> Decimal | None:
    """Cuántas veces el techo de la entidad suma el grupo."""
    suma = _decimal(grupo.get("suma"))
    techo = _decimal(grupo.get("techo"))
    if suma is None or techo is None or techo <= 0:
        return None
    return suma / techo


def evaluar(
    grupo: Mapping[str, Any], *,
    regla: Regla,
    version: VersionDeRegla,
    consultado_en: datetime,
    momento: datetime,
) -> Alerta | None:
    """Devuelve una Alerta si el grupo enciende la bandera, o `None`.

    **LA UNIDAD ES EL GRUPO, NO EL CONTRATO**, y por eso el expediente apunta a
    una clave compuesta y lleva adentro la lista de contratos. Emitir una
    Alerta por contrato daría 683 avisos donde hay 281 hallazgos, y cada aviso
    suelto no significaría nada: un contrato de mínima cuantía no tiene nada de
    particular. Lo que se encontró es la repetición.

    `None` NO es un fallo: es el resultado normal. Si la entidad no se puede
    mirar, levanta `NoSePuedeMirar` — que es una tercera cosa, distinta de las
    otras dos.
    """
    umbrales = version.umbrales

    if not techo_creible(grupo, umbrales):
        raise NoSePuedeMirar(
            f"la entidad {grupo.get('nit_entidad')!r} declara un techo de "
            f"{grupo.get('techo')} con un p95 de {grupo.get('p95_entidad')}: "
            "no se puede saber si fracciona"
        )

    minimas = grupo.get("minimas_entidad")
    minimo = umbrales.get("minimas_de_la_entidad", MINIMAS_DE_LA_ENTIDAD_POR_DEFECTO)
    if minimas is None or int(minimas) < int(minimo):
        raise NoSePuedeMirar(
            f"la entidad {grupo.get('nit_entidad')!r} tiene {minimas} mínimas "
            f"cuantías y hacen falta {minimo} para que su techo signifique algo"
        )

    contratos = grupo.get("contratos")
    if contratos is None or int(contratos) < int(
            umbrales.get("contratos_minimos", CONTRATOS_MINIMOS_POR_DEFECTO)):
        return None

    veces = veces_que_pasa(grupo)
    if veces is None:
        return None
    corte = corte_para(grupo, umbrales)
    if veces <= corte:
        return None

    ids: Sequence[str] = tuple(grupo.get("contratos_ids") or ())
    if not ids:
        # Sin los contratos, el Expediente no permitiría comprobar nada y la
        # Alerta sería una afirmación sin respaldo. No se emite.
        return None

    clave = "|".join((
        str(grupo.get("nit_entidad") or ""),
        str(grupo.get("proveedor_tipo") or ""),
        str(grupo.get("proveedor_numero") or ""),
        str(grupo.get("mes") or ""),
    ))

    return emitir(
        regla, version,
        id_registro_fuente=clave,
        dataset="contratos",
        valores_disparadores={
            "entidad": grupo.get("nombre_entidad"),
            "nit_entidad": grupo.get("nit_entidad"),
            "mes": str(grupo.get("mes") or ""),
            "contratos": int(contratos),
            "suma": str(_decimal(grupo.get("suma"))),
            "techo_de_la_entidad": str(_decimal(grupo.get("techo"))),
            "veces_el_techo": str(round(veces, 2)),
            "corte_de_su_tramo": str(corte),
            "minimas_de_la_entidad": int(minimas),
            "contratos_ids": list(ids),
        },
        consultado_en=consultado_en,
        momento=momento,
    )
