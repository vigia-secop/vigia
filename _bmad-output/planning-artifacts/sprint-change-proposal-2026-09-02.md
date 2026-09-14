---
title: "Propuesta de cambio de sprint — La marca de agua de ASSUMPTION-1 no es viable"
created: 2026-09-02
status: propuesta
disparador: "Sondeo de la API durante el diseño de la historia 1.2"
alcance: moderado
decide: Guillermo
---

# Propuesta de cambio de sprint — La marca de agua de ASSUMPTION-1 no es viable

## 1. Resumen del problema

El PRD fija en `ASSUMPTION-1` que la ingesta incremental use `ultima_actualizacion`
en Contratos y las fechas de publicación en Procesos como marca de agua. Al
diseñar la historia 1.2 sondeé la fuente real y el supuesto no se sostiene.

**Qué se midió** (datos.gov.co, dataset `jbjy-vk9h`, 2026-09-02):

| Medición | Resultado |
|---|---|
| Contratos con `ultima_actualizacion`, muestra de 20 ordenada por `:id` | 12 de 20 — **40% sin el campo** |
| Contratos con `ultima_actualizacion`, los 20 firmados más recientemente | **0 de 20 — 100% sin el campo** |
| `:created_at` y `:updated_at` de contratos de 2024, 2025 y 2026 | Idénticos entre sí y al milisegundo (`2026-08-25T09:05:54.277Z`) |
| Ídem en Procesos, para un proceso de 2022 | `2026-09-01T19:49:08.236Z`, también `:created_at` == `:updated_at` |

**Qué significa cada cosa:**

1. **`ultima_actualizacion` está vacío en buena parte de las filas, y sistemáticamente
   vacío en las más recientes.** En Socrata un campo nulo no llega como `null`: la
   clave simplemente no aparece. Un filtro `ultima_actualizacion > marca` no excluye
   esas filas una vez — las excluye **para siempre**, y en cada Ciclo. La ingesta
   incremental construida sobre ese campo perdería justamente los contratos nuevos,
   sin producir ningún síntoma: los Ciclos terminarían «bien», con conteos plausibles.

2. **Colombia Compra Eficiente recarga el dataset completo, no lo actualiza fila por
   fila.** Contratos firmados con dos años de diferencia comparten marca de tiempo de
   creación al milisegundo. En consecuencia el campo de sistema `:updated_at` —el
   candidato natural de reemplazo— tampoco sirve: cada recarga movería todas las filas
   y el «incremento» sería el universo entero.

**Por qué no lo atrapó la historia 1.3.** La validación de esquema compara campos
declarados, y `ultima_actualizacion` *sí está declarado* en los metadatos del dataset.
Está declarado y vacío. Es un hueco real de la validación actual, anotado abajo como
consecuencia.

## 2. Análisis de impacto

### Épicas

- **Épica 1 — Ver el SECOP sin ahogarse.** Impacto directo en la historia 1.2. Las
  historias 1.1 y 1.3 ya implementadas **no se tocan**: la capa cruda y la validación
  de esquema son independientes del mecanismo de cursor.
- **Épica 6 — Operación desatendida.** Impacto indirecto y real: el costo de un Ciclo
  diario cambia según la alternativa que se elija, y `ASSUMPTION-5` («un Ciclo diario
  nacional es viable en costo y tiempo») queda más expuesto de lo que estaba.
- **Épicas 2 a 5.** Sin impacto. Nada del motor de reglas, la revisión o la publicación
  depende de cómo se decida qué traer.

### Historias

| Historia | Impacto |
|---|---|
| 1.1 ingesta cruda | Ninguno. Su idempotencia por `(dataset, :id, hash)` es, de hecho, lo que hace baratas las alternativas de abajo. |
| 1.2 marca de agua | **Bloqueada.** Sus criterios de aceptación siguen siendo correctos en forma; cambia el campo sobre el que se apoyan y hace falta un criterio nuevo sobre el solapamiento. |
| 1.3 validación de esquema | Ninguno para lo entregado. Deja ver un hueco: valida presencia de campos, no que vengan poblados. |
| 6.1 Ciclo diario, 6.2 reporte de Ciclo | Sin cambio de criterios; sí cambia la magnitud que van a medir. |

### Conflictos con los artefactos de planeación

- **PRD, `ASSUMPTION-1`** — falsificado por medición. Hay que reescribirlo.
- **PRD, FR-1, segunda consecuencia** — «La ingesta usa `ultima_actualizacion` en
  Contratos y las fechas de publicación en Procesos como marca de agua». Falso para
  Contratos.
- **PRD, NFR «Costo de ingesta»** — sigue siendo válido, pero la alternativa elegida
  determina si se cumple.
- **Arquitectura, AD-4** — **no cae.** Dice que «la marca de agua es por dataset,
  persistida y auditable» y que un Ciclo registra cursor de entrada y de salida. Eso
  sigue siendo cierto con cualquiera de las opciones; AD-4 nunca nombró un campo.
- **Investigación de la API** — ya quedó corregida en dos puntos por la 1.1 (nombres
  de campos de adjudicación, y claves nulas ausentes). Este es el tercero.

### Impacto técnico

Ninguno sobre el código entregado. La capa cruda ya deduplica por contenido, así que
volver a leer un registro que no cambió cuesta una petición y cero filas. Esa propiedad
—construida en la 1.1 por otras razones— es la que vuelve viables las opciones B y C.

## 3. Camino recomendado

**Clasificación: ajuste directo (`Direct Adjustment`).** No hay que revertir trabajo
ni replantear la arquitectura. Se corrige un supuesto del PRD y se reescribe una
historia que todavía no se ha implementado.

### Las opciones sobre la mesa

**Opción A — Cursor por fecha del hecho, con ventana de solapamiento.** *(recomendada)*

El cursor deja de ser «cuándo se actualizó el registro» y pasa a ser «hasta qué fecha
de hecho ya leí»: `fecha_de_firma` en Contratos, `fecha_de_publicacion_del` en Procesos.
Ambos vienen poblados —son la razón de ser del registro— y ya se usan en la 1.1 para
acotar el rango. Cada Ciclo re-lee una ventana hacia atrás (por ejemplo 30 días) además
de lo nuevo, porque el SECOP publica con retraso: un contrato firmado el día 1 puede
aparecer el día 12.

- *A favor:* usa campos siempre presentes; el re-leído no cuesta filas gracias a la
  idempotencia de la 1.1; el tamaño de la ventana es un Umbral configurable, no código.
- *En contra:* una corrección retroactiva a un contrato viejo, fuera de la ventana, no
  se detecta. Se compensa con un barrido completo periódico (mensual), que sí la atrapa.
- *Costo:* un Ciclo diario trae lo nuevo más 30 días de solapamiento. Bajo.

**Opción B — Ventana móvil sin cursor.**

Cada Ciclo re-lee una ventana fija hacia atrás y punto. Sin cursor persistido.

- *A favor:* la más simple de todas; nada que corromper ni que reanudar.
- *En contra:* contradice AD-4, que exige cursor por dataset auditable, y renuncia a
  distinguir un Ciclo vacío legítimo de uno que no leyó nada por error.

**Opción C — Barrido completo cada Ciclo, con el hash decidiendo qué es nuevo.**

Traer el universo entero cada día y dejar que la identidad determinista de la 1.1
absorba lo repetido.

- *A favor:* la única que detecta *cualquier* cambio, incluidos los retroactivos.
- *En contra:* choca de frente con `ASSUMPTION-5` y con el NFR de costo de ingesta.
  Millones de registros diarios contra una API pública sin garantías de servicio.

**Opción D — Pedirle a Colombia Compra Eficiente un mecanismo de cambios.**

- *A favor:* resolvería el problema de raíz.
- *En contra:* no es una decisión que dependa del equipo ni tiene plazo. Anotarla como
  gestión paralela, no como plan.

### Recomendación

**Opción A**, con barrido completo mensual. Es la que respeta AD-4, la que no depende
de un campo que la fuente no llena, y la que aprovecha una propiedad que el sistema ya
tiene. La honestidad de la opción A es que **admite explícitamente** lo que no cubre —
correcciones retroactivas fuera de la ventana— en vez de fingir que un cursor sobre un
campo vacío las cubría.

**Riesgo residual:** si el retraso de publicación del SECOP resulta mayor que la ventana
elegida, se pierden registros. Mitigación: la ventana es un Umbral con vigencia, y el
reporte de Ciclo de la historia 6.2 debe incluir «cuántos registros entraron con fecha
de hecho anterior a la ventana» — si ese número roza el borde, la ventana se queda corta
y se ve antes de perder nada.

## 4. Cambios propuestos

### PRD — `ASSUMPTION-1`

**ACTUAL:**
> La ingesta usa `ultima_actualizacion` en Contratos y las fechas de publicación en
> Procesos como marca de agua. `[ASSUMPTION-1]`

**PROPUESTO:**
> La ingesta usa la fecha del hecho como marca de agua: `fecha_de_firma` en Contratos
> y `fecha_de_publicacion_del` en Procesos. Cada Ciclo re-lee una ventana de
> solapamiento hacia atrás, porque el SECOP publica con retraso, y un barrido completo
> periódico recoge las correcciones retroactivas. `ultima_actualizacion` no es utilizable:
> viene vacío en cerca del 40% de los contratos y en la totalidad de los más recientes
> (medido 2026-09-02). El campo de sistema `:updated_at` tampoco: la fuente recarga el
> dataset completo, de modo que cada recarga mueve todas las filas.

*Razón:* el supuesto original está falsificado por medición directa contra la fuente.

### PRD — FR-1, segunda consecuencia

**ACTUAL:**
> La ingesta usa `ultima_actualizacion` en Contratos y las fechas de publicación en
> Procesos como marca de agua.

**PROPUESTO:**
> La ingesta avanza sobre la fecha del hecho y re-lee una ventana de solapamiento
> configurable. Volver a leer un registro sin cambios no produce fila nueva ni Alerta
> repetida.

### PRD — NFR «Costo de ingesta», añadir

**PROPUESTO (añadir):**
> El costo de un Ciclo incluye la ventana de solapamiento, no solo lo nuevo. El barrido
> completo periódico se programa fuera de la ventana diaria.

### Épicas — Historia 1.2

**ACTUAL (título y criterios):**
> Historia 1.2: Ingesta incremental con marca de agua por dataset
> **Dado** un dataset con marca de agua registrada **Cuando** se ejecuta un Ciclo
> **Entonces** solo se consultan registros posteriores a esa marca **Y** al terminar se
> persiste la marca nueva.

**PROPUESTO:**
> Historia 1.2: Ingesta incremental con marca de agua y ventana de solapamiento
>
> **Dado** un dataset con marca de agua registrada y una ventana de solapamiento
> **Cuando** se ejecuta un Ciclo
> **Entonces** se consultan los registros cuya fecha de hecho sea posterior a la marca
> menos la ventana
> **Y** al terminar se persiste la marca nueva.
>
> **Dado** un registro ya presente que vuelve a entrar por el solapamiento
> **Cuando** se ingiere
> **Entonces** no se crea fila nueva y el Ciclo lo cuenta como duplicado.
>
> **Dado** un Ciclo que no encuentra registros nuevos **Cuando** termina **Entonces** se
> registra como Ciclo vacío con conteo cero **Y** se distingue explícitamente de un
> Ciclo fallido. *(sin cambio)*
>
> **Dado** un fallo de red a mitad de Ciclo **Cuando** el Ciclo se interrumpe
> **Entonces** la marca de agua no avanza **Y** el siguiente Ciclo reanuda sin perder
> registros. *(sin cambio)*
>
> **Dado** un Ciclo terminado
> **Cuando** se consulta su registro
> **Entonces** informa cuántos registros entraron con fecha de hecho anterior al inicio
> de la ventana — la señal de que la ventana se está quedando corta.

*Razón:* los criterios originales siguen siendo correctos en su forma; lo que cambia es
el campo del cursor y la necesidad de nombrar el solapamiento y su señal de alarma.

### Épicas — Historia nueva 1.7

**PROPUESTO (añadir al final de la épica 1):**
> ### Historia 1.7: Barrido completo periódico
>
> Como equipo, quiero re-leer el universo cada cierto tiempo, para que una corrección
> retroactiva en la fuente no quede invisible para siempre.
>
> **Dado** una programación de barrido **Cuando** se ejecuta **Entonces** se recorre el
> rango histórico completo del dataset **Y** los registros sin cambios no producen filas
> nuevas.
>
> **Dado** un barrido que encuentra registros modificados fuera de la ventana diaria
> **Cuando** termina **Entonces** los reporta aparte de los nuevos.

*Razón:* es la mitad que hace honesta a la opción A. Sin ella, la ingesta tiene un punto
ciego que nadie declaró.

### Arquitectura — sin cambios

AD-4 se mantiene tal cual. Se sugiere añadir una frase aclaratoria:

**PROPUESTO (añadir a AD-4):**
> El cursor es sobre la fecha del hecho, no sobre una marca de actualización de la
> fuente: el SECOP no publica una fiable. La ventana de solapamiento es parte del cursor,
> no un parche.

### Consecuencia para la historia 1.3 (ya entregada)

La validación de esquema comprueba que un campo esté **declarado**, no que venga
**poblado**. `ultima_actualizacion` habría pasado la validación mientras estaba vacío en
el 100% de los registros recientes. Propongo anotarlo como trabajo diferido, no como
cambio de la 1.3:

> Validar cobertura, no solo presencia: medir por Ciclo qué proporción de registros trae
> cada campo del que dependan reglas o cursores, y alertar cuando esa proporción se
> desplome. Es la versión de «falla ruidosamente» para un campo que se vacía en vez de
> desaparecer.

## 5. Entrega y siguientes pasos

**Alcance: moderado.** No requiere replanteo del arquitecto: ninguna decisión AD-1 a
AD-8 cae. Sí requiere que quien manda en el producto acepte reescribir `ASSUMPTION-1`,
`FR-1` y los criterios de la historia 1.2, y aceptar la 1.7 como historia nueva.

**Decide:** Guillermo.

**Si se aprueba:**

1. Aplicar las ediciones a `prd.md` y a `epics.md` de esta propuesta.
2. Añadir `1-7-barrido-completo` a `sprint-status.yaml`.
3. Anotar en `deferred-work.md` la validación de cobertura de campos.
4. Implementar la 1.2 reescrita con `bmad-build`, en un chat nuevo.

**Criterio de éxito:** un Ciclo diario que, sobre datos reales, no pierda ningún contrato
firmado en los últimos 30 días — comprobable comparando el conteo de la capa cruda contra
una consulta directa a la API para ese rango.

**Lo que NO hay que hacer:** implementar la 1.2 con `ultima_actualizacion` «por ahora,
para desbloquear». Produciría Ciclos verdes que pierden datos en silencio, que es
exactamente el modo de fallo contra el que está escrito este proyecto.
