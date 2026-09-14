---
title: Vigía SECOP
created: 2026-09-02
updated: 2026-09-02
status: draft
---

# PRD: Vigía SECOP

## 0. Propósito del documento

Este PRD traduce el product brief y la investigación técnica de la API en requisitos construibles. Está escrito para el equipo que va a implementar y para los workflows que siguen (arquitectura, épicas e historias). Se apoya en dos documentos previos y no los repite: el brief (`planning-artifacts/briefs/brief-vigia-secop-2026-09-02/`) y la investigación de viabilidad (`planning-artifacts/research/api-secop-viabilidad-2026-09-02.md`), que ya resolvió qué banderas son calculables con los campos reales.

Los supuestos van marcados `[ASSUMPTION]` en línea e indexados al final. El vocabulario del glosario es obligatorio: las historias y el código usan esos términos, sin sinónimos.

## 1. Visión

Vigía SECOP convierte el archivo de contratación pública colombiana en un flujo corto de casos que valen la pena mirar. Consume los datos abiertos del SECOP, los normaliza, les aplica un catálogo de reglas con umbrales calibrados y emite alertas trazables.

La v1 no es un producto de cara al público: es el instrumento con el que el equipo descubre qué reglas funcionan. La pregunta que debe responder no es "¿podemos detectar patrones?" sino "¿de cada cien alertas, cuántas resisten revisión humana?". Todo el diseño está subordinado a poder responder eso con evidencia.

Nada de lo que produce el sistema afirma que exista una irregularidad. Señala que un registro se aparta del comportamiento esperado, dice con qué criterio, y enlaza al expediente público para que un humano decida.

## 2. Usuario objetivo

### 2.1 Jobs to be done

- Ver, sobre datos reales, si una regla propuesta produce señal o ruido, antes de invertir en ella.
- Ajustar el umbral de una regla y observar de inmediato cómo cambia su tasa de confirmación.
- Revisar una alerta y llegar al documento fuente en un clic, sin reconstruir la consulta a mano.
- Sostener una afirmación frente a un tercero: qué regla, qué umbral, qué registro, qué fecha.
- Acumular serie histórica para poder decir "esto viene repitiéndose", no solo "esto es raro hoy".

### 2.2 No usuarios, y la audiencia pública

**No usuarios del sistema (v1):** periodistas, veedurías y entes de control. Nadie fuera del equipo opera el sistema, consulta su cola ni ajusta sus reglas.

**Audiencia pública:** existe desde la v1, pero como **lectora de reportes publicados**, no como usuaria. El canal es una cuenta de X operada por el equipo. Esto no relaja la regla anterior — la endurece: publicar convierte cada falso positivo en un error visible y no retractable. La condición sigue siendo la misma, con más razón: nada se publica antes de que la Regla que lo produjo tenga Tasa de confirmación aceptable.

El modelo de negocio no es la venta. Es la credibilidad: reportes públicos sostenidos que generen interés entrante. Eso significa que **la reputación de la cuenta es el activo comercial**, y una publicación errónea lo destruye más rápido de lo que veinte correctas lo construyen.

### 2.3 Recorridos de usuario

- **UJ-1. Guillermo calibra una regla nueva antes de soltarla al país.**
  - **Persona y contexto:** Guillermo acaba de agregar la bandera de representante legal compartido. No sabe si dispara diez alertas o diez mil.
  - **Estado de entrada:** ingesta corriendo, catálogo cargado, regla en estado `borrador`.
  - **Recorrido:** activa la regla en modo calibración sobre un recorte —un departamento, un año—; el sistema la corre solo ahí; ve el conteo de alertas y una muestra; ajusta el umbral de coincidencias mínimas y vuelve a correr.
  - **Clímax:** el conteo baja a un volumen revisable y la muestra deja de estar dominada por casos obvios y explicables.
  - **Resolución:** promueve la regla a `activa`; a partir de ahí corre sobre el universo nacional.
  - **Caso borde:** si el recorte devuelve cero alertas, el sistema lo distingue de un fallo de ingesta y lo dice, en vez de mostrar una lista vacía ambigua.

- **UJ-2. Ana revisa la cola y marca lo que no sirve.**
  - **Persona y contexto:** Ana, del equipo, tiene una hora para revisar la cola del día.
  - **Estado de entrada:** alertas del último ciclo, ordenadas por prioridad.
  - **Recorrido:** abre la alerta de mayor prioridad; ve la entidad, el proveedor, el valor y la regla que disparó; abre `urlproceso` en otra pestaña; confirma que la justificación es legítima.
  - **Clímax:** la marca como falso positivo con una razón de una línea.
  - **Resolución:** la tasa de confirmación de esa regla se actualiza; si cae bajo el piso definido, la regla queda señalada para revisión.

- **UJ-3. Guillermo necesita sustentar un hallazgo frente a alguien de afuera.**
  - **Persona y contexto:** alguien cuestiona una alerta.
  - **Recorrido:** abre el expediente de la alerta y obtiene, en un solo lugar, el identificador del registro, la regla con su versión, el umbral aplicado, la fecha de consulta y el enlace público.
  - **Clímax:** puede reproducir la alerta con esos datos, sin depender de su memoria.
  - **Resolución:** la conversación pasa a ser sobre el caso, no sobre si el sistema es confiable.

- **UJ-4. Guillermo publica el reporte de la semana sin exponerse.**
  - **Persona y contexto:** Guillermo quiere alimentar la cuenta de X con algo sólido y sostenible.
  - **Estado de entrada:** varias Alertas de la semana marcadas `confirmada`, todas de Reglas con Tasa de confirmación por encima del piso.
  - **Recorrido:** pide un Reporte agregado —oferente único por departamento en el último trimestre—; el sistema arma el borrador con la cifra, el método, el enlace a la consulta reproducible y la nota de indicador; él revisa el texto; el sistema bloquea la publicación si detecta un nombre de persona natural.
  - **Clímax:** aprueba, publica, y el Reporte queda registrado con las Alertas que lo sustentan y la fecha.
  - **Resolución:** si alguien lo cuestiona, puede mostrar exactamente qué afirmó, sobre qué datos y con qué método.
  - **Caso borde:** si el Reporte resulta equivocado, el procedimiento de rectificación publica la corrección con la misma visibilidad.

## 3. Glosario

- **Proceso** — Un procedimiento de contratación publicado en el SECOP, adjudicado o no. Un Proceso puede derivar en cero o más Contratos. ~~Grano del dataset `p6dx-8zbt`.~~ **Corregido el 2026-09-03:** el grano de `p6dx-8zbt` NO es el Proceso sino la **adjudicación** — un Proceso con varios lotes o varios adjudicatarios aparece en tantas filas como adjudicaciones tenga. Medido: `id_del_proceso = CO1.REQ.10772032` devuelve **21 filas**, idénticas en todo lo procedimental y distintas en proveedor y valor adjudicado. La mayoría de Procesos trae una sola fila porque tiene una sola adjudicación, y eso es lo que hacía invisible la diferencia. Consecuencia: `id_del_proceso` **no es llave primaria** del dataset, y contar filas de `p6dx-8zbt` no es contar Procesos. Ver `sprint-change-proposal-2026-09-03.md`.
- **Contrato** — Un contrato firmado y publicado. Grano del dataset `jbjy-vk9h`. Pertenece a un Proceso.
- **Entidad** — Organismo público que contrata. Identificada por NIT de entidad.
- **Proveedor** — Persona natural o jurídica adjudicataria. Identificada por documento de proveedor.
- **Bandera** — Definición conceptual de un patrón atípico. Ejemplo: "oferente único".
- **Regla** — Implementación ejecutable y versionada de una Bandera, con sus umbrales. Una Bandera tiene una o más Reglas a lo largo del tiempo.
- **Umbral** — Parámetro configurable de una Regla que determina cuándo dispara. Tiene fecha de vigencia.
- **Alerta** — Resultado de que una Regla dispare sobre un Proceso o Contrato. Unidad de trabajo del revisor.
- **Expediente** — Conjunto de datos de trazabilidad adjunto a una Alerta: registro fuente, Regla y versión, Umbral aplicado, fecha de consulta, enlace público.
- **Marca** — Clasificación humana de una Alerta: `confirmada`, `falso positivo` o `indeterminada`.
- **Tasa de confirmación** — Alertas marcadas `confirmada` sobre el total de Alertas marcadas de una Regla. Excluye las `indeterminada` del denominador.
- **Modo calibración** — Estado en que una Regla corre solo sobre un Recorte, sin emitir a la cola general.
- **Recorte** — Subconjunto acotado del universo por departamento, sector, modalidad o periodo.
- **Ciclo** — Una ejecución completa de ingesta más evaluación de Reglas activas.
- **Reporte** — Pieza publicable derivada de una o más Alertas marcadas `confirmada`. Puede ser agregado (por defecto) o individual (por excepción). Requiere aprobación humana antes de publicarse.
- **Audiencia** — Lectores del canal público. No operan el sistema ni acceden a la cola de Alertas.

## 4. Funcionalidades

### 4.1 Ingesta y normalización

**Descripción.** El sistema consulta periódicamente los datasets del SECOP vía API Socrata, incorpora solo lo nuevo o modificado, y deja los registros en un esquema unificado sobre el que las Reglas puedan operar sin conocer las particularidades de cada fuente. Realiza UJ-1, UJ-2.

#### FR-1: Ingesta incremental

El sistema puede incorporar Procesos y Contratos nuevos o actualizados desde la API sin reprocesar el histórico completo.

**Consecuencias (verificables):**
- Un Ciclo que no encuentra registros nuevos termina sin error y lo registra como Ciclo vacío, distinguible de un fallo.
- La ingesta avanza sobre la fecha del hecho —`fecha_de_firma` en Contratos, `fecha_de_publicacion_del` en Procesos— y re-lee una ventana de solapamiento configurable hacia atrás, porque el SECOP publica con retraso. Un barrido completo periódico recoge las correcciones retroactivas. `[ASSUMPTION-1]`
- Un registro reingerido con los mismos datos no genera duplicado ni Alerta repetida.
- Un fallo de red a mitad de Ciclo deja el estado consistente: o el lote entró completo, o no entró.

#### FR-2: Esquema unificado y llave de cruce

El sistema puede relacionar un Contrato con el Proceso que lo originó.

**Consecuencias:**
- Existe una llave de cruce entre `proceso_de_compra` (Contratos) e `id_del_portafolio` (Procesos). Ambos son identificadores del espacio `CO1.BDOS.`. **No** se cruza contra `id_del_proceso`, que es del espacio `CO1.REQ.` y no comparte valores con ninguna columna de Contratos. `[ASSUMPTION-2]`
- Los registros sin correspondencia quedan marcados como huérfanos y son consultables, no descartados en silencio.
- El porcentaje de huérfanos se reporta por Ciclo; una variación brusca es señal de cambio de esquema en la fuente.

**Fuera de alcance:** SECOP I y TVEC. Entran en v2; el esquema debe admitirlos sin rediseño.

#### FR-3: Normalización territorial

El sistema puede asignar código DIVIPOLA de departamento y municipio a cada Proceso y Contrato.

**Consecuencias:**
- La fuente es texto libre (`departamento`, `ciudad`, `departamento_entidad`, `ciudad_entidad`), no código. El mapeo es responsabilidad del sistema.
- La normalización resuelve tildes, mayúsculas, espacios y variantes de escritura.
- Los valores que no mapean quedan en una lista de no resueltos, revisable y corregible. **Nunca se asignan por aproximación silenciosa.**
- Existe un conjunto de pruebas con casos reales de variantes de escritura, incluidos municipios homónimos en departamentos distintos.

#### FR-4: Identidad de Proveedor

El sistema puede agrupar Contratos y Procesos por el mismo Proveedor.

**Consecuencias:**
- La llave primaria es `documento_proveedor` / `nit_del_proveedor_ganador`, normalizada (sin puntos, guiones ni dígito de verificación inconsistente).
- Un mismo documento con nombres escritos distinto se agrupa como un solo Proveedor, y las variantes de nombre quedan registradas.

### 4.2 Motor de Reglas

**Descripción.** Las Reglas son explícitas, versionadas y con umbrales configurables. No hay modelos opacos en v1: una Alerta que no se puede explicar no se puede defender. Realiza UJ-1, UJ-3.

#### FR-5: Reglas versionadas con umbrales configurables

El equipo puede definir y modificar Reglas y sus Umbrales sin desplegar código.

**Consecuencias:**
- Cambiar un Umbral crea una versión nueva de la Regla; las Alertas previas conservan la versión con que fueron emitidas.
- Los topes normativos (cuantías por modalidad, límites de adición) son configuración con fecha de vigencia, nunca constantes en código.
- Una Regla tiene estado: `borrador`, `calibración`, `activa`, `retirada`.

#### FR-6: Catálogo de Banderas de la v1

El sistema evalúa las Banderas confirmadas como calculables por la investigación técnica.

**Consecuencias — Banderas incluidas:**
- **Oferente único**, con el embudo completo: invitados, manifestaciones, respuestas, proveedores únicos y ganadores.
- **Representante legal compartido**: misma identificación de representante legal en Proveedores distintos adjudicados por la misma Entidad.
- **Adjudicación pegada al presupuesto**: razón entre valor adjudicado y `precio_base` por encima del umbral.
- **Concentración por Proveedor**: participación atípica de un Proveedor en el gasto de una Entidad frente a Entidades comparables.
- **Concentración por ordenador del gasto**: mismo ordenador y mismo Proveedor de forma reiterada.
- **Plazo exprés**: días entre publicación y adjudicación por debajo del percentil bajo de su modalidad y sector.
- **Posible fraccionamiento**: Contratos de objeto similar, mismo Proveedor, fechas cercanas, cada uno bajo el tope de la siguiente modalidad.
- **Desviación entre adjudicado y contratado**: delta entre `valor_del_contrato_adjudicado` y `valor_del_contrato`.
- **Prórroga en tiempo**: `dias_adicionados` frente a la duración original.
- **Ejecución anómala**: pagado que supera lo facturado, o pagado sin ejecución.

**Fuera de alcance:** *Contratista reciente* — requiere RUES, no disponible en las fuentes de v1. *Anomalía territorial per cápita* — depende de FR-3 estabilizado y de proyecciones DANE; queda para después de la primera calibración.

#### FR-7: Modo calibración

El equipo puede correr una Regla sobre un Recorte sin que sus Alertas entren a la cola general.

**Consecuencias:**
- Una Regla en `calibración` produce conteo, distribución y muestra revisable.
- Promover a `activa` requiere una acción explícita, nunca es automático.
- Un Recorte vacío se reporta como tal y se distingue de un fallo de ingesta.
- **Ninguna Regla pasa a `activa` sin haber sido calibrada sobre un Recorte.** Es la mitigación acordada al alcance nacional.

### 4.3 Alerta y Expediente

**Descripción.** Cada Alerta nace con su sustento. La trazabilidad no es una función aparte: es parte de la definición de Alerta. Realiza UJ-2, UJ-3.

#### FR-8: Expediente de trazabilidad

Toda Alerta puede mostrar el sustento completo de por qué existe.

**Consecuencias — el Expediente incluye siempre:**
- Identificador del registro fuente y dataset de origen.
- Regla y versión, con el Umbral aplicado y su valor.
- Los valores concretos que dispararon la Regla.
- Fecha y hora de la consulta a la API.
- `urlproceso` cuando el registro lo trae, como enlace al expediente público.
- Una Alerta sin Expediente completo no se emite.

#### FR-9: Lenguaje del producto

Toda superficie que un humano lea usa lenguaje de indicador, no de acusación.

**Consecuencias:**
- Los textos dicen "patrón atípico que amerita revisión". Los términos "irregular", "corrupto", "fraude", "ilegal" no aparecen en ninguna cadena de la interfaz, exportación o notificación.
- Existe una prueba automatizada que falla si alguno de esos términos aparece en textos de cara al usuario.
- Toda exportación lleva la nota de que las alertas son indicadores estadísticos y no constituyen imputación.

### 4.4 Revisión y calibración

**Descripción.** El bucle que produce el activo real del producto: el catálogo calibrado. Realiza UJ-2.

#### FR-10: Marcar Alertas

Un revisor puede marcar una Alerta como `confirmada`, `falso positivo` o `indeterminada`, con una razón breve.

**Consecuencias:**
- La Marca queda con autor y fecha; las Marcas no se sobrescriben, se versionan.
- Se puede filtrar la cola por Regla, Entidad, departamento y estado de Marca.

#### FR-11: Tasa de confirmación por Regla

El sistema calcula y muestra la Tasa de confirmación de cada Regla y versión.

**Consecuencias:**
- Se calcula sobre Alertas marcadas; las `indeterminada` se excluyen del denominador y se reportan aparte.
- Se muestra por versión de Regla, para poder ver si un cambio de Umbral mejoró o empeoró.
- Una Regla cuya Tasa cae bajo el piso configurado queda señalada para revisión. `[ASSUMPTION-3]`
- La señalización **no** desactiva la Regla automáticamente; retirar una Regla es decisión humana.

### 4.5 Publicación

**Descripción.** El canal público es una cuenta de X operada por el equipo. Un Reporte es una pieza publicable derivada de una o más Alertas ya revisadas. Esta funcionalidad es la que convierte al sistema en un actor público, y por eso es la que más restricciones lleva: la asimetría es brutal — una publicación equivocada cuesta mucho más de lo que aporta una acertada. Realiza UJ-4.

#### FR-12: Compuerta humana obligatoria

Ninguna Alerta se publica de forma automática.

**Consecuencias:**
- Publicar exige aprobación explícita de un humano sobre una Alerta ya marcada `confirmada`.
- El sistema **no tiene** capacidad técnica de publicar sin esa aprobación. No es una política operativa que se pueda saltar con prisa: es una restricción de diseño.
- Una Alerta cuya Regla esté en `calibración` no es publicable, ni siquiera con aprobación.

#### FR-13: Agregado por defecto, individual por excepción

El formato por defecto de un Reporte es el patrón agregado, no el señalamiento de un caso.

**Consecuencias:**
- Los Reportes por defecto se expresan a nivel de Entidad, sector, territorio o periodo: cuántos procesos con oferente único, qué proporción del gasto concentra un solo Proveedor, cómo se compara un municipio con sus pares.
- Publicar un caso individual identificado requiere una segunda aprobación y queda registrado como excepción.
- Un agregado es más difícil de refutar, más difícil de convertir en difamación, y periodísticamente más valioso que un contrato suelto.

#### FR-14: Ninguna persona natural identificada

Los Reportes publicados no nombran personas naturales.

**Consecuencias:**
- Representantes legales, ordenadores del gasto y supervisores se usan **dentro** del motor de reglas, pero sus nombres e identificaciones nunca salen en una publicación.
- Las Entidades públicas y las empresas sí pueden nombrarse: son sujetos de escrutinio público. Una persona natural, no — no sin concepto jurídico previo.
- Un patrón que solo se puede contar nombrando a una persona se publica de forma anonimizada ("un mismo representante legal figura en N proveedores adjudicados por la misma entidad") o no se publica.
- Existe una verificación automática que bloquea la publicación si el texto contiene un nombre o identificación proveniente de los campos de persona natural.

#### FR-15: Sustento visible en cada Reporte

Todo Reporte publicado enlaza a su fuente.

**Consecuencias:**
- Incluye el enlace público (`urlproceso` o el dataset y filtro que lo reproduce) y la fecha de consulta.
- Incluye la nota de que se trata de un indicador estadístico y no de una imputación.
- Aplica FR-9: el lenguaje del Reporte pasa la misma prueba de vocabulario que el resto del producto.

#### FR-16: Registro de publicaciones y rectificación

El sistema conserva el rastro de todo lo publicado y permite corregirlo.

**Consecuencias:**
- Cada Reporte publicado queda registrado con su contenido, las Alertas que lo sustentan, quién aprobó y cuándo.
- Existe un procedimiento definido de rectificación: si un Reporte resulta equivocado, se publica la corrección con la misma visibilidad que el original.
- El registro permite responder, meses después, exactamente qué se afirmó y sobre qué base.

**Fuera de alcance:** automatización de la publicación vía API de X. En v1 la publicación es manual desde el borrador que genera el sistema. `[ASSUMPTION-6]`

## 5. Requisitos no funcionales

**Reproducibilidad.** Dado un Expediente, cualquiera del equipo puede reconstruir la Alerta. Es el requisito que sostiene la defendibilidad del producto.

**Datos personales.** El catálogo usa nombres e identificaciones de personas naturales — representantes legales, ordenadores del gasto, supervisores. Son datos personales bajo el régimen colombiano de habeas data, aunque provengan de fuente pública. `[ASSUMPTION-4]` En consecuencia: acceso restringido al equipo, y **nunca en publicaciones** (FR-14). La decisión de publicar convierte esta revisión jurídica en bloqueante, no en pendiente: debe estar hecha antes del primer Reporte, no antes de un hipotético comprador.

**Riesgo reputacional y legal de publicar.** Publicar señalamientos sobre Entidades y Proveedores identificados expone al equipo a acciones legales y a la pérdida del activo principal, que es la credibilidad de la cuenta. Los controles no son opcionales ni tuneables: compuerta humana (FR-12), agregado por defecto (FR-13), sin personas naturales (FR-14), sustento visible (FR-15) y rectificación registrada (FR-16). Si alguno estorba, la respuesta correcta es no publicar esa pieza, no relajar el control.

**Resiliencia de la fuente.** El esquema de los datasets puede cambiar sin aviso. La ingesta valida que los campos esperados existan y falla ruidosamente si no, en vez de producir nulos silenciosos.

**Retención.** Los registros ingeridos se conservan históricamente. La serie es el activo; no se sobrescribe con la foto más reciente.

**Costo de ingesta.** El universo nacional es grande. La ingesta incremental debe completar un Ciclo diario sin intervención manual. `[ASSUMPTION-5]` El costo de un Ciclo incluye la ventana de solapamiento, no solo lo nuevo; el barrido completo periódico se programa fuera de la ventana diaria.

## 6. Criterios de éxito

- **SM-1.** Tasa de confirmación agregada del catálogo activo por encima del piso definido, medida sobre al menos cien Alertas marcadas.
- **SM-2.** Al menos seis Banderas del catálogo llegan a estado `activa` tras calibración. Que varias se descarten es resultado esperado, no fallo.
- **SM-3.** Tiempo mediano de revisión de una Alerta menor al de buscar el caso a mano.
- **SM-4.** Treinta días de Ciclos diarios consecutivos sin intervención manual.
- **SM-5.** Cero Alertas emitidas sin Expediente completo.

## 7. Fuera de alcance de la v1

Cuentas de usuario y permisos diferenciados. Notificaciones a terceros. Acceso externo a la cola de Alertas. Publicación automatizada vía API de X. SECOP I y TVEC. Cruces con RUES, sanciones, inhabilidades o datos societarios. Modelos de aprendizaje automático. API pública del producto.

*(La publicación de Reportes salió de esta lista: entró a la v1 en §4.5, con restricciones.)*

## 8. Índice de supuestos

| ID | Supuesto | Cómo se resuelve |
|---|---|---|
| ASSUMPTION-1 | ~~`ultima_actualizacion` es confiable como marca de agua~~ **Refutado el 2026-09-02.** Viene vacío en ~40% de los contratos y en la totalidad de los más recientes; `:updated_at` tampoco sirve porque la fuente recarga el dataset completo. Sustituido por: la fecha del hecho más una ventana de solapamiento es marca de agua suficiente | Medido contra la API. Ver `sprint-change-proposal-2026-09-02.md`. Queda por fijar el tamaño de la ventana contra el retraso real de publicación |
| ASSUMPTION-2 | ~~`proceso_de_compra` e `id_del_proceso` cruzan de forma fiable~~ **Corregido el 2026-09-03:** la llave es `proceso_de_compra` ↔ `id_del_portafolio`; `id_del_proceso` está en otro espacio de nombres (`CO1.REQ.`) y no cruza nunca. Sigue abierto **cuánto** cruza | Llave verificada contra la API, 5 de 5, y confirmada de forma independiente por `referencia_del_proceso`. Ver `sprint-change-proposal-2026-09-03.md`. El porcentaje de huérfanos lo mide la 1.4 sobre la ingesta real |
| ASSUMPTION-3 | Existe un piso único de Tasa de confirmación para todas las Reglas | Puede requerir pisos distintos por Bandera; decidir tras la primera calibración |
| ASSUMPTION-4 | El uso de datos personales de fuente pública exige control de acceso | Revisión jurídica antes de abrir a terceros |
| ASSUMPTION-5 | Un Ciclo diario sobre el universo nacional es viable en costo y tiempo | Medir en la primera ingesta completa; si no, pasar a Ciclo por Recorte rotativo |
| ASSUMPTION-6 | Publicación manual es suficiente en v1; no hace falta la API de X | Revisar si la cadencia de publicación se vuelve un cuello de botella |
| ASSUMPTION-7 | Nombrar Entidades y Proveedores en Reportes agregados es defendible; nombrar personas naturales no | Concepto jurídico antes del primer Reporte |

## 9. Estado de las preguntas abiertas

**Resuelto — el modelo de negocio.** No hay comprador y no se busca uno. El producto es de uso propio y el canal público es una cuenta de X con reportes periódicos. La monetización, si llega, es entrante: alguien ve el trabajo y se interesa. Esto es coherente y tiene precedentes, pero traslada el riesgo: el activo deja de ser el software y pasa a ser la credibilidad de la cuenta.

**Resuelto — la calibración.** Confirmado por el CEO: ninguna Regla pasa a `activa` a nivel nacional sin calibración previa sobre un Recorte.

**Abierto — el concepto jurídico.** Es ahora la única dependencia bloqueante antes del primer Reporte publicado. Cubre dos preguntas: qué se puede afirmar públicamente sobre una Entidad o un Proveedor identificado a partir de datos abiertos, y qué exposición genera el uso interno de datos de personas naturales.

**Abierto — el piso de Tasa de confirmación para publicar.** Debería ser más alto que el piso para mantener una Regla activa internamente. Publicar tiene un costo de error mucho mayor que revisar.
