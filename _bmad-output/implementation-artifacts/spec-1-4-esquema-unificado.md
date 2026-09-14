---
title: 'Historia 1.4 — Esquema unificado y cruce proceso–contrato'
type: 'feature'
created: '2026-09-03'
status: 'done'
baseline_commit: 'NO_VCS'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md'
  - '{project-root}/_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-03.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La capa cruda guarda Contratos y Procesos como dos montones de JSON sin relación entre sí. Casi ninguna Regla de las épicas 2 y 4 se puede escribir sobre eso: «adjudicación pegada al presupuesto» necesita el presupuesto, que vive en el Proceso, y el valor adjudicado, que vive en el Contrato. Sin el cruce, la mitad del producto no tiene sobre qué correr.

**Approach:** Derivar del crudo dos tablas tipadas —`proceso` y `contrato`— y enlazarlas por la llave que **realmente** las une, midiéndola contra la fuente en vez de deducirla del nombre de los campos. Lo que no cruza no se descarta: se conserva marcado y se cuenta, porque el porcentaje de huérfanos es un indicador de salud de la fuente, no un residuo a esconder.

## Boundaries & Constraints

**Always:**

- La llave de cruce es `contrato.proceso_de_compra` contra `proceso.id_del_portafolio`. Ambos viven en el espacio `CO1.BDOS.`. **Nunca** contra `proceso.id_del_proceso`, que vive en `CO1.REQ.` y no comparte un solo valor con Contratos.
- La capa normalizada se deriva **solo** de la capa cruda. No sale a la red. Rehacerla desde el mismo crudo tiene que dar exactamente la misma base.
- Se normaliza la versión **más reciente** de cada fila cruda. La capa cruda es de solo inserción y guarda todas las versiones; normalizar la vieja sobre la nueva dejaría la lectura mostrando el pasado.
- Un contrato que trae llave y no encuentra Proceso se conserva, se marca huérfano y es consultable.
- «Huérfano» y «sin llave de cruce» se cuentan por separado y se reportan por separado. Son fallos distintos con causas distintas.
- El porcentaje de huérfanos se mide **sobre los contratos que sí traen llave**, y es desconocido —no cero— cuando ninguno la trae.
- Ninguna conversión de tipo levanta por un valor ilegible: se guarda `None` y el registro entra igual. La capa normalizada expone la calidad del dato, no la juzga.
- La deduplicación de Procesos se cuenta y se reporta siempre, incluso en cero. Una deduplicación silenciosa es indistinguible de una pérdida de datos.

**Ask First:**

- Declarar única la relación portafolio → proceso. No está medido que un portafolio corresponda a un solo Proceso.
- Subir a la capa normalizada campos más allá de los que esta historia necesita.

**Never:**

- Descartar un contrato que no cruza.
- Cruzar contra `id_del_proceso`. Hay una prueba dedicada a impedir que vuelva.
- Identidad canónica de proveedor — es la 1.5. Territorio DIVIPOLA — es la 1.6.
- Guardar un enlace a un Proceso sin la llave que lo justifica. Lo impiden la clase y la base de datos, por separado.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Cruce normal | Contrato con `proceso_de_compra` = `CO1.BDOS.123`; existe Proceso con ese `id_del_portafolio` | Quedan enlazados | N/A |
| Huérfano | Contrato con llave; ningún Proceso la tiene | Entra con `id_del_proceso` nulo y cuenta como huérfano | Nunca se descarta |
| Sin llave | Contrato con `proceso_de_compra` vacío o ausente | Entra; cuenta como `sin_llave_de_cruce`, no como huérfano | N/A |
| Llave contra el campo equivocado | Un Proceso cuyo `id_del_proceso` coincide con el `proceso_de_compra` de un contrato | **No** se enlazan | Prueba de regresión dedicada |
| Proceso multi-lote | 21 filas crudas con el mismo `id_del_proceso` | Un solo Proceso; 20 filas colapsadas y reportadas | N/A |
| Portafolio ambiguo | Dos Procesos con el mismo `id_del_portafolio` | Gana el último y se registra la ambigüedad | Advertencia en el log, nunca silencio |
| Valor monetario ilegible | `valor_del_contrato` = `"n/a"` | `valor` en nulo; el contrato entra | La conversión no levanta |
| Campo vacío o de espacios | `"   "` | Se trata como ausente | N/A |
| Registro sin identidad | Contrato sin `id_contrato` | Se descarta, se cuenta y se nombra en el log | Es el único descarte admitido |
| Ninguno trae llave | 100 contratos, ninguno con `proceso_de_compra` | Porcentaje de huérfanos: **no medible**, no `0 %` | N/A |
| Sin Procesos ingeridos | Contratos con llave, tabla `proceso` vacía | Todo huérfano, con el mensaje de que falta ingerir `procesos` | Diagnóstico, no error |
| Repetir la normalización | Correrla dos veces sobre el mismo crudo | Base idéntica | N/A |
| Crudo con dos versiones | La misma fila ingerida ayer y hoy | Se normaliza la de hoy | N/A |
| Enlace inventado | `id_del_proceso` poblado con `proceso_de_compra` nulo | Imposible de construir y rechazado por la base | Dos barreras independientes |

</frozen-after-approval>

## Code Map

Módulo nuevo `vigia/normalizado/`, paralelo a `vigia/crudo/`: uno guarda lo que llegó, el otro lo lee.

- `vigia/normalizado/modelo.py` — `ProcesoNormalizado`, `ContratoNormalizado`, las constantes de llave y los conversores tolerantes.
- `vigia/normalizado/cruce.py` — `deduplicar_procesos`, `indexar_por_portafolio`, `cruzar_contratos`, `resumir`, `ResumenNormalizacion`, y el Protocol `FuenteCruda`.
- `vigia/normalizado/postgres.py` — lectura de la última versión de cada fila con cursor con nombre, y escritura por lotes con `ON CONFLICT DO UPDATE`.
- `vigia/normalizado/__main__.py` — `python -m vigia.normalizado`; imprime las cuatro señales.
- `migraciones/004_capa_normalizada.sql` — `proceso`, `contrato`, la restricción de enlace, los índices y las columnas de señales en `ciclo`.
- `tests/test_normalizado.py` — 18 pruebas de unidad, una por fila de la matriz.
- `tests/test_postgres.py` — 5 pruebas de integración: cruce completo, idempotencia, versión más reciente, y las dos barreras de la base.
- `probar.ps1` — PASO 10, la normalización dentro del guion de verificación de punta a punta.

## Tasks & Acceptance

**Execution:**

- [x] Medir la llave de cruce contra la fuente antes de escribir una línea de código.
- [x] `vigia/normalizado/modelo.py` — tipos, conversores que no levantan, y las propiedades `huerfano` / `sin_llave_de_cruce`.
- [x] `vigia/normalizado/cruce.py` — deduplicación, índice, cruce y resumen con conteos verificables.
- [x] `migraciones/004_capa_normalizada.sql` — tablas, restricción de enlace, índice parcial de huérfanos y columnas de señales.
- [x] `vigia/normalizado/postgres.py` — `DISTINCT ON` por identidad, cursor con nombre y escritura por lotes.
- [x] `vigia/normalizado/__main__.py` — las cuatro señales impresas, con el diagnóstico de «faltan Procesos».
- [x] `tests/test_normalizado.py` — cada fila de la matriz, más la regresión contra `id_del_proceso`.
- [x] `tests/test_postgres.py` — el cruce contra el motor real y las dos barreras de la base.
- [x] `probar.ps1` — PASO 10.
- [x] Correr la normalización sobre los contratos reales ya ingeridos. Primera corrida: 25 749 contratos, 100 % huérfanos por no haber Procesos todavía, con el diagnóstico correcto impreso.
- [x] Ingerir el dataset `procesos` y volver a medirlo con las dos mitades presentes. 340 995 Procesos (349 957 filas, 8 962 colapsadas); **86,9 % de contratos enlazados, 13,1 % huérfanos**, medido el 2026-09-03.

**Acceptance Criteria:**

- Dado un contrato con `proceso_de_compra`, cuando existe un Proceso cuyo `id_del_portafolio` es ese mismo valor, entonces quedan enlazados en la capa normalizada.
- Dado un contrato sin Proceso correspondiente, cuando se normaliza, entonces se marca como huérfano, sigue siendo consultable y no se descarta.
- Dado un Ciclo completo, cuando termina la normalización, entonces se reporta el porcentaje de huérfanos.
- Dado un Ciclo completo, cuando hay contratos **sin** `proceso_de_compra` poblado, entonces se reportan como señal aparte del porcentaje de huérfanos.

## Spec Change Log

- **2026-09-03** — Verificada de punta a punta sobre datos reales. El cruce por `id_del_portafolio` funciona: 22 365 de 25 749 contratos encontraron su Proceso. Los 3 384 huérfanos son un **techo**, no la medida final: los Procesos se trajeron desde el 1 de julio y un contrato de agosto puede venir de un Proceso muy anterior.
- **2026-09-03** — Medida la ambigüedad que la historia dejó sin declarar: **3 400 portafolios apuntan a más de un Proceso** (1,0 % de 340 995). La decisión de no hacer único `proceso_portafolio_idx` era correcta; con índice único la ingesta habría fallado.

- **2026-09-03** — La historia se planificó sobre una llave equivocada. `sprint-change-proposal-2026-09-03.md` documenta la medición que la corrigió; el primer criterio de aceptación y `prd.md` FR-2 se reescribieron antes de implementar.
- **2026-09-03** — Añadido el cuarto criterio: «sin llave de cruce» como señal separada de «huérfano».
- **2026-09-03** — El cuarto criterio del épico dice «supera un umbral configurable». Se implementó el reporte separado, **no** el umbral: sin una medición del valor normal de esta señal, cualquier umbral sería inventado. Anotado en `deferred-work.md`.

## Design Notes

**Por qué se midió la llave en vez de leerla.** El PRD decía cruzar `proceso_de_compra` contra `id_del_proceso`. Los nombres lo hacían obvio y era falso: 30 de 30 valores de `id_del_proceso` estaban en el espacio `CO1.REQ.`, y 25 de 25 valores de `proceso_de_compra` en `CO1.BDOS.`. Ni una coincidencia posible. El cruce contra `id_del_portafolio` acertó 5 de 5, con confirmación independiente por `referencia_del_proceso`. Un cruce equivocado no falla: produce cero enlaces y una tasa de huérfanos del 100 %, que se habría leído como «al SECOP le faltan datos». La prueba `test_no_se_cruza_contra_id_del_proceso` existe para que el error no vuelva por la puerta de atrás.

**Por qué los huérfanos se conservan.** Son el indicador de salud de la fuente que pide FR-2. Descartarlos dejaría la base más limpia y al producto ciego sobre exactamente aquello que vino a vigilar.

**Por qué dos señales y no una.** Un contrato sin la llave y un contrato con llave que no encuentra su Proceso tienen causas distintas: el primero es un campo que la fuente deja vacío, el segundo puede ser un Proceso que aún no se ingirió. Sumarlos esconde el primero, que es el mismo modo de fallo que vació a `ultima_actualizacion` en la historia 1.3.

**Por qué `None` y no `0.0`.** Cuando ningún contrato trae llave, la proporción de huérfanos no es cero: no existe. Devolver `0.0` diría «todo cruzó bien» en el peor caso posible.

**Por qué `DISTINCT ON` y no un `GROUP BY`.** La capa cruda guarda todas las versiones de una fila. Sin quedarse con la última, un contrato que cambió de valor aparecería dos veces y cuál gana dependería del orden de lectura — un no determinismo que solo se nota cuando ya contaminó un conteo.

**Por qué la tabla normalizada sí se actualiza.** La capa cruda es un registro histórico y no se toca. Esta es una lectura derivada: reescribir cada fila entera con `ON CONFLICT DO UPDATE` es lo que hace que rehacerla desde el mismo crudo dé el mismo resultado. Una fusión parcial dejaría restos de una normalización anterior.

**Por qué el índice de portafolio no es único.** Sería la restricción correcta si un portafolio correspondiera siempre a un solo Proceso, y eso no está medido. Declararlo único hoy convertiría un supuesto no verificado en un fallo de ingesta en producción. Mientras tanto, la ambigüedad se registra en el log.

**Por qué la restricción de enlace está dos veces.** `__post_init__` impide construir en Python un contrato enlazado sin llave; el `CHECK` de la base impide escribirlo por cualquier otra vía. La segunda no es redundante: protege contra la carga que no pase por el código.

## Verification

**Commands:**

- `pytest` — expected: toda la suite pasa; las de integración se omiten sin `VIGIA_DSN_PRUEBAS`.
- `VIGIA_DSN_PRUEBAS=... pytest -m postgres` — expected: 31 pruebas contra el motor real, incluido el cruce completo y la idempotencia.
- `python -m vigia.normalizado --dsn ...` — expected: las cuatro señales; correrlo dos veces deja la base idéntica.
- `probar.ps1` — expected: los 10 pasos, con la normalización al final.

## Suggested Review Order

**La llave de cruce, que es toda la historia**

- El nombre del campo engaña y el comentario lo dice antes que el código.
  [`modelo.py:18`](../../vigia/normalizado/modelo.py#L18)

- La regresión que impide que el error vuelva.
  [`test_normalizado.py:221`](../../tests/test_normalizado.py#L221)

- Y el cruce, que es deliberadamente aburrido una vez la llave está bien.
  [`cruce.py:172`](../../vigia/normalizado/cruce.py#L172)

**Que lo que no cruza siga existiendo**

- Huérfano y sin llave, dos propiedades y no una.
  [`modelo.py:164`](../../vigia/normalizado/modelo.py#L164)

- La proporción se mide sobre la población correcta, y es `None` cuando no hay población.
  [`cruce.py:85`](../../vigia/normalizado/cruce.py#L85)

- El comando lo dice con palabras: «no medible», no «0 %».
  [`vigia/normalizado/__main__.py:104`](../../vigia/normalizado/__main__.py#L104)

**Que los conteos no puedan mentir**

- El resumen se niega a construirse si las cuentas no cuadran.
  [`cruce.py:56`](../../vigia/normalizado/cruce.py#L56)

- Las filas colapsadas se reportan siempre, incluso en cero.
  [`cruce.py:72`](../../vigia/normalizado/cruce.py#L72)

- Un portafolio ambiguo gana el último **y lo dice**.
  [`cruce.py:138`](../../vigia/normalizado/cruce.py#L138)

**Que rehacerlo dé lo mismo**

- Solo la versión más reciente de cada fila cruda.
  [`postgres.py:21`](../../vigia/normalizado/postgres.py#L21)

- Y la prueba que lo fija contra el motor real.
  [`test_postgres.py:740`](../../tests/test_postgres.py#L740)

- Reescritura entera, no fusión parcial.
  [`postgres.py:63`](../../vigia/normalizado/postgres.py#L63)

**Periféricos**

- La restricción de enlace, la segunda vez, en la base.
  [`004_capa_normalizada.sql:74`](../../migraciones/004_capa_normalizada.sql#L74)

- El índice de portafolio, deliberadamente no único, con el porqué escrito.
  [`004_capa_normalizada.sql:49`](../../migraciones/004_capa_normalizada.sql#L49)

- Índice parcial: solo los huérfanos, que son los que se consultan.
  [`004_capa_normalizada.sql:86`](../../migraciones/004_capa_normalizada.sql#L86)

- Lotes de mil: el barrido nacional no cabe en una sentencia.
  [`postgres.py:79`](../../vigia/normalizado/postgres.py#L79)
