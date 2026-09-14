---
title: "Propuesta de cambio de sprint — La llave de cruce de ASSUMPTION-2 no es la que dice el PRD"
created: 2026-09-03
status: aprobada
disparador: "Sondeo de la API al reunir contexto para la historia 1.4"
alcance: menor
decide: Guillermo
---

# Propuesta de cambio de sprint — La llave de cruce de ASSUMPTION-2 no es la que dice el PRD

## 1. Resumen del problema

`FR-2` y `ASSUMPTION-2` fijan que Contratos y Procesos se cruzan por
`proceso_de_compra` (Contratos) e `id_del_proceso` (Procesos). Al reunir el
contexto de la historia 1.4 sondeé la fuente real y **los dos campos viven en
espacios de nombres distintos: no cruzan nunca, ni una sola fila.**

La buena noticia es que sí existe una llave, y es otra columna del mismo
dataset de Procesos.

**Qué se midió** (datos.gov.co, 2026-09-03):

| Medición | Resultado |
|---|---|
| Prefijo de `proceso_de_compra` en Contratos (`jbjy-vk9h`), muestra de 25 ordenada por `:id` | `CO1.BDOS.` en 25 de 25 |
| Prefijo de `id_del_proceso` en Procesos (`p6dx-8zbt`), muestra de 30 ordenada por `:id` | `CO1.REQ.` en 30 de 30 |
| `p6dx-8zbt?id_del_proceso=CO1.BDOS.3452554` | **cero filas** |
| `p6dx-8zbt?id_del_portafolio=CO1.BDOS.3452554` | **una fila**, `id_del_proceso = CO1.REQ.3544146` |
| Cruce por `id_del_portafolio` sobre los 5 primeros contratos del dataset | **5 de 5** |

**Los cuatro espacios de nombres del SECOP II**, tal como aparecen en los datos:

| Prefijo | Qué identifica | Dónde aparece |
|---|---|---|
| `CO1.PCCNTR.` | el Contrato | `contratos.id_contrato` |
| `CO1.BDOS.` | el «portafolio» del que cuelga el proceso | `contratos.proceso_de_compra` **y** `procesos.id_del_portafolio` |
| `CO1.REQ.` | el Procedimiento | `procesos.id_del_proceso` |
| `CO1.NTC.` | el aviso público | el `noticeUID` dentro de `urlproceso`, en ambos datasets |

`proceso_de_compra` no nombra un `id_del_proceso`: nombra un `id_del_portafolio`.
El nombre del campo en Contratos es lo que induce el error, y el PRD lo heredó.

**Confirmación independiente.** No se apoya solo en que los identificadores
coincidan. En 3 de los 5 casos cruzados, `referencia_del_proceso` (Procesos) y
`referencia_del_contrato` (Contratos) traen además la misma cadena escrita a
mano por la entidad —`CPS-3548-2022`, `HDSJDD-CD-0404-2026`—, lo que confirma
que las dos filas hablan del mismo trámite y no de una colisión numérica.

**Y a la vez descarta la alternativa obvia:** en los otros 2 casos las
referencias *no* coinciden (`90-2025` contra `ASISTENCIAL LOTE 6-2025`), así que
la referencia humana **no sirve como llave de cruce**. Es útil para verificar,
inútil para unir.

## 2. Análisis de impacto

### Épicas

- **Épica 1.** Impacto directo y exclusivo en la historia 1.4, que todavía no
  se ha empezado. Las historias 1.1, 1.2 y 1.3 ya implementadas **no se tocan**:
  ninguna sabe de cruces.
- **Épicas 2 a 5.** Sin impacto hoy. Toda Regla que necesite datos de ambos
  lados dependerá de esta llave, así que corregirla ahora es lo que impide que
  el error se propague a la lógica de detección.
- **Épica 6.** Sin impacto.

### Historias

- **1.4** — Sus criterios de aceptación nombran `id_del_proceso`. Hay que
  reescribirlos antes de implementarla. Es el único cambio de alcance.
- **1.5 y 1.6** — Enriquecen el esquema que fija la 1.4; se benefician de que
  la llave sea la correcta, pero sus criterios no cambian.

### Lo que este hallazgo **no** resuelve

`ASSUMPTION-2` pide dos cosas: *qué* llave, y *cuánto* cruza. Esto resuelve la
primera con evidencia. **La segunda sigue abierta**: 5 de 5 sobre las primeras
filas del dataset no es una tasa de huérfanos, es una prueba de existencia. La
tasa real solo se mide ingiriendo ambos datasets y contándolo, que es
precisamente el entregable de la 1.4.

## 3. Alternativas consideradas

**Opción A — Corregir la llave a `id_del_portafolio` y seguir con la 1.4.**
Es un cambio de dos nombres de campo en los criterios de aceptación y en el PRD.
La forma de la historia —enlazar, marcar huérfanos, reportar el porcentaje— no
cambia en nada.
*Costo:* reescribir `FR-2`, `ASSUMPTION-2` y los criterios de la 1.4.
*Riesgo:* ninguno identificado. La evidencia es directa y doblemente confirmada.

**Opción B — Cruzar por el `noticeUID` (`CO1.NTC.`) extraído de `urlproceso`.**
Ambos datasets traen ese identificador. Funcionaría, pero exige parsear una URL
para obtener la llave, en un campo que además llega anidado como
`{"url": "..."}`. Una llave que hay que extraer con una expresión regular de un
enlace es frágil frente a cualquier cambio de formato del enlace.
*Se descarta,* pero conviene guardarla: sirve como verificación cruzada barata
cuando el cruce por `id_del_portafolio` falle y haya que entender por qué.

**Opción C — Cruzar por `referencia_del_proceso` / `referencia_del_contrato`.**
Descartada por la medición: coinciden en 3 de 5. Son cadenas que escribe cada
entidad a mano, sin formato garantizado.

**Opción D — Aplazar la 1.4 hasta tener el esquema de Procesos capturado.**
No es una alternativa a las anteriores sino un prerrequisito de todas: la 1.4
no puede implementarse sin `vigia/schema/esperado/procesos.json`, que sigue sin
capturarse (anotado en `deferred-work.md`). Va como tarea previa, no como opción.

**Recomendación: Opción A**, más la captura de `procesos.json` como paso previo.

## 4. Cambios propuestos

### En el PRD (`prds/prd-vigia-secop-2026-09-02/prd.md`)

`FR-2`, primera consecuencia — reescribir:

> - Existe una llave de cruce entre `proceso_de_compra` (Contratos) e
>   `id_del_portafolio` (Procesos). Ambos son identificadores del espacio
>   `CO1.BDOS.`. **No** se cruza contra `id_del_proceso`, que es del espacio
>   `CO1.REQ.` y no comparte valores con ninguna columna de Contratos.
>   `[ASSUMPTION-2]`

`ASSUMPTION-2`, en la tabla de supuestos — reescribir:

> | ASSUMPTION-2 | ~~`proceso_de_compra` e `id_del_proceso` cruzan de forma fiable~~ **Corregido el 2026-09-03:** la llave es `proceso_de_compra` ↔ `id_del_portafolio`; `id_del_proceso` está en otro espacio de nombres y no cruza nunca. Sigue abierto **cuánto** cruza | Llave verificada contra la API, 5 de 5 y confirmada por `referencia_del_proceso`. Ver `sprint-change-proposal-2026-09-03.md`. El porcentaje de huérfanos lo mide la 1.4 sobre la ingesta real |

### En las épicas (`epics.md`, historia 1.4)

Primer criterio — reescribir:

> **Dado** un contrato con `proceso_de_compra`
> **Cuando** existe un proceso cuyo `id_del_portafolio` es ese mismo valor
> **Entonces** quedan enlazados en la capa normalizada.

Añadir un cuarto criterio, que es la lección de `ASSUMPTION-1` aplicada aquí:

> **Dado** un Ciclo completo
> **Cuando** la proporción de contratos **sin** `proceso_de_compra` poblado
> supera un umbral configurable
> **Entonces** se reporta como señal aparte del porcentaje de huérfanos.
>
> Un contrato sin la llave y un contrato con llave que no encuentra su proceso
> son fallos distintos con causas distintas, y contarlos juntos esconde el
> primero. Es el mismo modo de fallo que vació a `ultima_actualizacion`: un
> campo declarado que viene vacío.

### En el código

Ninguno todavía: la 1.4 no se ha empezado. El cambio entra en su spec.

## 5. Tareas previas

1. **Capturar el esquema de Procesos**, en una máquina con salida a
   datos.gov.co:

   ```
   python -m vigia.schema --capturar --dataset procesos
   ```

   Revisar el `diff` y versionarlo. Sin este archivo cualquier ingesta de
   `procesos` aborta con código 2, y la 1.4 no tiene con qué cruzar.

   *Por qué no se hizo aquí:* el contenedor de esta sesión no tiene salida a
   datos.gov.co (solo a través de la herramienta de fetch, que devuelve texto
   resumido). Escribir `procesos.json` a mano desde ese resumen convertiría un
   control de seguridad en una transcripción no verificada, que es exactamente
   lo que el README prohíbe: «el esquema esperado se captura, no se escribe a
   mano».

2. **Confirmar `campo_fecha_rango` de Procesos.** `vigia/ingest/datasets.py`
   usa `fecha_de_publicacion_del`. El sondeo lo confirma como campo existente y
   poblado (`2022-01-18T00:00:00.000`), pero el dataset tiene además
   `fecha_de_publicacion`, `fecha_de_ultima_publicaci` y cuatro
   `fecha_de_publicacion_fase*`. Conviene decidir cuál es «la fecha del hecho»
   de un Proceso con el mismo cuidado con que se decidió `fecha_de_firma` para
   Contratos, y no por el nombre.

## 6. Hallazgo suelto, para el registro

Al leer una fila completa de Procesos se confirma lo que `epic-1-context.md` ya
anotaba: **los nombres de campo de Procesos que usa el PRD no existen.** El
campo real del NIT del adjudicatario es `nit_del_proveedor_adjudicado`, no
`nit_del_proveedor_ganador`; el del valor es `valor_total_adjudicacion`, no
`valor_del_contrato_adjudicado`. Se anota aquí para que quien escriba la 1.5
(identidad de proveedor) no vuelva a partir del PRD sin verificar.

## 6.bis Segundo hallazgo: el grano de `p6dx-8zbt` no es el Proceso

Buscando si un portafolio puede tener varios procesos —pregunta necesaria para
decidir el esquema— apareció algo mayor.

**Qué se midió** (2026-09-03):

| Consulta | Filas |
|---|---|
| `p6dx-8zbt?id_del_proceso=CO1.REQ.3544146` | 1 |
| `p6dx-8zbt?id_del_proceso=CO1.REQ.10772032` | **21** |

Las 21 filas son idénticas en todo lo procedimental —`fase`,
`estado_del_procedimiento`, `numero_de_lotes` (460),
`codigo_principal_de_categoria`— y difieren en el proveedor adjudicado y el
valor. Es un proceso de 460 lotes con varios adjudicatarios.

**El grano de `p6dx-8zbt` es la adjudicación, no el Proceso.** El glosario del
PRD afirma lo contrario. `id_del_proceso` **no es llave primaria** del dataset.

**Por qué no se había visto.** La inmensa mayoría de Procesos tiene una sola
adjudicación, así que trae una sola fila. El caso de muchas filas existe, es
minoritario, y es exactamente el tipo de contrato grande que un vigilante de
contratación pública quiere mirar. El sesgo del error apunta hacia lo que más
importa.

**Qué se rompe si no se corrige:**

- Una tabla `proceso` con `id_del_proceso` como llave primaria falla al insertar
  el segundo lote, o —peor— lo descarta en silencio según cómo se escriba el
  `ON CONFLICT`.
- Contar filas de `p6dx-8zbt` sobreestima el número de Procesos.
- El **denominador** del porcentaje de huérfanos queda inflado por los
  procesos multiadjudicación, y el indicador que la 1.4 debe producir queda mal
  desde el primer Ciclo.

**Qué se propone para la 1.4:**

1. La tabla normalizada `proceso` se llena **deduplicando** por
   `id_del_proceso`, quedándose con la fila cruda más reciente.
2. Se cuenta y se reporta cuántas filas se colapsaron. Una deduplicación
   silenciosa es indistinguible de una pérdida de datos; si el número aparece en
   el registro del Ciclo, nadie tiene que adivinar por qué las filas crudas y
   los Procesos no cuadran.
3. El detalle por adjudicatario —proveedor, valor adjudicado, lote— **no se
   normaliza en la 1.4**. Se queda en la capa cruda, que lo conserva completo,
   hasta la 1.5, que es la historia de identidad de proveedor y su dueña natural.

**Lo que queda sin medir:** si un mismo `id_del_portafolio` puede corresponder a
más de un `id_del_proceso`. La consulta de agrupación sobre el universo nacional
excede el tiempo de respuesta de la API sin token. Por eso el diseño **no
asume** cardinalidad: el enlace se resuelve por unión sobre el identificador de
portafolio, que funciona igual con uno o con varios, en vez de por una clave
foránea que obligaría a apostar.

## 7. Decisión

- [x] **Opción A** — corregir la llave a `id_del_portafolio`, capturar
      `procesos.json` y seguir con la 1.4
- [ ] Opción B — cruzar por el `noticeUID` de `urlproceso`
- [ ] Otra

**Aprobada por Guillermo el 2026-09-03.** Aplicado el mismo día:

- `prd.md` — `FR-2`, primera consecuencia: reescrita con `id_del_portafolio`.
- `prd.md` — `ASSUMPTION-2`: tachado el enunciado viejo, anotada la corrección y
  lo que sigue abierto (la tasa, no la llave).
- `epics.md` — historia 1.4, primer criterio: reescrito.
- `epics.md` — historia 1.4: añadido el cuarto criterio, la señal de cobertura
  de la llave.
- `deferred-work.md` — dos entradas nuevas: el `noticeUID` como verificación
  cruzada, y la fecha del hecho de Procesos sin decidir.

Queda como prerrequisito de la 1.4, sin hacer: capturar
`vigia/schema/esperado/procesos.json` en una máquina con salida a datos.gov.co.
