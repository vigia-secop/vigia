-- ¿POR QUE HOY SOLO ENTRARON 17 CONTRATOS? SOLO LECTURA.
--
--     psql -f por-que-17.sql
--
-- EL HECHO. El 2026-09-23, con la misma ventana de 45 dias de siempre, la
-- ingesta de contratos vio 17 registros. El 22 fueron 139.172 y el 20,
-- 144.889. Ademas aparecieron dos campos nuevos en la fuente
-- (`criterios_de_sostenibilidad_ambiental`,
-- `requisitos_ambientales_en_las_especificaciones_t_cnicas`) y el 22 habian
-- cambiado de formato todos los campos de plata. Las tres cosas juntas huelen
-- a una republicacion del dataset de contratos con esquema nuevo.
--
-- LA SOSPECHA CONCRETA. El filtro que se manda a la fuente es
--
--     fecha_de_firma >= '2026-08-08T00:00:00.000'
--
-- Si la fuente cambio como escribe esa fecha —de «2026-08-08T00:00:00.000» a
-- «2026-08-08», por ejemplo— la comparacion deja de traer lo que traia, sin
-- que nada falle: la API responde 200 y devuelve casi nada. Un error que no
-- se ve es peor que uno que grita.
--
-- Esto no puede preguntarselo a la fuente (eso lo hace la ingesta); mira lo
-- que YA esta guardado, que es donde quedo la huella de las dos versiones.

\set ON_ERROR_STOP on
SET work_mem = '256MB';

-- 1. Cuantas filas entraron por dia, y con que forma venia la fecha de firma.
--    Si la longitud del texto cambia entre el 22 y el 23, ahi esta la causa.
SELECT consultado_en::date                                   AS dia,
       count(*)                                              AS filas,
       length(contenido->>'fecha_de_firma')                  AS largo_fecha,
       min(contenido->>'fecha_de_firma')                      AS ejemplo_menor,
       max(contenido->>'fecha_de_firma')                      AS ejemplo_mayor
FROM crudo_registro
WHERE dataset = 'contratos'
  AND consultado_en >= current_date - 4
GROUP BY 1, 3
ORDER BY 1 DESC, 2 DESC;

-- 2. Los 17 de hoy, de cerca: que fecha traen y si son contratos que ya
--    estaban. Si son de firma reciente y nada mas, la fuente simplemente
--    dejo de devolver lo viejo.
SELECT contenido->>'fecha_de_firma'  AS fecha_de_firma,
       contenido->>'estado_contrato' AS estado,
       left(contenido->>'nombre_entidad', 40) AS entidad,
       id_fila_fuente
FROM crudo_registro
WHERE dataset = 'contratos'
  AND consultado_en >= current_date
ORDER BY 1
LIMIT 20;

-- 3. Los dos campos nuevos: ¿vienen llenos o vacios? Un campo nuevo vacio es
--    ruido; uno lleno es informacion que el esquema todavia no conoce.
SELECT count(*)                                                      AS filas_de_hoy,
       count(contenido->'criterios_de_sostenibilidad_ambiental')      AS con_criterios,
       count(contenido->'requisitos_ambientales_en_las_especificaciones_t_cnicas') AS con_requisitos,
       min(contenido->>'criterios_de_sostenibilidad_ambiental')       AS ejemplo_criterios
FROM crudo_registro
WHERE dataset = 'contratos' AND consultado_en >= current_date;

-- 4. Hasta que fecha de firma llega lo que tenemos. Si el maximo se quedo en
--    el 22, hoy no entro nada nuevo de verdad.
SELECT max(contenido->>'fecha_de_firma') AS firma_mas_nueva_guardada,
       count(*)                          AS contratos_en_crudo
FROM crudo_registro
WHERE dataset = 'contratos';
