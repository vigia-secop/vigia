-- ¿QUE CAMBIO EN LA FUENTE? SOLO LECTURA.
--
--     psql -f que-cambio-hoy.sql
--
-- EL HECHO. El 2026-09-22 la ingesta de contratos vio 139.172 registros y los
-- insertó TODOS: cero duplicados. El 20 de septiembre, sobre casi los mismos
-- contratos, habían sido 124.345 duplicados de 144.889. Que de un día para otro
-- no se repita ni uno significa que el contenido de TODOS cambió, y el
-- validador de esquema no avisó de campos nuevos.
--
-- Esto lo averigua comparando, para una muestra de contratos, la versión de hoy
-- contra la inmediatamente anterior, campo por campo, y contando qué campos
-- difieren. Si es uno solo y en todos, es un cambio de formato en la fuente.

\set ON_ERROR_STOP on
SET work_mem = '256MB';

WITH ultima_corrida AS (
  SELECT max(consultado_en)::date AS dia FROM crudo_registro WHERE dataset = 'contratos'
),
muestra AS (
  SELECT r.id_fila_fuente
  FROM crudo_registro r, ultima_corrida u
  WHERE r.dataset = 'contratos' AND r.consultado_en >= u.dia
  LIMIT 2000
),
versiones AS (
  SELECT r.id_fila_fuente, r.contenido, r.consultado_en,
         row_number() OVER (PARTITION BY r.id_fila_fuente ORDER BY r.consultado_en DESC) AS n
  FROM crudo_registro r
  WHERE r.dataset = 'contratos'
    AND r.id_fila_fuente IN (SELECT id_fila_fuente FROM muestra)
),
pares AS (
  SELECT a.id_fila_fuente, a.contenido AS hoy, b.contenido AS antes
  FROM versiones a JOIN versiones b USING (id_fila_fuente)
  WHERE a.n = 1 AND b.n = 2
),
diferencias AS (
  SELECT p.id_fila_fuente, k AS campo,
         p.antes ->> k AS valor_antes, p.hoy ->> k AS valor_hoy
  FROM pares p,
       LATERAL (SELECT jsonb_object_keys(p.hoy) UNION SELECT jsonb_object_keys(p.antes)) AS ks(k)
  WHERE k NOT LIKE ':%'
    AND (p.hoy -> k) IS DISTINCT FROM (p.antes -> k)
)
SELECT campo,
       count(*)                          AS contratos_con_cambio,
       (SELECT count(*) FROM pares)      AS contratos_comparados,
       min(valor_antes)                  AS ejemplo_antes,
       min(valor_hoy)                    AS ejemplo_hoy
FROM diferencias
GROUP BY campo
ORDER BY contratos_con_cambio DESC
LIMIT 25;
