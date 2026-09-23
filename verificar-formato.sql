-- ¿EL CAMBIO DEL 22 DE SEPTIEMBRE FUE SOLO DE FORMATO? SOLO LECTURA.
--
--     psql -f verificar-formato.sql
--
-- EL HECHO. El 2026-09-22 la fuente devolvió TODOS los contratos con el
-- contenido cambiado: 139.172 vistos, 139.172 insertados, cero duplicados.
-- `que-cambio-hoy.sql` mostró qué campos cambiaron: los trece campos de plata
-- pasaron de «0» a «0.000000» (o a cadena vacía). Eso parece un cambio de
-- formato de la fuente, no de los datos.
--
-- PARECER NO BASTA. Si además cambió alguna cifra, el sitio estaría publicando
-- valores nuevos sin que nadie lo hubiera notado. Esto compara, para una
-- muestra de contratos, la ÚLTIMA versión contra la ANTERIOR, campo por campo,
-- y separa dos cosas:
--
--   iguales_como_numero : «0» -> «0.000000». Mismo número, otra escritura.
--   cambio_de_verdad    : el número cambió. Si esto no es cero, hay que mirar.
--
-- Se cuenta solo sobre los campos de plata; el resto ya lo listó la otra
-- consulta. `to_number` no sirve aquí: basta con el cast a numeric, que acepta
-- las dos escrituras, y con descartar antes lo que no sea un número.

\set ON_ERROR_STOP on
SET work_mem = '256MB';

WITH campos(campo) AS (VALUES
  ('valor_del_contrato'), ('valor_pagado'), ('valor_facturado'),
  ('valor_pendiente_de_pago'), ('valor_pendiente_de_ejecucion'),
  ('valor_pendiente_de'), ('valor_amortizado'), ('valor_de_pago_adelantado'),
  ('recursos_propios'), ('recursos_de_credito'),
  ('sistema_general_de_regal_as'), ('sistema_general_de_participaciones'),
  ('presupuesto_general_de_la_nacion_pgn'),
  ('recursos_propios_alcald_as_gobernaciones_y_resguardos_ind_genas_')
),
ultima_corrida AS (
  SELECT max(consultado_en)::date AS dia FROM crudo_registro WHERE dataset = 'contratos'
),
muestra AS (
  SELECT r.id_fila_fuente
  FROM crudo_registro r, ultima_corrida u
  WHERE r.dataset = 'contratos' AND r.consultado_en >= u.dia
  LIMIT 5000
),
versiones AS (
  SELECT r.id_fila_fuente, r.contenido,
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
comparado AS (
  SELECT p.id_fila_fuente, c.campo,
         nullif(trim(p.antes ->> c.campo), '') AS t_antes,
         nullif(trim(p.hoy   ->> c.campo), '') AS t_hoy
  FROM pares p CROSS JOIN campos c
  WHERE (p.hoy -> c.campo) IS DISTINCT FROM (p.antes -> c.campo)
),
juzgado AS (
  SELECT campo, t_antes, t_hoy,
         CASE
           WHEN t_antes IS NULL AND t_hoy IS NULL                      THEN 'vacio en ambos'
           -- El vacío va ANTES que las comparaciones numéricas. Si no, la
           -- comparación con NULL da NULL, el CASE cae al ELSE y un campo que
           -- pasó de «0» a vacío se cuenta como «CAMBIO DE VERDAD»: así salieron
           -- 25.348 falsos el 2026-09-22, que verificar-cifras.sql desmintió.
           WHEN t_antes IS NULL OR t_hoy IS NULL                       THEN
             CASE WHEN coalesce(t_antes, t_hoy) ~ '^-?0(\.0+)?$'       THEN 'cero que ahora viene vacio'
                  ELSE 'se vacio un valor: hay que mirarlo' END
           WHEN t_antes !~ '^-?[0-9]+(\.[0-9]+)?$'
             OR t_hoy   !~ '^-?[0-9]+(\.[0-9]+)?$'                     THEN
             CASE WHEN coalesce(t_antes, '0') ~ '^-?0(\.0+)?$'
                   AND coalesce(t_hoy,   '0') ~ '^-?0(\.0+)?$'         THEN 'cero escrito distinto'
                  ELSE 'texto: hay que mirarlo' END
           WHEN t_antes::numeric = t_hoy::numeric                      THEN 'mismo numero'
           ELSE 'CAMBIO DE VERDAD'
         END AS veredicto
  FROM comparado
)
SELECT veredicto, count(*) AS campos, count(DISTINCT campo) AS campos_distintos,
       min(t_antes) AS ejemplo_antes, min(t_hoy) AS ejemplo_hoy
FROM juzgado
GROUP BY veredicto
ORDER BY campos DESC;

-- Y el tamaño del problema: cuánto ocupa guardar una versión nueva de todo.
SELECT (SELECT count(*) FROM crudo_registro WHERE dataset = 'contratos')  AS filas_contratos,
       (SELECT count(*) FROM crudo_registro WHERE dataset = 'procesos')   AS filas_procesos,
       pg_size_pretty(pg_total_relation_size('crudo_registro'))           AS ocupa;
