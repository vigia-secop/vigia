"""El techo de lo posible: qué valor de contrato no puede ser cierto.

POR QUÉ EXISTE ESTE MÓDULO. El 2026-09-06, buscando la bandera 4.2, aparecieron
en la fuente valores que no pueden ser ciertos:

- Un proceso de la ESE Hospital Local San José con **$8 054 481 856 630 300**
  adjudicados. Ocho mil billones de pesos, en un renglón.
- Cinco casos del mismo número con tres ceros de más: `$431 340 000` de
  presupuesto contra `$431 340 000 000` adjudicado, en entidades distintas.

Eso no es un asunto de Reglas. Es un asunto de **todo lo que Vigía publica**.
El Panel dice «$12,91 billones en la ventana»; un solo registro con tres ceros
de más vuelve mentira ese total, pone al de la errata en la cima del ranking de
contratistas, y nadie se entera, **porque el número no falla: sale, se lee, y
está mal.**

Es el mismo daño que una alerta inventada, por otra puerta.

LO QUE ESTE MÓDULO NO HACE. No corrige. No adivina cuál era el valor verdadero.
No borra. Vigía no es la fuente y no puede escribir sobre ella. Lo único que
hace es **marcar**, para que los totales y los rankings puedan dejarlos fuera y
declararlo, y para que se puedan listar aparte con su valor tal cual.
"""

from __future__ import annotations

from decimal import Decimal

#: Techo de un contrato individual, en pesos colombianos.
#:
#: **De dónde sale este número, y por qué no es un umbral inventado.** El
#: Presupuesto General de la Nación de Colombia está en el orden de los
#: 500 billones de pesos (5 × 10^14) al año — Ley anual de presupuesto,
#: Ministerio de Hacienda y Crédito Público, https://www.minhacienda.gov.co.
#: Un contrato individual de 100 billones sería la quinta parte de todo lo que
#: el Estado colombiano gasta en un año, en un solo renglón de SECOP. No
#: existe, y no existirá en la vida útil de este proyecto.
#:
#: Esa es la diferencia con los umbrales que mataron a las historias 2.4 y 4.2:
#: aquel 20 de visualizaciones se escogía porque daba una cola de tamaño
#: cómodo. Este techo **sale del tamaño del Estado**, se puede citar, y su
#: fecha de vigencia se puede discutir sin mirar nuestros resultados.
#:
#: Deliberadamente holgado. El contrato público más grande de Colombia —una
#: concesión vial de cuarta generación— vive en el orden de los billones
#: (10^12), cien veces por debajo. El techo no está para separar «grande» de
#: «muy grande»: está para atajar lo **imposible**, y por eso se pone dos
#: órdenes de magnitud por encima de lo mayor que se ha visto. Un techo apretado
#: dejaría fuera contratos reales, que es exactamente el error contrario y peor.
TECHO_DE_CONTRATO = Decimal("1e14")

#: Fecha desde la que rige el techo de arriba, como pide la historia 2.1 para
#: todo tope normativo. Si el orden de magnitud del presupuesto nacional
#: cambia, se añade un techo nuevo con su fecha; **este no se edita**, porque
#: un contrato marcado en 2026 tiene que poder explicarse en 2029 con el techo
#: que lo marcó.
TECHO_VIGENTE_DESDE = "2026-09-06"

#: La fuente citable del techo, obligatoria por la misma razón.
TECHO_FUENTE = (
    "Presupuesto General de la Nación, orden de magnitud anual "
    "(~5 × 10^14 COP). Ministerio de Hacienda y Crédito Público."
)

#: Factor de la errata más común de la fuente: el mismo número con tres ceros
#: de más. Se busca de frente, comparando contratos de la misma entidad con el
#: mismo proveedor, y NO se corrige: se lista.
FACTOR_ERRATA_DE_MILES = 1000


def fuera_de_escala(valor) -> bool:
    """Si un valor de contrato no puede ser cierto.

    `None` no está fuera de escala: un contrato sin valor es otra cosa —falta
    el dato— y ya se cuenta aparte en el bloque de cobertura. Confundir «no
    puede ser» con «no está» haría que el Panel reportara como imposibles
    contratos que simplemente no traen la cifra.

    Un valor negativo tampoco es «imposible» en este sentido: existe y aparece
    en la fuente, normalmente en modificaciones. Se deja pasar a propósito para
    no esconder algo que sí merece verse.
    """
    if valor is None:
        return False
    return Decimal(str(valor)) >= TECHO_DE_CONTRATO
