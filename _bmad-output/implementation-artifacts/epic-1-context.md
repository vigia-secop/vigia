# Epic 1 Context: Ver el SECOP sin ahogarse

<!-- Compilado desde los artefactos de planeación. Edítalo libremente. Regenéralo con compile-epic-context si cambian los documentos de planeación. -->

## Goal

Al terminar la épica, el equipo consulta Procesos y Contratos del SECOP en un esquema unificado —con territorio y proveedor resueltos— sin tocar la API a mano. Es la base de todo lo demás y ya entrega valor por sí sola: responde en segundos preguntas de contratación que hoy cuestan media hora de trabajo manual. Nada del motor de reglas, la revisión ni la publicación puede construirse antes que esto, porque todas esas capas leen de aquí.

## Stories

- Historia 1.1: Traer datos del SECOP y guardarlos crudos
- Historia 1.2: Ingesta incremental con marca de agua por dataset
- Historia 1.3: Validación de esquema que falla ruidosamente
- Historia 1.4: Esquema unificado y cruce proceso–contrato
- Historia 1.5: Identidad de proveedor normalizada
- Historia 1.6: Mapeo territorial a DIVIPOLA

## Requirements & Constraints

- La ingesta incorpora registros nuevos o modificados sin reprocesar el histórico completo. Una ejecución que no encuentra nada nuevo termina sin error y queda registrada como ejecución vacía, distinguible de un fallo.
- Reingerir un registro sin cambios no produce duplicado. Un fallo a mitad de ejecución deja el estado consistente: el lote entró completo o no entró.
- Los registros ingeridos se conservan históricamente. La serie es el activo; nunca se sobrescribe con la foto más reciente.
- Toda consulta a la fuente registra su fecha y hora junto al dato. Es requisito de trazabilidad del Expediente, no telemetría.
- Un fallo de validación de esquema detiene la ejecución y notifica nombrando el campo faltante. Nunca se degrada a nulos silenciosos. Un campo nuevo inesperado no detiene nada: se registra como novedad para revisión.
- Contratos y Procesos se enlazan por una llave de cruce. Lo que no cruza se marca huérfano y sigue consultable; nunca se descarta en silencio. El porcentaje de huérfanos se reporta por ejecución.
- El territorio se resuelve contra una tabla de correspondencias versionada. Lo no resuelto va a una cola de no resueltos; nunca se asigna un código por aproximación o similitud.
- La identidad de Proveedor se deriva de una forma canónica del documento; las variantes de nombre quedan registradas y consultables.
- Una ejecución diaria del universo nacional debe caber sin intervención manual. Se mide antes de optimizar.
- Los campos de personas naturales que trae la fuente son datos personales: acceso restringido al equipo y nunca en superficies publicadas.

## Technical Decisions

- **Pipeline por lotes con estado versionado**, no un servicio en tiempo real. Toda la ingesta es una secuencia de transformaciones idempotentes sobre almacenamiento inmutable.
- **Tres capas de almacenamiento**: cruda (la respuesta de la fuente tal como llegó, con fecha de consulta, nunca se modifica), normalizada (esquema unificado, territorio e identidades resueltos) y derivada (aguas abajo de esta épica). Reprocesar significa reconstruir normalizado desde crudo. El crudo es la única fuente de verdad y el seguro contra un cambio de esquema en la fuente.
- **PostgreSQL** como almacén único: crudo en JSONB, normalizado en tablas tipadas. **Python** para todo el pipeline.
- **La marca de agua es por dataset**, persistida y auditable. Cada ejecución registra cursor de entrada, cursor de salida, registros vistos, nuevos, huérfanos y errores. Una ejecución vacía es un registro válido.
- **El mapeo territorial es una tabla versionada con procedencia por entrada**, no una función con heurística.
- **Los campos de persona natural llevan una marca de sensibilidad en la definición del esquema**, que aguas abajo alimenta el filtro de publicación. La marca se declara aquí, en la capa de esquema.
- **Vocabulario obligatorio**: los términos del glosario son los nombres de tablas, tipos y funciones. Proceso, Contrato, Entidad, Proveedor, Ciclo, Recorte. Sin sinónimos ni traducciones al inglés para conceptos del dominio.
- Fechas en ISO 8601 y UTC en almacenamiento. Valores monetarios en pesos, enteros, sin decimales; la fuente trae varios campos de valor y no se mezclan.

## Fuentes y hechos verificados de la API

Verificado contra `datos.gov.co` el 2026-09-02 — corrige dos supuestos del documento de investigación:

- Datasets Socrata públicos sin credenciales: Contratos `jbjy-vk9h`, Procesos `p6dx-8zbt`. Filtros y paginación por `$where`, `$select`, `$limit`, `$offset`.
- **La paginación no tiene orden implícito.** Socrata documenta que paginar sin cláusula `$order` puede devolver resultados inconsistentes entre páginas; el mínimo seguro es `$order=:id`.
- **Los campos nulos no vienen como `null`: la clave simplemente no aparece** en el registro. Un campo ausente no es evidencia de cambio de esquema, y contarlo como tal produciría falsos positivos en la validación.
- Cada registro trae campos de sistema disponibles con `$select=:*,*`: `:id` (identificador estable de fila), `:created_at`, `:updated_at`, `:version`.
- `urlproceso` llega como objeto anidado `{"url": "..."}`, no como cadena.
- Los nombres reales de los campos de adjudicación en Procesos son `adjudicado`, `valor_total_adjudicacion`, `nit_del_proveedor_adjudicado` y `estado_del_procedimiento` — no los que nombra el documento de investigación (`fecha_de_adjudicacion`, `valor_del_contrato_adjudicado`, `nit_del_proveedor_ganador`, `cantidad_de_ganadores`, que no existen). Afecta a las épicas 2 y 4, no a la 1.

## Cross-Story Dependencies

- 1.1 habilita todo lo demás: sin capa cruda no hay qué normalizar ni qué reprocesar.
- 1.2 depende de que 1.1 haya definido la identidad del registro crudo y el registro de ejecución.
- 1.3 se apoya en la respuesta cruda de 1.1 para comparar el conjunto de campos esperados contra el recibido.
- 1.4, 1.5 y 1.6 leen de la capa cruda y escriben la normalizada; entre ellas, 1.4 fija el esquema unificado que 1.5 y 1.6 enriquecen.
- Las épicas 2 a 6 dependen íntegramente de esta.
