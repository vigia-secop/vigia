# Trabajo diferido

Hallazgos reales que la revisión de una historia identificó y que no
corresponden a esa historia. Append-only: no se editan ni se borran entradas.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: La ingesta no tiene reintento ni espera ante 429, 503 o el 202 con que Socrata responde a una consulta en curso; un hipo de red aborta el Ciclo entero.
  evidence: La spec de la 1.1 prohíbe explícitamente reintentos y espera exponencial porque reanudar es de la 1.2. Sigue siendo necesario para el Ciclo diario desatendido que exige SM-4.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: La paginación por `$offset` no es estable frente a escrituras en la fuente durante un recorrido largo; la paginación por llave (`:id` mayor que el último visto) lo resuelve y evita el costo del offset profundo.
  evidence: `$order=:id` elimina el desorden implícito, pero no el corrimiento por filas insertadas a mitad del recorrido. Cambiar la estrategia de cursor está en «Ask First» de la spec y encaja naturalmente con la marca de agua de la 1.2.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: No hay control de versiones de esquema: un solo archivo SQL montado en el arranque del contenedor, sin tabla de migraciones aplicadas ni herramienta que detecte una base a medio migrar.
  evidence: El README ya documenta el parche manual con `psql` para volúmenes existentes. Con la segunda migración deja de ser sostenible.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: La invariante de solo inserción de la capa cruda está documentada pero no impuesta: la aplicación se conecta con el rol dueño de la tabla, que puede hacer UPDATE, DELETE y DDL.
  evidence: AD-1 dice que el crudo nunca se modifica. Un rol de aplicación con solo INSERT y SELECT convierte esa invariante en una garantía del motor, como ya se hizo con la idempotencia.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: No hay integración continua ni verificador estático; el código está anotado de punta a punta y usa Protocol, pero nada comprueba los tipos ni corre `pytest -m postgres` automáticamente.
  evidence: Las pruebas de integración se omiten por defecto, así que sin CI que las corra contra una base real la garantía de durabilidad solo se verifica cuando alguien se acuerda.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: `ResumenCiclo` se imprime y se descarta: no hay tabla de Ciclos ni columna que ligue cada fila cruda al Ciclo que la trajo.
  evidence: AD-4 exige que cada Ciclo registre cursor de entrada y salida, registros vistos, nuevos, huérfanos y errores. Es el corazón de la historia 1.2, pero conviene que la 1.2 sepa que la 1.1 dejó ese hueco a propósito.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-validacion-de-esquema.md`
  summary: No hay forma de leer `esquema_novedad`: la migración crea un índice pensado para «qué falta por mirar» y nada en el repositorio hace esa consulta.
  evidence: Las novedades se escriben y quedan inaccesibles sin SQL a mano. Falta un comando que las liste y permita marcarlas revisadas.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-validacion-de-esquema.md`
  summary: El esquema se valida una sola vez, al arrancar el Ciclo; una ingesta larga no se entera si la fuente cambia a mitad del recorrido.
  evidence: Con Ciclos diarios de horas (épica 6) el cambio se detectaría un día tarde. Revalidar cada N páginas es barato.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-validacion-de-esquema.md`
  summary: Una avalancha de campos nuevos (decenas de golpe) pasa como si nada e inunda `esquema_novedad`.
  evidence: Un cambio masivo de esquema es tan significativo como un campo que desaparece, pero hoy no detiene nada ni se distingue de una novedad aislada.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-validacion-de-esquema.md`
  summary: La corrida abre dos conexiones al mismo DSN, una por cada repositorio, sin necesidad.
  evidence: Mismo destino y mismo ciclo de vida en el ExitStack. Compartir la conexión es trivial y reduce a la mitad las conexiones por Ciclo.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-validacion-de-esquema.md`
  summary: `procesos` sigue sin esquema capturado, así que cualquier ingesta de ese dataset aborta con código 2.
  evidence: Bloqueado por límite de tasa de la API el 2026-09-02. Se resuelve corriendo `python -m vigia.schema --capturar --dataset procesos` y revisando el archivo.

- source_spec: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-02.md`
  summary: La validación de esquema comprueba que un campo esté declarado, no que venga poblado; `ultima_actualizacion` la habría pasado mientras estaba vacío en el 100% de los registros recientes.
  evidence: Medido el 2026-09-02. Falta medir por Ciclo la cobertura de cada campo del que dependan reglas o cursores, y alertar cuando se desplome. Es la versión de «falla ruidosamente» para un campo que se vacía en vez de desaparecer.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-marca-de-agua.md`
  summary: No existe un estado `en_curso`: un proceso muerto por SIGKILL, OOM o corte de luz no deja ninguna fila en `ciclo`, que es justo el escenario que el diseño dice evitar.
  evidence: `ejecutar_ciclo` solo escribe al terminar. Un registro de apertura, o un tercer estado, cierra el hueco. Encaja con la 6.1 (Ciclo diario programado), donde importa de verdad.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-marca-de-agua.md`
  summary: Nada impide que dos Ciclos del mismo dataset corran a la vez; con cron, dos ejecuciones encimadas son el caso normal cuando un Ciclo tarda más que su intervalo.
  evidence: Sin `pg_advisory_lock` ni índice único sobre un Ciclo en curso, el resultado es trabajo duplicado y una marca que salta según cuál termine último. Es de la 6.1.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-marca-de-agua.md`
  summary: No hay comando para inspeccionar ni corregir la marca de agua; si queda mal, la única cura es UPDATE a mano sobre `ingesta_marca`.
  evidence: El `--hasta` futuro ya se rechaza, pero cualquier otra vía de corrupción deja al operador sin herramienta.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-marca-de-agua.md`
  summary: Falta medir qué proporción de contratos carece de `fecha_de_firma`; esos registros son invisibles para todo Ciclo incremental, para siempre.
  evidence: La consulta filtra sobre ese mismo campo y SoQL descarta los nulos. Es la misma medición que refutó `ultima_actualizacion`, aplicada al campo que lo reemplazó.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-validacion-de-esquema.md`
  summary: La suite se escribió y se verificó solo en Linux; una llamada a `os.geteuid()` en un decorador rompía la importación del módulo entero en Windows, que es la máquina real del equipo.
  evidence: Detectado el 2026-09-02 al correr la suite por primera vez en Windows. Corregido, pero nada impide que vuelva a pasar: falta CI que corra la suite en Windows además de Linux, o al menos una comprobación de que ningún módulo de prueba usa APIs exclusivas de POSIX en tiempo de importación.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-validacion-de-esquema.md`
  summary: `capturado_en` se sellaba en UTC y la prueba lo comparaba contra la fecha del sistema; en una máquina en UTC las dos coinciden siempre y el desajuste era invisible.
  evidence: Detectado el 2026-09-02 al correr en Windows con hora de Colombia (UTC-5) a las 8 p.m., cuando en UTC ya era el día siguiente. Corregido: la captura usa hora de Colombia y la prueba compara contra el mismo reloj. Falta una revisión general de que ninguna prueba compare un valor calculado con una zona contra otro calculado con otra.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-marca-de-agua.md`
  summary: En régimen estable el Ciclo relee los últimos 30 días en cada corrida, no un incremento: `--hasta` es hoy y la marca queda en `hasta`, así que la ventana hace todo el trabajo.
  evidence: Medido el 2026-09-02 contra la fuente real. Es correcto por idempotencia, pero el costo en peticiones de un Ciclo diario nacional es el de 30 días, no el de un día. Es exactamente lo que `ASSUMPTION-5` manda medir antes de optimizar. Alternativas si duele: acotar `--hasta` a la fecha de hecho máxima disponible en la fuente, o estrechar la ventana con la evidencia de `en_borde_de_ventana`.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-marca-de-agua.md`
  summary: Confirmado contra la fuente: existen contratos con `fecha_de_firma` nula, y ordenando por ese campo salen de primeros.
  evidence: Medido el 2026-09-02: `$order=fecha_de_firma DESC` devuelve filas sin la clave. Esos contratos son invisibles para todo Ciclo incremental porque la consulta filtra sobre ese mismo campo. Falta medir qué proporción del universo son y decidir si se recogen por otra vía (por ejemplo un barrido sin filtro de fecha en la historia 1.7).

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: El proyecto exigía virtualización por hardware para poder correr sus propias pruebas de integración: la única forma documentada de conseguir una base era Docker Desktop, que en Windows no arranca sin VT-x/SVM habilitado en la BIOS.
  evidence: Detectado el 2026-09-03 en la máquina real del equipo: Docker Desktop reportó «Virtualization support not detected» y «Engine stopped». Corregido: `probar.ps1` prefiere un PostgreSQL instalado en la máquina y usa Docker solo si está; el README documenta la instalación nativa como camino principal. Queda la lección general: una dependencia de desarrollo que exige tocar la BIOS es una barrera de entrada, no un detalle de configuración, y no se descubre hasta que alguien corre el proyecto en una máquina que no es la del autor.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: Falta medir cuánto pesa la capa cruda por cada mil contratos ingeridos, y no hay decisión de dónde vivirá la base cuando el Ciclo diario deje de correr en una máquina de escritorio.
  evidence: Surgió el 2026-09-03 al evaluar Amazon RDS. Es de solo inserción y guarda el JSONB completo de 85 campos, así que crece de forma monótona: cualquier hospedaje con tope de almacenamiento (el free tier de RDS son 20 GB) se topa, y sin la medición no se sabe cuándo. Es la evidencia que necesita la 6.1 para elegir hospedaje en vez de adivinarlo.

- source_spec: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-03.md`
  summary: El `noticeUID` (`CO1.NTC.`) aparece dentro de `urlproceso` en los dos datasets y es una segunda vía de cruce, independiente de `id_del_portafolio`.
  evidence: Medido el 2026-09-03. Se descartó como llave principal por frágil —hay que sacarla de una URL anidada en `{"url": "..."}` con una expresión regular—, pero sirve como verificación cruzada barata cuando el cruce principal falle: dos llaves independientes que discrepan dicen algo que una sola no puede decir.

- source_spec: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-03.md`
  summary: Procesos tiene siete campos de fecha (`fecha_de_publicacion_del`, `fecha_de_publicacion`, `fecha_de_ultima_publicaci` y cuatro `fecha_de_publicacion_fase*`) y `datasets.py` eligió el primero sin justificarlo.
  evidence: Detectado el 2026-09-03 al leer una fila completa de `p6dx-8zbt`. Para Contratos se decidió `fecha_de_firma` con criterio explícito; para Procesos se heredó un nombre. Falta decidir cuál es «la fecha del hecho» de un Proceso y escribir por qué, antes de que un Ciclo incremental de ese dataset dependa de la elección.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-marca-de-agua.md`
  summary: El retraso de publicación del SECOP no es constante: la fuente publica a saltos. Medido el 2026-09-02, una ventana de 7 días devolvía cero filas; el 2026-09-03, la misma consulta devolvió 24 685 contratos.
  evidence: Dos mediciones consecutivas contra la fuente real desde la máquina del equipo. Invalida la lectura de ayer, que trató nueve días como si fuera el retraso característico. Consecuencia para calibrar la ventana: el número que importa no es el retraso promedio sino el salto máximo entre recargas, y ese exige observar durante semanas. Hasta tenerlo, estrechar la ventana con una sola medición es exactamente el error que la ventana existe para evitar.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-marca-de-agua.md`
  summary: Primera medición del costo de lectura de un Ciclo: 24 685 contratos en 25 páginas y 56 segundos, sin token, desde una máquina doméstica. Extrapolado a la ventana de 30 días, ~92 500 contratos, ~93 páginas, ~3,5 minutos.
  evidence: Medido el 2026-09-03 con `--dry-run`. Es la primera evidencia sobre `ASSUMPTION-5` y por ahora la sostiene con holgura. Falta la mitad cara: el costo de ESCRITURA en la capa cruda, que solo se mide con una ingesta real contra PostgreSQL, y el dataset de Procesos, que todavía no se puede ingerir.

- source_spec: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-03.md`
  summary: El grano de `p6dx-8zbt` es la adjudicación, no el Proceso: `id_del_proceso = CO1.REQ.10772032` devuelve 21 filas, iguales en lo procedimental y distintas en proveedor y valor adjudicado.
  evidence: Medido el 2026-09-03. `id_del_proceso` no es llave primaria del dataset. La mayoría de Procesos trae una sola fila —tiene una sola adjudicación— y por eso el error era invisible; los que traen muchas son los procesos grandes de varios lotes, justo los que más importa vigilar. La 1.4 deduplica y reporta cuántas filas colapsó; el detalle por adjudicatario queda para la 1.5.

- source_spec: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-03.md`
  summary: Sin medir: si un mismo `id_del_portafolio` puede corresponder a más de un `id_del_proceso`.
  evidence: La consulta de agrupación sobre el universo nacional excede el tiempo de respuesta de la API sin token (2026-09-03, dos intentos, ambos con timeout). El diseño de la 1.4 evita apostar —une por identificador de portafolio en vez de declarar una clave foránea— pero la pregunta sigue abierta y se responde barato con un token de Socrata, o contra la base ya ingerida.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: CONFIRMADO en condiciones reales: la falta de reintento aborta Ciclos de verdad. El 2026-09-03 la fuente devolvió HTTP 500 en `$offset=5000` y el Ciclo se interrumpió tras 5 de 25 páginas.
  evidence: Es la primera entrada de este archivo, escrita el 2026-09-02 como riesgo teórico. Hoy ocurrió: `{"errorCode":"internal-error","tag":"67f706da-ad93-4d0c-8012-2d5367e61b22"}`. El comportamiento fue el correcto —el Ciclo quedó `interrumpido` con su causa, sin truncar en silencio— pero con 25 páginas por Ciclo y un 500 esporádico, un Ciclo diario desatendido fallaría a menudo. Deja de ser trabajo diferido y pasa a ser prerrequisito de la épica 6: reintento con espera exponencial ante 429, 500, 502, 503 y el 202 de Socrata, con tope de intentos y respeto a `Retry-After`.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-2-marca-de-agua.md`
  summary: `ASSUMPTION-5` medido de punta a punta: 24 685 contratos leídos y guardados en 95,4 s. Escribir cuesta un 80% sobre leer (53 s → 95,4 s). Extrapolado a la ventana de 30 días, ~6 minutos por Ciclo.
  evidence: Primera ingesta real, 2026-09-03, PostgreSQL 17 nativo en una máquina doméstica, con token de Socrata. El supuesto queda sostenido con evidencia y no por defecto. Falta sumarle Procesos, que no se puede ingerir hasta capturar su esquema. Queda también sin medir cuánto pesa en disco esa ingesta, que es el número que decide el hospedaje de la 6.1.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: Sin token de Socrata la cuota por IP corta el Ciclo a mitad: el 2026-09-03 los 503 se volvieron permanentes en la página 10 de 25, y con token las 25 páginas pasaron sin un solo reintento.
  evidence: Medido las dos formas el mismo día y con la misma consulta. El token es gratuito y pasa de cuota compartida por IP a cuota propia. Consecuencia operativa: `VIGIA_TOKEN_SOCRATA` deja de ser opcional para cualquier Ciclo del tamaño real, y la épica 6 debería fallar ruidosamente al arrancar si no está configurado, en vez de descubrirlo a mitad del recorrido.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: Idempotencia verificada sobre datos reales: repetir el mismo Ciclo sobre 24 685 contratos ya ingeridos insertó 0 y dejó la tabla intacta. Costo del rechazo por duplicado: 25 s sobre los 53 s de solo leer.
  evidence: Medido el 2026-09-03, segunda corrida del mismo rango contra la base de la primera. Es el precio real de la ventana de solapamiento en régimen estable: cada Ciclo reenvía treinta días de filas para que la llave primaria las rechace. Extrapolado, ~4,8 min por Ciclo estable contra ~6 min por uno que trae todo nuevo. Si algún día duele, la vía es enviar solo las llaves para descartar antes de serializar el JSONB, no debilitar la ventana.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: `probar.ps1` comprobaba que `.env` existiera y nunca lo leía. El token de Socrata llevaba horas configurado y sin usarse, y una corrida limpia se atribuyó al token cuando fue la fuente recuperándose sola.
  evidence: Detectado el 2026-09-03 cuando `capturar-procesos.ps1` —que sí carga el `.env`— devolvió 403 «Invalid app_token specified» sobre un token que la corrida anterior parecía haber usado con éxito. Corregido: `probar.ps1` carga el `.env` y dice cuántos caracteres tiene el token. Lección general: un archivo de configuración que el programa no lee es peor que no tenerlo, porque parece que sí. Falta que el propio `python -m vigia` avise al arrancar cuando `VIGIA_TOKEN_SOCRATA` está ausente, en vez de depender de que el guion de turno lo cargue.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-esquema-unificado.md`
  summary: La normalización recorre SIEMPRE todo el crudo, no solo lo que trajo el último Ciclo. Con el universo nacional serán cientos de miles de filas releídas cada vez.
  evidence: Es correcto y es lo que hace posible el reproceso desde crudo de la 6.3, pero el costo crece con el histórico y hoy no está medido. Cuando duela, la vía es normalizar por rango de `consultado_en` sin perder la capacidad de rehacerlo todo.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-esquema-unificado.md`
  summary: Las señales de normalización (`normalizados`, `huerfanos`, `sin_llave_de_cruce`, `procesos_colapsados`) tienen columna en `ciclo` pero el comando de normalización no escribe ahí: hoy solo las imprime.
  evidence: La migración 004 las crea y las comenta. Ligarlas al Ciclo exige decidir si la normalización es parte del Ciclo o un paso aparte con su propio registro, y esa decisión es de la 6.1 (Ciclo diario programado), donde el Ciclo pasa a ser una unidad operativa de verdad.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-esquema-unificado.md`
  summary: La capa normalizada guarda 9 de los 85 campos de Contratos y 9 de los 59 de Procesos: identidad, llave de cruce, entidad, valor y fechas.
  evidence: Deliberado. La 1.5 (identidad de proveedor) y la 1.6 (territorio) añaden lo suyo, y el resto sigue accesible en el crudo por `id_fila_fuente` + `hash_contenido`. Falta revisar, al escribir las Reglas de las épicas 2 y 4, que ningún umbral necesite un campo que no se subió a la capa normalizada.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-esquema-unificado.md`
  summary: El cuarto criterio de la 1.4 pide que «sin llave de cruce» se reporte cuando supera un **umbral configurable**. Se implementó el reporte separado; el umbral no.
  evidence: Deliberado. No hay ni una medición del valor normal de esta señal sobre datos reales, y un umbral inventado sería peor que ninguno: o no dispara nunca, o dispara siempre y se aprende a ignorarlo. La 2.5 (modo calibración) es donde los umbrales dejan de ser adivinanzas; este debería salir de ahí, no de antes.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: Un token de Socrata vencido tumbaba la corrida entera de `probar.ps1`, pese a ser una credencial OPCIONAL. Corregido: el paso 8 reintenta una vez sin token y sigue sin él, diciéndolo en voz alta.
  evidence: El 2026-09-03, en cuanto `probar.ps1` empezó a leer de verdad el `.env`, la fuente respondió 403 «Invalid app_token specified» y los 10 pasos se quedaron en 8. Patrón general que vale más allá de este token: una credencial opcional nunca debe poder bloquear más de lo que habilita; si falla, se degrada a la ruta sin ella y se nombra el hecho. Pendiente aplicarlo dentro de `python -m vigia`, no solo en el guion: hoy la degradación vive en PowerShell y no protege a quien corra el módulo a mano ni al Ciclo programado de la 6.1.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-ingesta-cruda.md`
  summary: CORRECCIÓN DE UNA ENTRADA ANTERIOR. La idempotencia de la capa cruda NO es una propiedad general: solo se cumple entre dos Ciclos separados por minutos. `:id` de Socrata no es estable, y la llave primaria del crudo se apoya en él.
  evidence: Medido el 2026-09-03 a las 17:39 con `revisar-crudo.ps1`. Tras dos Ciclos sobre el rango IDÉNTICO 2026-08-26..2026-09-02, `crudo_registro` tiene 50 434 filas y **50 434 `id_fila_fuente` distintos** — ni un solo contrato con dos versiones—, mientras la capa normalizada colapsa esas filas en 25 749 `id_contrato` distintos. Es decir, 24 685 contratos volvieron a entrar con un `:id` NUEVO. La consulta que compara la versión vieja con la nueva de un mismo contrato devolvió 0 filas: no es que el contenido cambiara, es que la fuente reasignó los identificadores de fila. La entrada anterior («segunda corrida insertó 0 y contó 24 685 duplicados») está bien medida pero mal generalizada: las dos corridas de aquel día fueron minutos después una de otra, dentro de la misma publicación del dataset.
  impact: Tres consecuencias, en orden de gravedad. (1) `insertados`/`duplicados` del Ciclo dejan de ser una señal de salud: `duplicados` marcará 0 para siempre y una duplicación real sería indistinguible del funcionamiento normal. (2) El crudo crece por el tamaño de la VENTANA, no por lo nuevo: 149 MB para 8 días × 2 Ciclos, ~3,1 KB por fila. Extrapolado a la ventana nacional de 30 días corriendo a diario son ~300 MB por Ciclo, ~9 GB al mes, de los cuales ~97 % son reinserciones. (3) El reproceso desde crudo de la 6.3 seguiría siendo correcto, porque el `DISTINCT ON` de la capa normalizada colapsa bien; pero leería tres veces más filas de las necesarias.
  fix: Cambiar la llave del crudo del `:id` de la plataforma al identificador de negocio del dataset (`id_contrato`, `id_del_proceso`) más el hash de contenido. Es una migración y un cambio en `RegistroCrudo`, con tamaño de historia propia: toca la 1.1, que está en `review`. No parchear antes de decidirlo, porque cambiar la llave primaria de la serie histórica no se deshace.
  no_regression: La capa normalizada NO está afectada y la 1.4 no tiene que cambiar: se identifica por `id_contrato` y el `DISTINCT ON` hizo exactamente su trabajo. Que un error en la capa de abajo saliera recuperable desde arriba es la primera vez que el diseño «el crudo guarda todo y no interpreta nada» se paga solo.

- source_spec: `_bmad-output/planning-artifacts/prd.md`
  summary: FRONTERA DE RÉGIMEN. El 7 de agosto de 2026 se posesionó el nuevo gobierno NACIONAL. Ninguna Regla puede comparar un contrato o un proveedor contra un histórico que cruce esa fecha sin saber que la cruza.
  evidence: Aportado por el dueño del producto el 2026-09-03 y medido el mismo día contra la base. En el agregado el efecto es casi nulo —7 718 procesos por día hábil antes, 7 643 después, 1,0 % de diferencia— y la razón es constitucional, no estadística: el cambio es del orden NACIONAL, mientras alcaldes y gobernadores siguen en el periodo 2024-2027 y no cambiaron nada ese día. La mayor parte de lo que se publica en el SECOP es territorial, así que el promedio nacional lo diluye. Donde sí se ve es entidad por entidad: la Agencia Nacional de Tierras pasó de 2 997 procesos a 40 (-98,7 %) y el sistema de medios públicos de 812 a 1 (-99,9 %), mientras entidades territoriales del mismo tamaño no se movieron o subieron.
  impact: (1) La 2.5 (modo calibración) y la 3.3 (tasa de confirmación) no pueden calibrar umbrales sobre una serie que cruce el 7 de agosto sin partirla, o el cambio de régimen se leerá como señal. (2) La 4.4 (concentración por ordenador) compara contra el ordenador del gasto, y en entidades nacionales ese cargo cambió: el histórico del ordenador anterior no es línea base del nuevo. (3) La 4.3 (concentración por proveedor) hereda el mismo problema en entidades nacionales. (4) La épica 5 necesita decirlo en el sustento: un proveedor que "aparece de la nada" en septiembre en una entidad nacional puede ser rotación normal de gobierno.
  fix: El PRD necesita una restricción explícita —«las fronteras de régimen son datos, no supuestos»— con al menos dos fechas conocidas: 2026-08-07 (nacional) y 2028-01-01 (territorial, fin del periodo 2024-2027). Clasificar entidades por orden nacional/territorial es prerrequisito, y hoy no existe: es parte de la 1.6.

- source_spec: `_bmad-output/planning-artifacts/prd.md`
  summary: CALENDARIO HÁBIL COLOMBIANO. Cualquier Regla que compare ritmos por unidad de tiempo tiene que descontar festivos, o inventará señales. Casi publico una caída del 45,7 % que era puro calendario.
  evidence: Medido el 2026-09-03. Comparando los once días naturales anteriores al 7 de agosto contra los once posteriores salían 79 789 procesos contra 43 321: una caída del 45,7 %. Falsa entera. La ventana posterior tiene cinco días hábiles y la anterior nueve, porque el 7 de agosto es festivo (Batalla de Boyacá) y el 17 también (Asunción, trasladada al lunes por la Ley Emiliani). Normalizando por día hábil real, 8 568 contra 7 621; y sobre el período completo, 1,0 % de diferencia.
  impact: Afecta directamente a la 4.5 (plazo exprés) y a la 4.6 (posible fraccionamiento), que miden distancias temporales, y a cualquier umbral expresado «por día» o «por semana». Colombia tiene dieciocho festivos al año y la Ley Emiliani mueve doce de ellos al lunes siguiente, así que el calendario no se puede aproximar con `dow <= 5`.
  fix: Una tabla de festivos versionada en el repositorio, capturada y revisada como la de esquemas esperados de la 1.3 y la territorial de la 1.6 — no calculada al vuelo, no traída de una librería sin fijar. Con función `es_habil(fecha)` y `dias_habiles(desde, hasta)` usadas por toda Regla que hable de tiempo.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-4-esquema-unificado.md`
  summary: Medido el techo de huérfanos y su causa probable. De los 22 365 contratos enlazados, el 95,9 % viene de procesos publicados DESPUÉS del 7 de agosto; solo el 4,1 % de procesos anteriores.
  evidence: Los contratos ingeridos se firmaron entre el 26 de agosto y el 2 de septiembre, y los procesos se trajeron desde el 1 de julio. Que casi todo lo enlazado venga de procesos de las últimas cuatro semanas dice que el trayecto proceso→contrato es de días, no de meses —coherente con que el 81 % sea contratación directa— y sugiere que los 3 384 huérfanos son sobre todo contratos de procesos anteriores al 1 de julio, fuera de la ventana. Es una hipótesis con evidencia, no un hecho: se confirma ampliando la ventana de procesos hacia atrás y volviendo a medir.

- source_spec: `_bmad-output/planning-artifacts/epics.md` (historia 4.5)
  summary: Medido el «plazo exprés» sobre datos reales antes de escribir la Regla. Un umbral único es inservible y el criterio por modalidad queda confirmado con números, no supuesto.
  evidence: Medido el 2026-09-03 sobre los 22 365 contratos enlazados. Mediana global: 1 día. **9 093 contratos (40,7 %) se firmaron el MISMO DÍA en que se publicó su Proceso.** Un umbral absoluto de «un día o menos» marcaría 14 469 contratos, el 64,7 % del total. Partido por modalidad el dato se separa limpio: contratación directa, mediana 1 día (mínimo 0); licitación pública, mediana 44 días y mínimo 16 sobre 33 casos. Cuarenta y cuatro veces de diferencia entre las medianas. Cero contratos firmados antes de publicarse su proceso: en esta dimensión las fechas de la fuente son internamente consistentes.
  impact: (1) Confirma el criterio de aceptación de la 4.5 tal como está escrito («por debajo del percentil configurado de su modalidad y sector») y descarta cualquier versión con umbral global. (2) Hallazgo incómodo para la priorización de la épica 4: la bandera más barata de calcular es la menos útil sobre el grueso del volumen. En contratación directa —81 % de lo enlazado— el Proceso y el Contrato se publican casi a la vez y el plazo no discrimina. El valor de la 4.5 está en la minoría competitiva. (3) La 2.5 (modo calibración) no es un lujo ni un paso posterior: sin ella esta bandera no se puede encender sin inundar la cola.
  limite: La distribución está RECORTADA POR ARRIBA. Solo entran contratos enlazados, y enlazar exige que el Proceso caiga dentro de la ventana ingerida (desde el 1 de julio). Un contrato cuyo Proceso se publicó en marzo hoy cuenta como huérfano, no como plazo largo. El plazo real es mayor que el medido, y los percentiles altos no se pueden usar para calibrar hasta que la 1.7 amplíe la ventana. Los percentiles bajos —que son los que usa esta bandera— sí sobreviven al sesgo.

- source_spec: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-04.md`
  summary: RESUELTO EN CÓDIGO, pendiente de correr sobre la base real. La capa cruda pasa a llave de negocio y a hash sin campos de plataforma. 229 pruebas en verde contra PostgreSQL real.
  evidence: `DatasetSecop.campos_identidad` declara la identidad por dataset (`id_contrato`; `id_del_proceso` + `id_adjudicacion`), `hash_contenido` excluye las claves que empiezan por `:`, y `python -m vigia.crudo.rellave` traslada lo ya guardado usando las mismas funciones que la ingesta —por eso es Python y no SQL: dos implementaciones del mismo hash es una de más—. La migración 005 solo crea la tabla de destino; nada se borra y el intercambio deja la tabla anterior como `crudo_registro_antes_de_005`.
  hallazgo: Una prueba de integración que ya existía detectó el efecto secundario: con identidad = solo `id_del_proceso`, las 21 filas del proceso multilote colapsaban en una y la capa cruda perdía 20 adjudicaciones. Por eso la identidad de `procesos` lleva `id_adjudicacion` como segundo componente. La prueba sabía la respuesta antes que yo.
  pendiente: Correrlo sobre la base real de Guillermo. Es la decisión que la propuesta deja en su mano, y hasta que la tome `crudo_registro` sigue siendo la de antes.

- source_spec: `_bmad-output/planning-artifacts/epics.md` (historia 1.5)
  summary: MEDIDO ANTES DE DISEÑAR. El 82,4 % de los contratos del SECOP son con PERSONAS NATURALES, no con empresas: 4 929 133 con Cédula de Ciudadanía frente a 900 513 con NIT, sobre los ~6,02 millones del histórico nacional.
  evidence: Consultado a `jbjy-vk9h` el 2026-09-04. Cambia el peso de varias historias: la 5.2 (filtro de persona natural) deja de ser un detalle de privacidad y pasa a decidir qué se puede publicar de cuatro de cada cinco contratos; y «concentración por proveedor» de la 4.3 va a hablar sobre todo de personas, con lo que eso implica para el sustento de la épica 5.

- source_spec: `_bmad-output/planning-artifacts/epics.md` (historia 1.5)
  summary: EVITADA UNA ALERTA FALSA DE PRIMERA MAGNITUD. 175 836 contratos traen la cadena literal «No Definido» como documento de proveedor. Canonizar sin más los habría fundido en un único proveedor `NODEFINIDO`, el contratista más concentrado de Colombia, y falso entero.
  evidence: Medido el 2026-09-04. Son sobre todo Uniones Temporales y Consorcios, que la fuente registra con tipo «NIT» y documento sin definir. La regla que lo ataja no es una lista de centinelas —siempre se queda corta— sino «un documento sin un solo dígito no es un documento». Los contratos NO se descartan: no entran al índice de proveedores y se cuentan aparte, igual que los huérfanos de la 1.4.
  pendiente: Las UT y Consorcios se quedan sin identidad de proveedor, y con ellos toda la contratación por unión temporal — que en salud y alimentación escolar es enorme. Darles identidad exige mirar los integrantes, que este dataset no trae. Es una historia propia y hay que decidir si entra en la v1.

- source_spec: `_bmad-output/planning-artifacts/epics.md` (historia 1.5)
  summary: La regla del dígito de verificación del NIT se restringe a números que empiezan por 8 o 9, y es una elección deliberada de fallar por defecto y no por exceso.
  evidence: Sobre 25 documentos reales de tipo NIT y diez dígitos (2026-09-04): los **16 que empiezan por 8 o 9 verificaron su DV, los 16**; de los 9 que empiezan por 1 solo verificó 1, que es justo lo que da el azar (una de cada once). Esos nueve son cédulas de diez dígitos mal etiquetadas como NIT. Aplicarles la regla les quitaría un dígito y las convertiría en otra persona.
  decision: Queda sin cubrir el NIT de persona natural cuya cédula empieza por 1: contará como dos proveedores si aparece con y sin DV. Se acepta. Separar de más subestima una concentración; unir de más la inventa, y una alerta inventada es lo que este proyecto no se puede permitir. El mismo criterio debería regir cualquier futura fusión de identidades.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-5-identidad-de-proveedor.md`
  summary: Las pruebas de integración de la 1.4 replicaban la tubería de normalización a mano en vez de llamarla. Al llegar la 1.5 la copia se quedó atrás: no guardaba proveedores y tres pruebas pasaban sobre una tubería que ya no era la de producción.
  evidence: Detectado el 2026-09-04. Corregido extrayendo `ejecutar(dsn)` en `vigia/normalizado/__main__.py`, que ahora usan el comando y las pruebas por igual. Lección general: una tubería duplicada en las pruebas no prueba el producto, prueba la copia — y no avisa cuando divergen.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-5-identidad-de-proveedor.md`
  summary: Las Uniones Temporales y Consorcios se quedan SIN identidad de proveedor, y con ellos toda la contratación por unión temporal.
  evidence: Son la mayor parte de los 175 836 contratos con documento «No Definido». En alimentación escolar (PAE) y salud mueven cifras muy grandes: en la muestra del 2026-09-04 aparecieron «UT NUTRIENDO EL PAE 2026», «UT NOC 2022», «CONSORCIO INTER-IPES». Quedan fuera del alcance de la 4.3 y de la 4.6 mientras no tengan identidad.
  fix: Darles identidad exige los integrantes de la unión, que `jbjy-vk9h` no trae. Habría que mirar el dataset de proveedores o el de procesos. Es una historia propia y hay que decidir si entra en la v1 — el comando ya reporta qué porcentaje de contratos deja sin vigilar, así que la decisión se puede tomar con el número delante.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-5-identidad-de-proveedor.md`
  summary: CORRECCIÓN DE DOS AFIRMACIONES MÍAS QUE ERAN FALSAS. Escribí, en este mismo archivo y en el código, que los 175 836 contratos con documento «No Definido» eran «casi todos» y «la mayor parte» Uniones Temporales y Consorcios. No lo eran, y no lo había medido: lo deduje de haber visto tres nombres de UT en una muestra pequeña.
  evidence: |
    Medido el 2026-09-04 contra `jbjy-vk9h`, sobre los 175 836:

    | Estado del contrato | Contratos |
    |---|---|
    | Borrador | 91 448 |
    | Cancelado | 69 095 |
    | subtotal: nunca adjudicaron a nadie | **160 543 (91,3 %)** |
    | contratos de verdad (Modificado, terminado, En ejecución, Cerrado, Aprobado, Suspendido, …) | **15 293 (8,7 %)** |

    Y de esos 15 293 contratos reales, **15 291 —el 99,99 %— traen `es_grupo = 'Si'`**: ahí sí son Uniones Temporales y Consorcios.

    El universo de grupos son 39 767 contratos, y **25 866 de ellos SÍ traen NIT**: una unión temporal en Colombia tiene NIT propio, y esos ya se agrupaban bien desde la 1.5. El hueco nunca fueron «las uniones temporales»: es la parte de ellas a la que la entidad no le diligenció el documento.
  impacto_del_error: Sobredimensionaba el problema en un factor de once (175 836 frente a 15 291) y apuntaba a la solución equivocada —«hay que buscar los integrantes de la unión en otro dataset»— cuando el 65 % de los grupos ya estaban identificados y a los demás les bastaba con no desaparecer del conteo. Guillermo tomó la nota por buena y preguntó cómo evitar que quedaran volando; la pregunta era la correcta, la premisa era mía y estaba mal.
  leccion: La medición que faltaba costó tres consultas. La afirmación sin medir llevaba un día en el repositorio con aspecto de hecho, dentro de un archivo cuyo propósito es justamente registrar lo medido. Una frase como «casi todos son X» necesita el mismo `count(*)` que cualquier otra.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-5-identidad-de-proveedor.md`
  summary: RESUELTO (1.5b). Las Uniones Temporales y Consorcios sin documento ya no desaparecen: reciben identidad PROVISIONAL, una por contrato, marcada como tal.
  evidence: `identidad_del_contrato()` en `vigia/normalizado/proveedor.py` da identidad `(UNION TEMPORAL O CONSORCIO SIN DOCUMENTO, id_contrato)` a todo contrato cuyo documento no sirva **y** venga marcado `es_grupo = 'Si'`. Migración 007: `proveedor.provisional` y `contrato.proveedor_provisional` son columnas GENERADAS a partir del tipo, no banderas que escriba Python, para que la base y el código no puedan discrepar. El comando reporta cuántos son y cuánta plata mueven; `reporte.sql` los lista uno a uno por valor. 286 pruebas en verde contra PostgreSQL real.
  decision: |
    Una identidad POR CONTRATO, no por nombre. El nombre («UNION TEMPORAL SALUD 2024») lo teclea cada entidad, no es único en el país, y agrupar por él fundiría uniones distintas en una concentración inventada. Con una identidad por contrato el error es imposible en las dos direcciones: no funde nada y no deja nada fuera del conteo. El nombre queda registrado como variante, así que la historia que quiera juntarlas tendrá con qué — y con evidencia.

    Lo que una identidad provisional NO habilita: medir concentración. Por construcción hay exactamente una por contrato, así que jamás podrá aparecer en un ranking de contratistas. La 4.3 tiene que excluirlas del ranking Y reportar su total, que es lo contrario de esconderlas.
  pendiente: |
    (1) LA CIFRA EN DINERO del hueco nacional sigue sin medir. Las consultas están escritas en `medir_uniones.py`, listas para correr; la fuente dejó de responder agregados a mitad de la sesión y NO se inventó el número.
    (2) IDENTIDAD REAL de esas uniones: los integrantes no están en `jbjy-vk9h`. Habría que mirar el dataset de procesos o la ficha de SECOP II. Es una historia propia (1.8), y ahora es una MEJORA, no un agujero: hoy los contratos ya se cuentan, se suman y se listan.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-5-identidad-de-proveedor.md`
  summary: MEDIDO SOBRE LA BASE REAL DE GUILLERMO (2026-09-04, 25 749 contratos de la ventana). Las uniones temporales sin documento son 102 contratos —el 0,40 %— y mueven **$358.964.624.020: el 15,03 % de todo el valor de la ventana**, repartidos en 73 entidades.
  evidence: |
    Corrida completa en su maquina: migraciones 001-007 aplicadas, normalizacion sobre 341 549 filas de procesos y 25 749 contratos. Resultado: 24 998 identidades de proveedor, 102 provisionales, 2 contratos sin identidad ninguna, 12,9 % de huerfanos.

    Los tres mayores: CONSORCIO BOCAS 26 con el Fondo Mixto de Innovacion y Desarrollo Social ($104 604 909 072), CONSORCIO GR COLIBRIES con el Municipio de Pereira ($39 954 375 001) y UT ECOSISTEMAS ESTRATEGICOS 2026 con CORPOBOYACA ($30 605 438 931).
  por_que_importa: Cuatro de cada mil contratos cargan la sexta parte del dinero, y hasta hoy no tenian identidad de proveedor: no salian en ningun conteo. La cifra nacional en dinero sigue sin medir, pero esta ventana ya dice que el hueco no era pequeno en plata aunque lo fuera en numero de contratos.

- source_spec: `uniones-lista.ps1`
  summary: ERROR CORREGIDO EN CALIENTE. La primera version de la consulta ordenaba mal y el «top 20» no era el de los mayores, sino alfabetico.
  evidence: |
    La consulta decia `to_char(valor, 'FM999G999G999G999') AS valor ... ORDER BY valor DESC`. En `ORDER BY`, PostgreSQL prefiere el NOMBRE DE SALIDA sobre la columna, asi que ordeno por el texto ya formateado: «998.000.000» quedaba por encima de «9.287.018.195». El ranking se veia perfectamente plausible —cifras grandes, entidades reales— y estaba mal.
  leccion: Un resultado plausible no es un resultado verificado. Lo que delato el fallo fue mirar la columna de valores de arriba abajo, no revisar la consulta. Cualquier `ORDER BY` sobre una columna que ademas se formatea en el `SELECT` tiene que usar un alias distinto, o apuntar a la tabla.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-6-territorio-y-orden.md`
  summary: MEDIDO ANTES DE DISEÑAR. El campo `orden` del SECOP tiene TRES valores, no dos: Territorial, Nacional y **Corporación Autónoma**.
  evidence: Agosto de 2026: 90 101 / 19 967 / **2 224**. Año 2019 completo: 73 932 / 66 860 / **1 800**. Las CAR aparecen en los dos cortes, con siete años de distancia, así que no son ruido de un mes. Una bandera booleana `es_nacional` las habría metido en el cajón que no es, y son quienes manejan la plata ambiental.
  impact: Afecta a cualquier análisis del corte del 7 de agosto de 2026 y a toda Regla con umbral distinto por orden administrativo. La columna `contrato.orden` es texto con CHECK sobre los tres valores medidos: una cuarta categoría que entre por descuido se rechaza en vez de colarse.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-6-territorio-y-orden.md`
  summary: EVITADO UN HUECO SILENCIOSO DEL 16 % DE LOS CONTRATOS. Los nombres de departamento del SECOP no coinciden con los de DIVIPOLA en exactamente dos casos, y uno de ellos es Bogotá.
  evidence: |
    El DANE escribe `BOGOTÁ, D.C.` y el SECOP `Distrito Capital de Bogotá`; el DANE `ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA` y el SECOP `San Andrés, Providencia y Santa Catalina`. Los otros 31 cuadran al normalizar. Bogotá son 17 732 contratos de los 110 000 de agosto de 2026: el 16 %.

    Un cruce por nombre no habría dado error ni fila rechazada — simplemente un hueco. Los dos alias quedan declarados con su código y una prueba recorre los 33 nombres que el SECOP escribe exigiendo que todos resuelvan.
  hallazgo_lateral: Los nombres de departamento de la fuente vienen LIMPIOS: 33 valores distintos en un mes, sin variantes ni erratas, más 1,4 % de «No Definido». El problema no era limpiar, era traducir. Conviene comprobar el supuesto antes de escribir el limpiador.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-6-territorio-y-orden.md`
  summary: El municipio NO se puede identificar por su nombre. Queda con nombre y sin código, a sabiendas.
  evidence: «Argelia» son tres municipios distintos: Antioquia (16 contratos), Cauca (16) y Valle del Cauca (15). Con conteos así de parecidos, fundirlos no se vería raro en ningún reporte — es el mismo modo de fallo del proveedor «NODEFINIDO», pero repartido y por eso más difícil de ver.
  fix: Historia 1.9. Cargar la tabla DIVIPOLA de municipios (~1 100 filas) y comprobarla contra los 638 nombres que el SECOP escribe en un mes. Mientras tanto, cualquier corte municipal se hace por el par (departamento, nombre) y hay que decirlo en el reporte.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-6-territorio-y-orden.md`
  summary: MEDIDO SOBRE LA BASE REAL (2026-09-05, 25 749 contratos). El reparto por orden administrativo confirma que las Corporaciones Autónomas no son residuales, y aparece un centinela NUEVO a nivel de municipio.
  evidence: |
    | Orden | Contratos | Valor |
    |---|---|---|
    | TERRITORIAL | 21 272 | $1 829 607 004 776 |
    | NACIONAL | 4 039 | $505 001 293 894 |
    | CORPORACION AUTONOMA | 438 | $53 140 588 632 |

    Cero contratos sin orden declarado y cero sin código de departamento: los 33 nombres resolvieron.

    Por departamento, Antioquia encabeza por valor ($747 200 millones en 3 159 contratos) por delante de Bogotá ($451 568 millones en 3 733), y Casanare es tercero con 561 contratos — señal de que el valor no sigue al número de contratos.
  hallazgo: |
    **«NO DEFINIDO» aparece como nombre de municipio en 28 departamentos distintos.** Es el mismo modo de fallo que el «No Definido» del documento de proveedor, un nivel más abajo: codificar municipios por el nombre habría creado un municipio fantasma con contratos de medio país. Y «SAN ANDRES» aparece en 3 departamentos, «ALBANIA», «BARBOSA», «CALDAS», «CORDOBA», «FLORENCIA», «LA UNION», «RIONEGRO» y seis más en 2.

    Confirma en datos propios lo que la tabla del DANE ya decía: 1 122 municipios con solo 1 037 nombres distintos. (El número de nombres COMPARTIDOS es 66, no 85; ver la corrección más abajo.)

- source_spec: `capturar-divipola.ps1`
  summary: UN SUPUESTO MÍO, FALSO, QUE LA PROPIA COMPROBACIÓN ATRAPÓ. Escribí en el capturador que «ningún nombre de municipio colombiano trae coma», con una comprobación que abortaba si la encontraba. Abortó en la primera corrida, contra Bogotá.
  evidence: DIVIPOLA llama al municipio 11001 **«BOGOTÁ, D.C.»**, con coma. El script paró antes de escribir —hizo exactamente lo que debía: dejar la tabla anterior intacta en vez de reemplazarla por un CSV roto— pero la premisa estaba mal. Corregido citando el campo como manda el CSV, con una prueba que fija el caso.
  leccion: |
    Vale la pena separar las dos cosas que hizo esa comprobación. Como **guardia** funcionó: falló ruidosamente y no corrompió nada. Como **supuesto** era falso, y lo era sobre el municipio más importante del país — el mismo que ya había fallado en la 1.6 por escribirse distinto en DANE y en SECOP.

    Bogotá lleva dos por dos: es el caso raro en las dos tablas. Cualquier tabla territorial nueva debería probarse contra Bogotá antes que contra nada.

- source_spec: `vigia/normalizado/divipola.py`
  summary: CORRECCIÓN DE UN NÚMERO QUE INFERÍ EN VEZ DE MEDIR. Escribí que «85 nombres los comparte más de un municipio». Son **66** —67 al normalizar—. La prueba contra la tabla real lo tumbó.
  evidence: |
    La tabla capturada trae 1 122 municipios y 1 037 nombres distintos. Convertí la resta 1 122 − 1 037 = 85 en un conteo de nombres, y no lo es: **cuenta filas sobrantes**. Un nombre que aparece cuatro veces aporta 3 a esa resta y 1 al conteo de nombres compartidos.

    Los números reales: **66 nombres compartidos, que abarcan 151 municipios**. Los más repetidos van de a cuatro — «LA UNIÓN», «VILLANUEVA» y «BUENAVISTA» son cuatro municipios cada uno; «ARGELIA» y «GRANADA», tres.
  hallazgo: |
    Al normalizar (mayúsculas, sin tildes) suben a **67**: `CHIMÁ` (Córdoba, 23168) y `CHIMA` (Santander, 68176) son dos municipios reales que **se distinguen solo por la tilde**. Están en departamentos distintos, así que el par los separa igual — pero es la prueba más limpia de que el nombre por sí solo, normalizado o no, no identifica a un municipio.
  leccion: Una resta entre dos conteos no es un conteo. La afirmación se escribió antes de tener la tabla y sobrevivió hasta que hubo con qué comprobarla; la prueba que la comprobaba se escribió con el número inferido y falló en la primera corrida real, que es exactamente para lo que sirve.

- source_spec: `vigia/panel.py`
  summary: EL PANEL ENCONTRÓ UN FALLO REAL EN SU PRIMERA CORRIDA. El documento `000000000` pasaba el filtro de centinelas y había fundido TRES consorcios distintos en un solo proveedor, con tres razones sociales.
  evidence: |
    La regla de la 1.5 era «un documento sin un solo dígito no es un documento». `000000000` tiene dígitos, así que entraba como identidad válida. En la ventana del 2026-09-05 aparecía en `proveedor` con `variantes = 3` y nombre principal «CONSORCIO INTER CANCHA UNION» — tres consorcios que no tienen nada que ver, contados como uno.

    Tres, no trescientos, porque la ventana es de ocho días. Sobre el histórico nacional sería exactamente el `NODEFINIDO` que la 1.5 existe para evitar, entrando por la puerta de al lado.
  fix: |
    Regla nueva en `canonizar_documento`: **un documento que es un solo carácter repetido no es un documento** — `000000000`, `0`, `11111111`. Ningún NIT ni cédula real de Colombia lo es, así que el riesgo de separar a alguien de verdad es nulo, y el de fundir a varios era real y ya estaba ocurriendo. Los que además son grupo pasan a identidad provisional, que es donde deben estar.
  leccion: |
    Ninguna prueba lo habría encontrado: las pruebas comprueban los casos que uno ya pensó, y este no se me había ocurrido. Lo encontró **mirar los datos reales dibujados**, en el primer minuto de existir el Panel.

    Es un argumento a favor de sacar producto temprano aunque las Reglas no estén: una tabla ordenada por valor delante de los ojos hace preguntas que un `pytest -q` en verde no hace.
  pendiente: La corrección está en el código de su máquina, pero `proveedor` todavía tiene la identidad fundida hasta la próxima normalización.

- source_spec: `_bmad-output/planning-artifacts/epics.md` (historia 2.4)
  summary: MEDIDO ANTES DE ESCRIBIR LA REGLA, sobre 341 549 procesos de la base real. La bandera de oferente único SÍ se puede construir —el embudo llega poblado en el 99,92 % de los adjudicados— pero **un umbral global marcaría más de la mitad del país**.
  evidence: |
    De 341 549 procesos, **9 942 están adjudicados** (2,9 %). De esos 9 942:

    | | |
    |---|---|
    | con `respuestas >= 1` | 9 934 (99,92 %) |
    | con proveedores únicos poblado | 9 731 |
    | con `respuestas = 0` | 8 |
    | con `visualizaciones > 0` | 9 403 (94,6 %) |
    | con `invitados > 0` | 2 554 (25,7 %) |

    Distribución de respuestas: **1 respuesta → 5 415 procesos**; 2 → 1 495; 3 → 808; 4 → 524; 5 → 335. Es decir, **el 54,5 % de los procesos adjudicados del país tiene exactamente una respuesta**.
  decision: |
    **El filtro de modalidad no es una cortesía, es lo que hace que la bandera signifique algo.** 7 766 de los 9 942 adjudicados —el 78 %— están en mínima cuantía (5 390), contratación directa con ofertas (1 378) y régimen especial (998), donde una sola oferta es el desenlace esperado. Quedan ~2 176 en modalidades competitivas.

    Y el caso que la historia describe existe: **4 137 procesos adjudicados con UNA respuesta habiendo tenido más de un invitado o más de una visualización**, con 83,8 invitados y 10 visualizaciones de promedio. En la muestra, una Selección Abreviada con **178 visualizaciones y una sola respuesta**.
  limite: |
    Dos contadores del embudo no sirven y hay que decirlo: `proveedores_que_manifestaron` llega en **cero en todos** los casos mirados, y `proveedores_invitados` solo está poblado en el 25,7 %. Los dos van al Expediente porque el criterio de aceptación pide el embudo entero, pero la Regla no puede apoyarse en ellos: la segunda pata usable es `visualizaciones_del`.
  pendiente: Falta el número que fija el umbral: cuántos de los ~2 176 procesos COMPETITIVOS adjudicados tienen un solo proveedor único. Sin él, `proveedores_unicos_maximos = 1` es una semilla razonada, no un umbral calibrado — y por eso la Regla nace en `borrador` y no puede activarse.

- source_spec: `vigia/calendario.py`
  summary: OTRO SUPUESTO MÍO CORREGIDO POR UNA PRUEBA. Escribí que Colombia tiene dieciocho festivos «siempre». En 2025 y 2030 tiene **diecisiete**.
  evidence: El Sagrado Corazón —Pascua + 68, trasladado al lunes— cae el mismo lunes que San Pedro y San Pablo —29 de junio, trasladado— en esos dos años. El calendario oficial de la Alcaldía de Bogotá para 2025 lista diecisiete fechas, y el módulo las reproduce una por una; esa comparación fecha-por-fecha es ahora la prueba más fuerte del archivo, porque no comprueba una propiedad sino un calendario entero contra su fuente.
  leccion: El algoritmo estaba bien desde el principio; lo que estaba mal era la afirmación que escribí encima de él. Una prueba parametrizada por año —en vez de por un año— fue la que lo encontró.

- source_spec: `instalar-tareas.ps1`
  summary: EL ANTIVIRUS DEL EQUIPO BLOQUEÓ EL INSTALADOR DE TAREAS PROGRAMADAS, y NO se intentó rodear.
  evidence: El archivo llegó a la carpeta pero quedó en un estado ilegible: aparece en el listado sin tamaño ni fecha, y no se puede leer ni ejecutar. En el equipo corre ReasonLabs. Un script que registra tareas programadas es exactamente el patrón que un antivirus debe atajar.
  decision: No se busca un rodeo. Las dos salidas limpias son que el usuario excluya el archivo en su antivirus, o que cree las tres tareas a mano en el Programador de tareas con los comandos documentados. Los tres scripts que las tareas invocan —`ciclo-diario.ps1`, `resumen-periodo.ps1`— sí llegaron y funcionan.

- source_spec: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-06.md`
  summary: EL NÚMERO QUE TUMBÓ LA PRIMERA BANDERA. De los 2 176 procesos competitivos adjudicados, **1 150 —el 52,8 %— terminaron con un solo proveedor único**. En Colombia eso no es una anomalía: es el desenlace mayoritario.
  evidence: |
    Por modalidad, el oferente único es la norma en casi todas:

    | Modalidad | Adjudicados | Con uno solo | % |
    |---|---|---|---|
    | Selección Abreviada de Menor Cuantía | 1 176 | 677 | 57,6 |
    | Selección abreviada subasta inversa | 648 | 299 | 46,1 |
    | Concurso de méritos abierto | 165 | 85 | 51,5 |
    | Licitación pública | 119 | 69 | 58,0 |
    | Licitación pública Obra Pública | 41 | 10 | 24,4 |
    | Enajenación con sobre cerrado | 15 | 3 | 20,0 |

    Las dos excepciones —Obra Pública y Enajenación con sobre cerrado— son justo donde hay activo físico y pliego largo.

    Esos 1 150 procesos mueven **$768 502 882 210**, con 20,3 visualizaciones y 3,8 invitados de promedio. El mayor: una licitación de **$72 001 177 364 con 23 visualizaciones y una sola respuesta**. En los quince mayores, `proveedores_invitados = 0` — el contador confirmado como inservible.
  impacto: |
    La historia 2.4 pide detectar «procesos competitivos que terminan con un solo proponente» dando por hecho que eso es notable. **No lo es.** Una Regla así enciende sobre más de la mitad de su propio universo.

    Y NO se arregla subiendo el umbral: exigir más de 20 visualizaciones baja de 1 150 a 459, pero el 20 no sale de los datos — se elige porque da un número que cabe en una cola. Un umbral escogido para que el resultado quepa no mide nada del mundo.
  fix: Propuesta de cambio del 2026-09-06: la Regla pasa de absoluta a **relativa por modalidad** (`embudo-estrecho`), con la misma forma que la 4.5 ya adoptó para el plazo exprés. La medición que lo decide está escrita en `medir-embudo-relativo.sql` y decide en las dos direcciones: si los procesos de un solo oferente recibieron tanta atención como los de varios, la bandera se descarta.

- source_spec: `vigia/panel.py`, `vigia/resumen.py`, `vigia/revision.py`
  summary: LAS TRES PÁGINAS DEL PROYECTO SALÍAN SIN `<!doctype>` NI `<meta charset>`, y se abren con doble clic desde una carpeta de Windows.
  evidence: |
    Ninguno de los tres generadores emitía cabecera: la plantilla empezaba directamente en `<title>`. Sin `<meta charset="utf-8">` el navegador tiene que adivinar la codificación de un archivo abierto por `file://`, y en un Windows en español la adivina como cp1252. El archivo se escribe en UTF-8, así que **«Vigía» se lee «VigÃ­a» y «razón social» se lee «razÃ³n social»** — en el Panel, en el resumen semanal y en la lista de revisión a la vez.

    Lo encontró una prueba nueva de la lista de revisión que comprobaba que el HTML empezara por `<!doctype html>`. Falló, y al mirar por qué resultó que las otras dos estaban igual desde que existen.
  leccion: |
    El error viene de haber escrito esas plantillas pensando en una página publicada, donde algo más pone la cabecera. Abiertas desde el disco no hay ese algo. **Un archivo que el usuario abre con doble clic es un documento completo o no es nada**, y eso incluye `<html lang="es">`, `<head>`, `<meta charset>`, `<body>` y sus cierres.

    Vale anotar cómo se veía desde afuera: el Panel llevaba días abriéndose y nadie lo reportó, porque un acento roto se lee como «así se ve» y no como «esto está mal». Los defectos que no fallan son los que más duran.
  fix: Las tres plantillas llevan ahora cabecera y cuerpo completos, y una prueba parametrizada (`test_revision.py::TestLasTresPaginasSeAbrenBienDesdeElDisco`) lo comprueba **en las tres**, cargando la salida de verdad de `panel.sql`, `resumen.sql` y `revision.sql` guardada en `tests/datos/`. Cargas inventadas se quedarían viejas en silencio cuando la consulta cambie de forma.

- source_spec: `dia.ps1`
  summary: EL CICLO SE PASÓ DE CALENDARIO A INVENTARIO, y con eso el antivirus dejó de ser un bloqueante.
  evidence: |
    El diseño anterior eran tres tareas programadas: el ciclo a las 06:00, el resumen semanal el lunes 07:30, el mensual el lunes 08:00. Dos problemas, y el antivirus era el menos grave:

    1. **Un disparador que pasa no vuelve.** Si el equipo está apagado el lunes a las 07:30, el resumen de esa semana no se saca nunca. Nadie se entera, porque lo que falta es un archivo que no existe.
    2. El instalador quedó en cuarentena, y no se busca un rodeo.
  decision: |
    `dia.ps1` no pregunta **qué día es hoy** sino **qué falta**: ¿existe ya el resumen de la última semana completa? ¿Y el del último mes completo? Si no, los saca — sea martes o sea jueves. Mira cuatro semanas y dos meses hacia atrás, así que el equipo puede estar apagado quince días sin perder nada.

    Correrlo dos veces el mismo día no duplica ni reescribe nada, porque la pregunta sigue teniendo la misma respuesta.
  limite: Cuatro semanas y dos meses es el corte a propósito. Más atrás que eso ya no es «me salté unos días», es un reproceso, y un reproceso se pide a mano y a sabiendas.

- source_spec: `vigia/normalizado/escala.py`, `migraciones/009_valores_fuera_de_escala.sql`
  summary: LA FUENTE PUBLICA VALORES QUE NO PUEDEN SER CIERTOS, Y HASTA HOY LOS SUMÁBAMOS. Un proceso con **$8 054 481 856 630 300** adjudicados —ocho mil billones, varias veces el PIB del país— y cinco casos del mismo número con tres ceros de más.
  evidence: |
    Apareció buscando la bandera 4.2, no buscándolo a él. De los 119 procesos que adjudican por encima de su presupuesto, los mayores son:

    | Entidad | Presupuesto | Adjudicado |
    |---|---|---|
    | ESE Hospital Local San José | $320 873 959 | **$8 054 481 856 630 300** |
    | Alcaldía de Tipacoque | $431 340 000 | $431 340 000 **000** |
    | Distrito de Medellín | $210 160 000 | $210 160 000 **000** |
    | CVC | $99 070 693 | $99 070 693 **000** |

    Probado de punta a punta en la base de prueba: metiendo ese contrato del hospital, el total de la ventana pasaba de **$27 009 500 000 a $8 054 481 856 630 300**. Un factor de trescientos mil, por un solo registro.
  decision: |
    **Guarda, no corrección.** Vigía no es la fuente y no escribe sobre ella: marca, excluye de totales y rankings, y lo declara. Los contratos marcados se listan aparte **con su valor tal como la fuente lo publica**.

    El techo es 10^14 pesos —100 billones— y **sale del tamaño del Estado, no de nuestros resultados**: el Presupuesto General de la Nación está en el orden de 5 × 10^14 anuales, así que un contrato de 100 billones sería la quinta parte del gasto público del año en un renglón de SECOP. Lleva fecha de vigencia y fuente citable, como la historia 2.1 exige para todo tope normativo.

    Está **deliberadamente holgado**: el mayor contrato público colombiano vive en el orden de 10^12, cien veces por debajo. El techo no separa «grande» de «muy grande», ataja lo imposible. Un techo apretado escondería contratos ciertos, que es el error contrario y peor — y hay una prueba que lo impide si alguien lo aprieta.
  limite: |
    **Este techo NO ataja la errata de los tres ceros.** `$431 340 000 000` es un contrato perfectamente posible; solo se sabe que es errata comparándolo con el presupuesto del mismo proceso. Queda escrito en una prueba con ese nombre para que nadie crea que la guarda cubre más de lo que cubre. Esa segunda familia se busca aparte, y todavía no está hecha.
  leccion: |
    Se encontró **buscando otra cosa**, y llevaba días publicándose. Es del mismo tipo que el `<meta charset>` que faltaba: **un defecto que no falla**. El número sale, se lee, y está mal.

    Y es exactamente el mismo daño que una alerta inventada, por otra puerta: un total falso con la cara de Vigía le cuesta a alguien su reputación igual que una acusación, y tampoco hay forma de devolvérsela.

- source_spec: `ciclo-diario.ps1`
  summary: EL CICLO NO APLICABA LAS MIGRACIONES, y eso convertía cada columna nueva en una bomba de tiempo.
  evidence: Hasta la 009, las migraciones se aplicaban a mano o de rebote, dentro de scripts de otras historias como `uniones.ps1`. Al añadir `contrato.valor_fuera_de_escala`, el código y las consultas la daban por existente y la base del usuario no la tenía: `panel.sql` habría fallado en la primera corrida después de actualizar el repositorio.
  fix: El Ciclo aplica **todas** las migraciones en orden, en cada corrida, como paso 0 de 5. Todas son idempotentes (`IF NOT EXISTS`), así que reaplicarlas no cuesta nada, y a cambio el repositorio y la base no se pueden separar sin que el Ciclo lo arregle solo.

- source_spec: `medir-valores-imposibles.sql` · CORRECCIÓN DE UNA AFIRMACIÓN MÍA
  summary: DIJE «la fuente publica valores imposibles y hasta hoy los estábamos sumando». **La segunda mitad era falsa.** Medido sobre los 117 470 contratos reales: **cero** fuera de escala. El Panel nunca estuvo envenenado.
  evidence: |
    Los valores imposibles —el proceso de $8 054 481 856 630 300 y los cinco del mismo número con tres ceros de más— viven en `p6dx-8zbt`, la capa de **procesos**, en el campo `valor_total_adjudicacion`. El Panel suma `jbjy-vk9h`, la capa de **contratos**, y ahí no hay ninguno: `valor_fuera_de_escala` marca 0 de 117 470, y el mayor contrato real es $1 566 000 000 000 de la Fuerza Aeroespacial Colombiana, que cabe holgadamente.
  leccion: |
    **Inferí de una capa a la otra sin comprobarlo, y lo dije como un hecho.** Es exactamente el error de la afirmación de los «85 nombres de municipio» y el de «Colombia tiene 18 festivos siempre»: una conclusión razonable que nadie había medido, escrita con la seguridad de una que sí.

    Que el proyecto se sostenga en que los números sean ciertos incluye —sobre todo— los números con los que yo justifico el trabajo. Una alarma exagerada gasta la credibilidad igual que una alerta inventada.
  decision: |
    **La guarda se queda igual, y no por terquedad.** No es que atrape algo hoy: es que la errata está probada en la fuente, y nada impide que el mismo diligenciamiento aparezca mañana en la capa de contratos. Una guarda que atrapa cero es una guarda que funciona; el momento de ponerla es antes, no después de publicar el total equivocado.

    Lo que sí cambia es cómo se cuenta: no es «tapamos un agujero por el que ya nos entraba agua», es «pusimos la tapa antes de que entrara».
  pendiente: La capa `proceso` normalizada no tiene columnas de valor todavía, así que ahí no hay nada que guardar. Cuando una historia futura normalice `precio_base` y `valor_total_adjudicacion`, la guarda tiene que ir con ella en la misma migración — ahí sí hay 119 casos esperando.

- source_spec: `_bmad-output/planning-artifacts/epics.md` (historia 4.3)
  summary: LA PRIMERA MEDICIÓN QUE SOBREVIVE. La concentración por proveedor **no es la norma**: exigiendo cinco contratos por entidad, la mediana de lo que se lleva el mayor proveedor es **29 %**, y solo el **2,1 %** de las entidades pasa del 90 %.
  evidence: |
    Sobre 116 428 contratos con identidad de proveedor real y 2 173 entidades:

    | Mínimo de contratos | Entidades | Mediana del mayor | p90 | Con ≥90 % |
    |---|---|---|---|---|
    | 1 | 2 173 | 0,449 | **1,000** | **458** |
    | **5** | **1 418** | **0,293** | **0,682** | **30** |
    | 10 | 1 159 | 0,269 | 0,642 | 18 |
    | 30 | 624 | 0,221 | 0,585 | 7 |
    | 100 | 224 | 0,173 | 0,507 | 3 |

    **La trampa que se predijo existe y es enorme, y se puede quitar sin pagar nada.** Sin mínimo, el p90 es 1,000 y hay 458 entidades al 100 %: son las 755 entidades con cuatro contratos o menos, que por aritmética no pueden tener otra cosa. Pero esas 755 entidades son 1 377 de 116 428 contratos y $602 mil millones de $11,0 billones — **excluirlas no esconde nada**.

    Exigir cinco contratos no es elegir un umbral por el tamaño de la cola: es **quitar un artefacto aritmético conocido**. Esa es toda la diferencia con el «20 visualizaciones» que mató a la 2.4.
  limite: |
    **DOS límites, y el segundo bloquea la historia.**

    1. 410 contratos de unión temporal sin documento —**$1,91 billones, el 14,8 % del valor**— tienen identidad provisional propia y son invisibles para cualquier medida de concentración. Va en cada informe.

    2. **La ventana es de 33 días, y la concentración es un fenómeno de tiempo.** Una entidad con seis contratos en agosto, cinco al mismo proveedor, puede ser normal vista sobre un año. Los 30 del corte son una foto, no una serie. Publicar esa lista hoy sería señalar a alguien con evidencia de un mes: el mismo error de las tres banderas muertas, al revés.
  decision: |
    **No se construye la Regla todavía, y tampoco se lista a nadie.** Primero se trae historia: `EJECUTAR-HISTORIA.bat` ingiere seis meses hacia atrás, mes a mes, sin tocar la marca de agua del ciclo diario. Después se vuelve a medir. Si la forma aguanta con seis meses, la 4.3 se escribe con el número; si se aplana, se descarta como las otras.
  otro_hallazgo: |
    **La otra cara NO sirve, y conviene tenerlo escrito.** 105 196 de 108 714 proveedores (96,8 %) le facturan a UNA sola entidad, y solo tres a treinta o más. Pero los de más alcance son Aseguradora Solidaria (72 entidades), La Previsora (61), ICONTEC (31), Servicios Postales Nacionales (23), Compensar y la Universidad Nacional. Una bandera de «proveedor con muchas entidades» marcaría al sector asegurador y al que certifica normas técnicas. **La dirección útil es la entidad, no el proveedor.**

- source_spec: `tests/test_escala.py` (el límite documentado de la guarda 1e14) · `medir-erratas.sql`
  summary: LA ERRATA ×10ⁿ YA TIENE DETECTOR, Y LA ENCONTRÓ EL USUARIO ANTES QUE NOSOTROS. El 2026-09-11 el Panel encabezaba «Contratos mayores» con la ALCALDÍA MUNICIPAL DE TIPACOQUE —municipio de unos 3.000 habitantes— firmando $431.340.000.000 con una fundación. El presupuesto del proceso: $431.340.000. El mismo número con tres ceros de más.
  evidence: |
    La guarda de valores imposibles (migración 009, techo 1e14) **no lo atajó, y está escrito desde antes que nunca podría**:

    ```python
    def test_el_mismo_numero_con_tres_ceros_de_mas_todavia_cabe(self):
        assert not fuera_de_escala(Decimal("431340000000"))
    ```

    Tener el límite documentado no impidió que la fila saliera desnuda en dos páginas. **Un límite escrito en una prueba no es una guarda.** La lección es esa, y vale más que el detector.

    La firma que sí distingue la tecla del sobrecosto es la **proporción**: adjudicado ÷ presupuesto del propio proceso cae EXACTAMENTE sobre una potencia de diez. Un sobrecosto real da 2,3 ó 12,4; una tecla da 1.000,000. `medir-erratas.sql` mide primero cuántos procesos caen en cada orden de magnitud —el fondo antes que nada, como en las tres banderas muertas— y solo después lista los que son potencia exacta.

    La segunda prueba no necesita proceso enlazado: el contrato contra la **mediana de su propia entidad**, con mínimo de 5 contratos. Sobre datos de forma real, Tipacoque sale a 19.696 veces la mediana de su alcaldía.
  hecho: |
    · `medir-erratas.sql` + `erratas.ps1` + `EJECUTAR-erratas.bat` — la medición, con las dos pruebas y el cálculo de cuánto valor arrastran las sospechosas.
    · `revision.sql` sección `erratas_x1000` y `conteo_erratas`, y la tabla nueva **arriba del todo** en `revision.html`: quien abra la página ve el desmentido antes que la cifra.
    · `panel.sql` `contratos_mayores` ahora trae `errata_probable` y `valor_probable`; `panel.py` marca la fila y escribe la nota. **La fila no se saca de la tabla**: sacarla sería corregir la fuente a ojo.
    · `vigia/revision.py` grita el conteo por consola —y por tanto sale en la corrida de `ciclo-diario.ps1`, que es quien lo llama—, igual que con los valores imposibles pero con el motivo contrario: estos **sí están dentro de todos los totales**, porque su valor cabe en la realidad.
  pendiente: |
    **Falta el número real.** Todo lo anterior se probó contra datos sintéticos con la forma de los reales. El que decide qué pasa después es el porcentaje de la sección 7 de `medir-erratas.sql`: cuánto del valor de la ventana lo mueven las sospechosas.

    Si es apreciable, hay que decidir —y es una decisión, no un detalle técnico— si `boletin.sql` publica totales con esas cifras dentro. Marcarlas en una página de escritorio y publicarlas en un total sin marca sería lo peor de los dos mundos.

- source_spec: idea del usuario, 2026-09-11 · `medir-nominas-paralelas.sql`
  summary: NÓMINAS PARALELAS. La misma persona con varios contratos abiertos AL MISMO TIEMPO, en entidades distintas. Es la medición que justifica guardar la cédula completa en la base.
  evidence: |
    Yo argumenté que las cédulas aportaban poco: de los 23 contratos que el usuario pegó, dos NIT movían el 99,7 % del dinero y veintiuna cédulas el 0,3 %. **El argumento era correcto y estaba mirando la variable equivocada.** En una nómina paralela el valor de cada contrato es pequeño a propósito —prestación de servicios, quince o veinte millones— y lo que no es pequeño es el patrón. Eso no se ve sumando plata; se ve contando solapamientos.

    La medición cuenta traslapes de rango de fechas, no contratos por año: dos contratos consecutivos —enero a junio, julio a diciembre— son una renovación, no simultaneidad, y no deben contarse. Hay una prueba negativa explícita para ese caso.
  limite: |
    **Tener dos contratos a la vez no es ilegal ni irregular.** Un profesional independiente con dos entidades es legal y común. La incompatibilidad depende del régimen y de la dedicación pactada, **que SECOP no publica**. De aquí no sale una acusación: sale un conteo.

    Y la ventana pesa igual que en la 4.3: con 33 días de datos, «cuatro contratos simultáneos» significa mucho menos que con un año.
  pendiente: |
    Correr `EJECUTAR-nominas-paralelas.bat` sobre datos reales y leer la sección 5. Si el traslape entre entidades distintas resulta ser la norma, la historia se cierra como se cerraron la 2.4 y la 4.2. Si es delgado, hay una cifra publicable **sin nombrar a nadie**: «N personas tuvieron contratos simultáneos con tres o más entidades».
