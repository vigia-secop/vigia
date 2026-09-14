---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - planning-artifacts/briefs/brief-vigia-secop-2026-09-02/brief.md
  - planning-artifacts/research/api-secop-viabilidad-2026-09-02.md
  - planning-artifacts/prds/prd-vigia-secop-2026-09-02/prd.md
  - planning-artifacts/architecture/architecture-vigia-secop-2026-09-02/spine.md
---

# Vigía SECOP — Desglose de épicas

## Resumen

Traduce el PRD y la arquitectura en historias implementables. El orden de las épicas es el orden de construcción: cada una entrega valor por sí sola y habilita la siguiente sin depender de ella.

El usuario de todas las historias es el equipo — no hay usuarios externos en v1. Donde dice "el equipo", el actor es quien opera y calibra el sistema.

## Inventario de requisitos

### Funcionales

FR-1 ingesta incremental · FR-2 esquema unificado y llave de cruce · FR-3 normalización territorial · FR-4 identidad de proveedor · FR-5 reglas versionadas · FR-6 catálogo de banderas · FR-7 modo calibración · FR-8 expediente · FR-9 lenguaje · FR-10 marcar alertas · FR-11 tasa de confirmación · FR-12 compuerta humana · FR-13 agregado por defecto · FR-14 sin personas naturales · FR-15 sustento visible · FR-16 registro y rectificación

### No funcionales

Reproducibilidad · datos personales · riesgo reputacional y legal · resiliencia de la fuente · retención · costo de ingesta

### Invariantes de arquitectura

INV-1 expediente obligatorio · INV-2 lenguaje verificado · INV-3 calibración previa · INV-4 aprobación humana · INV-5 sin personas naturales publicadas · AD-1 a AD-8

## Mapa de cobertura

| Requisito | Historias |
|---|---|
| FR-1 | 1.1, 1.2, 1.3, 1.7 |
| FR-2 | 1.4 |
| FR-3 | 1.6 |
| FR-4 | 1.5 |
| FR-5 | 2.1 |
| FR-6 | 2.4, 4.1–4.8 |
| FR-7 | 2.5 |
| FR-8 | 2.2, 2.3 |
| FR-9 | 2.6 |
| FR-10 | 3.2 |
| FR-11 | 3.3, 3.4 |
| FR-12 | 5.3 |
| FR-13 | 5.1 |
| FR-14 | 5.2 |
| FR-15 | 5.4 |
| FR-16 | 5.5 |
| NFR resiliencia | 1.3, 6.2 |
| NFR reproducibilidad | 2.2, 6.3 |
| NFR costo de ingesta | 6.1, 6.2 |

## Lista de épicas

1. **Ver el SECOP sin ahogarse** — datos ingeridos y normalizados, consultables.
2. **La primera bandera, calibrada** — el motor completo probado con una regla real.
3. **Revisar y medir** — el bucle de calibración cierra con evidencia.
4. **El catálogo completo** — las nueve banderas restantes.
5. **Publicar sin quemarse** — el canal público, con sus controles.
6. **Operación desatendida** — que corra solo treinta días.

**Nota de secuencia.** La épica 5 tiene una dependencia externa bloqueante: el concepto jurídico. Se puede construir en paralelo, pero no se publica nada hasta tenerlo.

---

## Épica 1: Ver el SECOP sin ahogarse

Al terminar, el equipo puede consultar contratos y procesos del SECOP en un esquema unificado, con territorio y proveedor resueltos, sin tocar la API a mano. Es la base de todo lo demás y ya tiene valor por sí sola: permite responder preguntas sobre contratación que hoy exigen media hora de trabajo manual.

### Historia 1.1: Traer datos del SECOP y guardarlos crudos

Como equipo,
quiero consultar los datasets del SECOP y guardar la respuesta tal como llega,
para tener una fuente inmutable que pueda reprocesar cuando cambie la lógica.

**Criterios de aceptación:**

**Dado** un dataset del SECOP y un rango de fechas
**Cuando** se ejecuta la ingesta
**Entonces** cada registro se guarda en la capa cruda con la fecha y hora de consulta
**Y** el contenido guardado es idéntico al que devolvió la API, sin transformación.

**Dado** un registro ya presente en la capa cruda
**Cuando** se vuelve a ingerir sin cambios
**Entonces** no se crea un duplicado.

**Dado** que la consulta devuelve más registros que el límite de página
**Cuando** se ejecuta la ingesta
**Entonces** se recorren todas las páginas hasta agotar el resultado.

### Historia 1.2: Ingesta incremental con marca de agua y ventana de solapamiento

Como equipo,
quiero que cada ejecución traiga solo lo nuevo o modificado,
para no reprocesar millones de registros cada día.

> Revisada el 2026-09-02 por `sprint-change-proposal-2026-09-02.md`: el cursor va sobre
> la fecha del hecho, no sobre `ultima_actualizacion`, que la fuente no llena.

**Criterios de aceptación:**

**Dado** un dataset con marca de agua registrada y una ventana de solapamiento
**Cuando** se ejecuta un Ciclo
**Entonces** se consultan los registros cuya fecha de hecho sea posterior a la marca menos la ventana
**Y** al terminar se persiste la marca nueva.

**Dado** un registro ya presente que vuelve a entrar por el solapamiento
**Cuando** se ingiere
**Entonces** no se crea fila nueva
**Y** el Ciclo lo cuenta como duplicado.

**Dado** un Ciclo que no encuentra registros nuevos
**Cuando** termina
**Entonces** se registra como Ciclo vacío con conteo cero
**Y** se distingue explícitamente de un Ciclo fallido.

**Dado** un fallo de red a mitad de Ciclo
**Cuando** el Ciclo se interrumpe
**Entonces** la marca de agua no avanza
**Y** el siguiente Ciclo reanuda sin perder registros.

**Dado** un Ciclo terminado
**Cuando** se consulta su registro
**Entonces** informa cuántos registros entraron con fecha de hecho anterior al inicio de la ventana
**Y** esa cifra es la señal de que la ventana se está quedando corta.

### Historia 1.3: Validación de esquema que falla ruidosamente

Como equipo,
quiero que la ingesta se detenga si la fuente cambió de forma,
para no descubrir semanas después que llevo un mes guardando nulos.

**Criterios de aceptación:**

**Dado** el conjunto de campos esperados por dataset
**Cuando** la respuesta de la API no trae alguno
**Entonces** el Ciclo se detiene con error que nombra el campo faltante
**Y** no se escribe nada en la capa normalizada.

**Dado** que la API devuelve un campo nuevo no esperado
**Cuando** se ejecuta la ingesta
**Entonces** el Ciclo continúa
**Y** el campo nuevo se registra como novedad para revisión.

### Historia 1.4: Esquema unificado y cruce proceso–contrato

Como equipo,
quiero relacionar cada contrato con el proceso que lo originó,
para poder aplicar reglas que necesitan datos de ambos.

**Criterios de aceptación:**

**Dado** un contrato con `proceso_de_compra`
**Cuando** existe un proceso cuyo `id_del_portafolio` es ese mismo valor
**Entonces** quedan enlazados en la capa normalizada.

> La llave es `id_del_portafolio`, no `id_del_proceso`. Los dos campos de
> Procesos se parecen en el nombre y viven en espacios distintos: el segundo es
> `CO1.REQ.` y no cruza con nada de Contratos. Corregido por
> `sprint-change-proposal-2026-09-03.md`.

**Dado** un contrato sin proceso correspondiente
**Cuando** se normaliza
**Entonces** se marca como huérfano y sigue siendo consultable
**Y** no se descarta.

**Dado** un Ciclo completo
**Cuando** termina la normalización
**Entonces** se reporta el porcentaje de huérfanos del Ciclo.

**Dado** un Ciclo completo
**Cuando** la proporción de contratos **sin** `proceso_de_compra` poblado supera
un umbral configurable
**Entonces** se reporta como señal aparte del porcentaje de huérfanos.

> Un contrato sin la llave y un contrato con llave que no encuentra su proceso
> son fallos distintos, con causas distintas. Contarlos juntos esconde el
> primero, que es el modo de fallo que vació a `ultima_actualizacion`: un campo
> declarado en el esquema que llega vacío. Añadido por
> `sprint-change-proposal-2026-09-03.md`.

### Historia 1.5: Identidad de proveedor normalizada

Como equipo,
quiero agrupar todos los contratos de un mismo proveedor bajo una identidad,
para poder medir concentración y reincidencia.

**Criterios de aceptación:**

**Dado** un documento de proveedor con puntos, guiones o espacios
**Cuando** se normaliza
**Entonces** se reduce a una forma canónica única.

**Dado** el mismo documento con el nombre escrito de formas distintas
**Cuando** se agrupa
**Entonces** queda una sola identidad de Proveedor
**Y** las variantes de nombre quedan registradas y consultables.

### Historia 1.6: Mapeo territorial a DIVIPOLA

Como equipo,
quiero que cada registro tenga código de departamento y municipio,
para poder comparar territorios sin inventar equivalencias.

**Criterios de aceptación:**

**Dado** un texto de departamento o ciudad con tildes, mayúsculas o espacios extra
**Cuando** se normaliza
**Entonces** se resuelve al código DIVIPOLA correcto.

**Dado** un municipio homónimo en dos departamentos
**Cuando** se resuelve con el departamento del registro
**Entonces** se asigna el código correcto para esa combinación.

**Dado** un texto que no corresponde a ninguna entrada de la tabla
**Cuando** se normaliza
**Entonces** queda en la cola de no resueltos
**Y** **no** se asigna ningún código por aproximación.

**Dado** la cola de no resueltos
**Cuando** el equipo agrega una correspondencia
**Entonces** queda registrada con su procedencia y se aplica a los registros pendientes.

### Historia 1.7: Barrido completo periódico

Como equipo,
quiero re-leer el universo cada cierto tiempo,
para que una corrección retroactiva en la fuente no quede invisible para siempre.

> Añadida el 2026-09-02 por `sprint-change-proposal-2026-09-02.md`. Es la mitad que hace
> honesta a la ingesta por ventana: sin ella, lo que se corrige fuera de la ventana no
> se entera nadie.

**Criterios de aceptación:**

**Dado** una programación de barrido
**Cuando** se ejecuta
**Entonces** se recorre el rango histórico completo del dataset
**Y** los registros sin cambios no producen filas nuevas.

**Dado** un barrido que encuentra registros modificados fuera de la ventana diaria
**Cuando** termina
**Entonces** los reporta aparte de los nuevos.

---

## Épica 2: La primera bandera, calibrada

Al terminar, el motor de reglas está probado de punta a punta con una bandera real —oferente único— incluyendo expediente, modo calibración y la prueba de lenguaje. El valor: el equipo puede ver, sobre datos reales, si una regla produce señal o ruido.

### Historia 2.1: Reglas versionadas con umbrales configurables

Como equipo,
quiero definir y modificar reglas y umbrales sin desplegar código,
para poder calibrar en minutos y no en semanas.

**Criterios de aceptación:**

**Dado** una Regla existente
**Cuando** se cambia un umbral
**Entonces** se crea una versión nueva
**Y** la versión anterior se conserva sin modificar.

**Dado** un tope normativo como una cuantía por modalidad
**Cuando** se configura
**Entonces** lleva fecha de vigencia
**Y** no existe ese valor escrito en el código.

**Dado** una Regla
**Cuando** se consulta su estado
**Entonces** es uno de `borrador`, `calibración`, `activa` o `retirada`.

### Historia 2.2: Emisión de alerta con identidad determinista

Como equipo,
quiero que reejecutar un ciclo no duplique alertas,
para poder reprocesar sin ensuciar la cola.

**Criterios de aceptación:**

**Dado** el mismo registro fuente, la misma versión de Regla y los mismos valores disparadores
**Cuando** se evalúa dos veces
**Entonces** se produce una sola Alerta.

**Dado** un cambio de umbral que crea una versión nueva de Regla
**Cuando** se evalúa el mismo registro
**Entonces** se emite una Alerta nueva y distinta de la anterior.

### Historia 2.3: Expediente completo obligatorio

Como equipo,
quiero que ninguna alerta exista sin su sustento,
para poder defender cualquier afirmación meses después.

**Criterios de aceptación:**

**Dado** una Alerta emitida
**Cuando** se consulta su Expediente
**Entonces** contiene identificador del registro fuente, dataset de origen, Regla y versión, umbral aplicado con su valor, valores disparadores concretos, y fecha y hora de consulta a la API.

**Dado** un registro fuente que trae `urlproceso`
**Cuando** se construye el Expediente
**Entonces** incluye ese enlace.

**Dado** un intento de emitir una Alerta con Expediente incompleto
**Cuando** se ejecuta
**Entonces** la emisión falla y la Alerta no se crea.

### Historia 2.4: Bandera de oferente único

Como equipo,
quiero detectar procesos competitivos que terminan con un solo proponente,
para tener la primera señal real corriendo sobre datos.

**Criterios de aceptación:**

**Dado** un proceso con modalidad competitiva
**Cuando** el número de respuestas o proveedores únicos está en o por debajo del umbral
**Entonces** se emite una Alerta de oferente único.

**Dado** un proceso con muchos invitados y muchas visualizaciones pero una sola respuesta
**Cuando** se evalúa
**Entonces** el Expediente registra el embudo completo: invitados, manifestaciones, respuestas, proveedores únicos y ganadores.

**Dado** un proceso de modalidad no competitiva
**Cuando** se evalúa
**Entonces** no se emite Alerta por esta bandera.

### Historia 2.5: Modo calibración sobre un recorte

Como equipo,
quiero probar una regla sobre un pedazo antes de soltarla al país,
para no inundarme de alertas ni quemar la credibilidad de la cuenta.

**Criterios de aceptación:**

**Dado** una Regla en estado `calibración` y un Recorte
**Cuando** se ejecuta
**Entonces** las Alertas producidas no entran a la cola general
**Y** se muestra conteo, distribución y una muestra revisable.

**Dado** un Recorte que no produce Alertas
**Cuando** termina la ejecución
**Entonces** se reporta como recorte sin resultados
**Y** se distingue de un fallo de ingesta.

**Dado** una Regla en `calibración`
**Cuando** se intenta promover a `activa`
**Entonces** requiere una acción explícita del equipo.

**Dado** una Regla en `borrador` que nunca corrió en `calibración`
**Cuando** se intenta promover a `activa`
**Entonces** el sistema lo impide.

### Historia 2.6: Prueba de vocabulario prohibido

Como equipo,
quiero que el sistema falle si aparece lenguaje acusatorio,
para que la regla no se erosione con el tiempo ni con la prisa.

**Criterios de aceptación:**

**Dado** el conjunto de textos de cara al usuario
**Cuando** se ejecuta la prueba
**Entonces** falla si alguno contiene "irregular", "corrupto", "fraude" o "ilegal".

**Dado** una exportación de Alertas
**Cuando** se genera
**Entonces** incluye la nota de que son indicadores estadísticos y no constituyen imputación.

---

## Épica 3: Revisar y medir

Al terminar, el bucle de calibración está cerrado: el equipo revisa alertas, las marca, y ve la tasa de confirmación por regla y versión. Es la épica que produce el activo real del producto — el catálogo calibrado.

### Historia 3.1: Cola de alertas con filtros

Como equipo,
quiero ver las alertas del ciclo ordenadas y filtrables,
para revisar en una hora lo que importa.

**Criterios de aceptación:**

**Dado** un conjunto de Alertas
**Cuando** se abre la cola
**Entonces** se pueden filtrar por Regla, Entidad, departamento y estado de Marca.

**Dado** una Alerta en la cola
**Cuando** se abre
**Entonces** muestra Entidad, Proveedor, valor, Regla que disparó y el enlace del Expediente en una sola vista.

### Historia 3.2: Marcar alertas

Como equipo,
quiero clasificar cada alerta revisada con una razón breve,
para que la calibración se apoye en evidencia y no en memoria.

**Criterios de aceptación:**

**Dado** una Alerta abierta
**Cuando** se marca
**Entonces** queda como `confirmada`, `falso positivo` o `indeterminada`, con autor, fecha y razón.

**Dado** una Alerta ya marcada
**Cuando** se marca de nuevo
**Entonces** se crea una Marca nueva
**Y** la anterior se conserva.

### Historia 3.3: Tasa de confirmación por regla y versión

Como equipo,
quiero ver si una regla mejora o empeora cuando cambio su umbral,
para decidir con datos y no con intuición.

**Criterios de aceptación:**

**Dado** un conjunto de Alertas marcadas de una Regla
**Cuando** se calcula la Tasa de confirmación
**Entonces** el denominador excluye las marcadas `indeterminada`
**Y** el conteo de `indeterminada` se reporta aparte.

**Dado** una Regla con dos versiones
**Cuando** se consulta su desempeño
**Entonces** la Tasa se muestra por versión, no agregada.

### Historia 3.4: Señalización de reglas bajo el piso

Como equipo,
quiero que el sistema me avise cuando una regla está produciendo ruido,
sin que la apague por su cuenta.

**Criterios de aceptación:**

**Dado** un piso de Tasa de confirmación configurado
**Cuando** una Regla cae por debajo
**Entonces** queda señalada para revisión.

**Dado** una Regla señalada
**Cuando** pasa un Ciclo
**Entonces** sigue `activa`
**Y** retirarla requiere una acción humana explícita.

---

## Épica 4: El catálogo completo

Al terminar, las nueve banderas restantes están implementadas y pasaron por calibración. El valor: cobertura real del catálogo, con evidencia de cuáles sobrevivieron.

Cada historia sigue el mismo patrón de aceptación: la bandera emite Alerta cuando se cumple su condición, el Expediente registra los valores concretos que la dispararon, la Regla arranca en `borrador` y solo llega a `activa` tras calibración sobre un Recorte.

### Historia 4.1: Representante legal compartido

Como equipo,
quiero detectar una misma persona representando a varios proveedores adjudicados por la misma entidad,
para encontrar el patrón de sociedades de fachada.

**Criterios de aceptación:**

**Dado** dos o más Proveedores distintos con la misma identificación de representante legal
**Cuando** han sido adjudicados por la misma Entidad dentro de la ventana configurada
**Entonces** se emite Alerta al superar el umbral de coincidencias.

**Dado** los campos de representante legal
**Cuando** se define el esquema
**Entonces** quedan marcados como sensibles conforme a AD-6.

**Dado** una Alerta de esta bandera
**Cuando** se consulta el Expediente
**Entonces** identifica los Proveedores involucrados y el conteo, y los datos de la persona natural quedan sujetos a la marca de sensibilidad.

### Historia 4.2: Adjudicación pegada al presupuesto

Como equipo,
quiero detectar adjudicaciones sospechosamente cercanas al presupuesto oficial,
porque es señal reconocida de información filtrada.

**Criterios de aceptación:**

**Dado** un proceso con `precio_base` y `valor_del_contrato_adjudicado`
**Cuando** la razón entre ambos supera el umbral
**Entonces** se emite Alerta.

**Dado** un proceso sin `precio_base` registrado
**Cuando** se evalúa
**Entonces** no se emite Alerta y el caso se cuenta como no evaluable.

### Historia 4.3: Concentración por proveedor

Como equipo,
quiero detectar proveedores que concentran una porción atípica del gasto de una entidad,
comparando contra entidades parecidas y no contra un número fijo.

**Criterios de aceptación:**

**Dado** el gasto de una Entidad en un periodo
**Cuando** un Proveedor concentra una participación por encima del percentil configurado frente a Entidades comparables
**Entonces** se emite Alerta.

**Dado** una Entidad con muy pocos contratos en el periodo
**Cuando** se evalúa
**Entonces** queda excluida por tamaño de muestra insuficiente.

### Historia 4.4: Concentración por ordenador del gasto

Como equipo,
quiero mover el análisis del nivel entidad al nivel funcionario,
para ver patrones que la agregación por entidad esconde.

**Criterios de aceptación:**

**Dado** contratos con el mismo ordenador del gasto y el mismo Proveedor
**Cuando** la reiteración supera el umbral en la ventana configurada
**Entonces** se emite Alerta.

**Dado** los campos de ordenador del gasto y supervisor
**Cuando** se define el esquema
**Entonces** quedan marcados como sensibles.

### Historia 4.5: Plazo exprés

Como equipo,
quiero detectar procesos adjudicados anormalmente rápido para su modalidad,
porque el afán suele acompañar decisiones tomadas de antemano.

**Criterios de aceptación:**

**Dado** un proceso con fecha de publicación y fecha de adjudicación
**Cuando** los días transcurridos están por debajo del percentil configurado de su modalidad y sector
**Entonces** se emite Alerta.

**Dado** una combinación de modalidad y sector sin datos suficientes para calcular percentil
**Cuando** se evalúa
**Entonces** no se emite Alerta y el caso se cuenta como no evaluable.

### Historia 4.6: Posible fraccionamiento

Como equipo,
quiero detectar contratos partidos para quedar bajo el tope de la siguiente modalidad,
que es el patrón más citado en contratación pública.

**Criterios de aceptación:**

**Dado** varios Contratos del mismo Proveedor y la misma Entidad en una ventana de tiempo
**Cuando** sus objetos son similares por encima del umbral de similitud y cada valor queda bajo el tope de modalidad vigente
**Entonces** se emite una Alerta que agrupa el conjunto.

**Dado** que el tope de modalidad cambió de vigencia
**Cuando** se evalúa un contrato antiguo
**Entonces** se aplica el tope vigente a la fecha del contrato, no el actual.

### Historia 4.7: Desviación entre adjudicado y contratado, y prórroga en tiempo

Como equipo,
quiero recuperar la señal de adiciones que la API no entrega directamente,
usando lo que sí existe.

**Criterios de aceptación:**

**Dado** un proceso con valor adjudicado y su contrato con valor contratado
**Cuando** el delta supera el umbral
**Entonces** se emite Alerta de desviación.

**Dado** un contrato con `dias_adicionados`
**Cuando** la proporción frente a la duración original supera el umbral
**Entonces** se emite Alerta de prórroga.

**Dado** que no existe campo de valor de adición en la fuente
**Cuando** se documenta la Regla
**Entonces** el Expediente deja explícito qué se está midiendo y qué no.

### Historia 4.8: Ejecución anómala

Como equipo,
quiero detectar contratos pagados por encima de lo facturado o sin ejecución,
porque el dinero que ya salió es el más difícil de recuperar.

**Criterios de aceptación:**

**Dado** un contrato donde el valor pagado supera el valor facturado
**Cuando** la diferencia supera el umbral
**Entonces** se emite Alerta.

**Dado** un contrato con pagos registrados y valor pendiente de ejecución cercano al total
**Cuando** se evalúa
**Entonces** se emite Alerta.

---

## Épica 5: Publicar sin quemarse

Al terminar, el equipo puede producir reportes publicables con todos los controles activos. **Bloqueada por el concepto jurídico**: se construye, se prueba, pero no se publica nada hasta tenerlo.

### Historia 5.1: Armado de reporte agregado

Como equipo,
quiero que el sistema arme el borrador de un reporte por patrón,
para publicar el hallazgo y no el señalamiento suelto.

**Criterios de aceptación:**

**Dado** un conjunto de Alertas marcadas `confirmada` de una Regla `activa`
**Cuando** se solicita un Reporte
**Entonces** el borrador se expresa a nivel de Entidad, sector, territorio o periodo, no de caso individual.

**Dado** una solicitud de Reporte sobre un caso individual identificado
**Cuando** se genera
**Entonces** queda marcado como excepción y exige una segunda aprobación.

**Dado** Alertas de una Regla en `calibración`
**Cuando** se intenta armar un Reporte
**Entonces** el sistema lo impide.

### Historia 5.2: Filtro de persona natural bloqueante

Como equipo,
quiero que sea imposible publicar el nombre de una persona natural por descuido,
porque es el error que no tiene vuelta atrás.

**Criterios de aceptación:**

**Dado** un borrador de Reporte
**Cuando** su texto contiene un valor proveniente de una columna marcada como sensible en los registros que lo sustentan
**Entonces** la publicación se bloquea y se nombra el campo detectado.

**Dado** un patrón que solo puede contarse nombrando una persona
**Cuando** se arma el Reporte
**Entonces** se expresa de forma anonimizada por conteo.

**Dado** el filtro
**Cuando** se prueba
**Entonces** la verificación compara contra los valores reales de las columnas marcadas, no contra una lista de palabras.

### Historia 5.3: Compuerta de aprobación estructural

Como equipo,
quiero que el sistema no tenga forma de publicar solo,
para que ninguna prisa pueda saltarse el control.

**Criterios de aceptación:**

**Dado** el componente de publicación
**Cuando** se revisa su acceso
**Entonces** solo puede leer Reportes en estado `aprobado`
**Y** no tiene acceso a Alertas.

**Dado** un Reporte en cualquier estado distinto de `aprobado`
**Cuando** se intenta publicar
**Entonces** la operación no existe como ruta ejecutable.

**Dado** una transición a `aprobado`
**Cuando** ocurre
**Entonces** queda registrada con autor y fecha.

### Historia 5.4: Sustento visible en el reporte

Como equipo,
quiero que cada publicación traiga su respaldo,
para que la discusión sea sobre el caso y no sobre si el sistema es serio.

**Criterios de aceptación:**

**Dado** un Reporte aprobado
**Cuando** se genera el texto final
**Entonces** incluye el enlace público o el dataset y filtro que lo reproduce, y la fecha de consulta.

**Dado** un Reporte
**Cuando** se genera
**Entonces** incluye la nota de indicador estadístico
**Y** pasa la prueba de vocabulario de la historia 2.6.

### Historia 5.5: Registro de publicaciones y rectificación

Como equipo,
quiero poder responder meses después qué afirmé y sobre qué base,
y corregir con la misma visibilidad si me equivoqué.

**Criterios de aceptación:**

**Dado** un Reporte publicado
**Cuando** se consulta el registro
**Entonces** muestra el contenido publicado, las Alertas que lo sustentan, quién aprobó y cuándo.

**Dado** un Reporte que resultó equivocado
**Cuando** se emite una rectificación
**Entonces** queda vinculada al original
**Y** el original queda marcado como rectificado.

---

## Épica 6: Operación desatendida

Al terminar, el sistema corre solo. Es la épica que persigue el criterio de éxito SM-4: treinta días de ciclos consecutivos sin intervención manual.

### Historia 6.1: Ciclo diario programado

Como equipo,
quiero que la ingesta y la evaluación corran solas cada día,
para dedicar mi tiempo a revisar, no a ejecutar.

**Criterios de aceptación:**

**Dado** una programación diaria
**Cuando** llega la hora
**Entonces** se ejecuta ingesta y evaluación de todas las Reglas `activas`.

**Dado** un Ciclo que falla
**Cuando** termina
**Entonces** se notifica al equipo con la causa
**Y** el Ciclo siguiente no se salta por el fallo anterior.

### Historia 6.2: Reporte de ciclo

Como equipo,
quiero ver la salud de cada ciclo de un vistazo,
para detectar un problema de datos antes de que contamine las alertas.

**Criterios de aceptación:**

**Dado** un Ciclo terminado
**Cuando** se consulta su reporte
**Entonces** muestra registros vistos, nuevos, huérfanos, territorios no resueltos, Alertas emitidas por Regla y duración.

**Dado** una variación brusca en el porcentaje de huérfanos o de no resueltos frente al Ciclo anterior
**Cuando** se genera el reporte
**Entonces** se señala como anomalía.

**Dado** la duración de los Ciclos
**Cuando** se acumulan treinta días
**Entonces** se puede evaluar si el Ciclo diario nacional es sostenible o hay que pasar a Recortes rotativos.

### Historia 6.3: Reproceso desde crudo

Como equipo,
quiero reconstruir todo desde los datos crudos cuando cambie la lógica,
porque es lo que hace que una alerta vieja siga siendo defendible.

**Criterios de aceptación:**

**Dado** la capa cruda intacta
**Cuando** se ejecuta un reproceso
**Entonces** se reconstruyen las capas normalizada y derivada sin volver a consultar la API.

**Dado** un reproceso con las mismas versiones de Regla
**Cuando** termina
**Entonces** produce las mismas Alertas con las mismas identidades.
