-- PERFIL DE CONTRATACION DE UNA ENTIDAD. SOLO LECTURA.
--
--     psql -f perfil-entidad.sql
--
-- QUE ES. Todo lo que el SECOP II publica de una entidad, ordenado en las
-- preguntas que un periodista o un veedor hace primero: cuanto contrata, con
-- quien, por que via, y que cosas se salen del patron.
--
-- QUE NO ES. Una acusacion. Ninguna de estas consultas puede mostrar
-- corrupcion: muestran CONTRATACION. Un proveedor concentrado puede ser el
-- unico del pais que hace ese trabajo; una contratacion directa puede estar
-- perfectamente sustentada en la ley; un contrato de valor raro puede ser un
-- error de digitacion de la entidad. Lo que sale de aqui son preguntas con
-- su enlace a la fuente, para que alguien las conteste. Escribir «corrupcion»
-- donde el dato dice «llama la atencion» es exactamente lo que destruye la
-- credibilidad que hace util a Vigia.
--
-- LA COMPARACION ES OBLIGATORIA. Un numero solo no significa nada: 60 % de
-- contratacion directa es escandaloso o normal segun contra que se compare.
-- Por eso cada medida de la entidad va al lado de la misma medida en el resto
-- de entidades del orden nacional.
--
-- A QUIEN MIRA. Por NIT, no por nombre. El primer intento fue por nombre
-- —«%JURISDICCI_N ESPECIAL PARA LA PAZ%»— y devolvio CERO filas: en el SECOP
-- la Jurisdiccion Especial para la Paz se llama, a secas, «JEP». Si esa
-- consulta se hubiera publicado, habria dicho que la JEP no contrata. El
-- nombre lo escribe cada entidad como quiere; el NIT no.
--
-- QUE PERIODO CUBRE. La base tiene contratos firmados desde el 2026-06-10.
-- Todo lo que sale de aqui es de esos tres meses y medio, no de la historia
-- de la entidad. Decir «lo que ha firmado la JEP» sobre esto seria falso.

\set ON_ERROR_STOP on
SET work_mem = '256MB';

\set nit '901140004'

-- ---------------------------------------------------------------- 1
-- PRIMERO: ¿a quien estamos mirando? Un NIT puede venir escrito con varios
-- nombres distintos. Esto se revisa ANTES de creerle a cualquier cifra.
\echo '== 1. Que entidad es ese NIT =='
SELECT nit_entidad,
       nombre_entidad,
       count(*)                               AS contratos,
       sum(valor)::numeric(24,0)              AS valor_total,
       min(fecha_de_firma)                    AS primera_firma,
       max(fecha_de_firma)                    AS ultima_firma
FROM contrato
WHERE nit_entidad = :'nit'
GROUP BY 1, 2
ORDER BY contratos DESC;

-- ---------------------------------------------------------------- 2
\echo ''
\echo '== 2. Cuanto contrata, mes a mes =='
SELECT to_char(fecha_de_firma, 'YYYY-MM')      AS mes,
       count(*)                                AS contratos,
       sum(valor)::numeric(24,0)               AS valor_total,
       round(avg(valor))::numeric(24,0)        AS valor_promedio,
       max(valor)::numeric(24,0)               AS contrato_mayor
FROM contrato
WHERE nit_entidad = :'nit' AND fecha_de_firma IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC
LIMIT 24;

-- ---------------------------------------------------------------- 3
-- Concentracion. La pregunta no es «quien es el que mas recibe» —siempre hay
-- uno— sino «cuanto del total se lleva el puñado de arriba».
\echo ''
\echo '== 3. Los 20 proveedores con mas plata =='
WITH mios AS (
  SELECT * FROM contrato WHERE nit_entidad = :'nit'
),
total AS (SELECT sum(valor) AS v FROM mios)
SELECT coalesce(proveedor_nombre, '(sin proveedor legible)')       AS proveedor,
       proveedor_tipo || ' ' || left(coalesce(proveedor_numero,''), 3) || '***' AS documento,
       count(*)                                                     AS contratos,
       sum(valor)::numeric(24,0)                                    AS valor_total,
       round(100 * sum(valor) / nullif((SELECT v FROM total), 0), 2) AS pct_del_total,
       min(fecha_de_firma)                                          AS desde,
       max(fecha_de_firma)                                          AS hasta
FROM mios
GROUP BY 1, 2
ORDER BY valor_total DESC NULLS LAST
LIMIT 20;

\echo ''
\echo '== 3b. Que parte del total se lleva el grupo de arriba =='
WITH mios AS (
  SELECT proveedor_numero, valor FROM contrato WHERE nit_entidad = :'nit'
),
por_proveedor AS (
  SELECT proveedor_numero, sum(valor) AS v FROM mios GROUP BY 1
),
ordenados AS (
  SELECT v, row_number() OVER (ORDER BY v DESC NULLS LAST) AS n FROM por_proveedor
)
SELECT (SELECT count(*) FROM por_proveedor)                                    AS proveedores,
       round(100 * (SELECT sum(v) FROM ordenados WHERE n <= 1)
                 / nullif((SELECT sum(v) FROM ordenados), 0), 1)               AS pct_del_primero,
       round(100 * (SELECT sum(v) FROM ordenados WHERE n <= 5)
                 / nullif((SELECT sum(v) FROM ordenados), 0), 1)               AS pct_de_los_5,
       round(100 * (SELECT sum(v) FROM ordenados WHERE n <= 10)
                 / nullif((SELECT sum(v) FROM ordenados), 0), 1)               AS pct_de_los_10;

-- ---------------------------------------------------------------- 4
-- La via de contratacion vive en el crudo, no en la capa normalizada. Se lee
-- la ultima version de cada contrato de esta entidad: son pocos, asi que el
-- filtro por id hace barata la consulta.
\echo ''
\echo '== 4. Por que via contrata, y como se compara =='
WITH mios AS (
  SELECT DISTINCT ON (contenido->>'id_contrato') contenido
  FROM crudo_registro
  WHERE dataset = 'contratos'
    AND contenido->>'nit_entidad' = :'nit'
  ORDER BY contenido->>'id_contrato', consultado_en DESC
),
resumen AS (
  SELECT coalesce(contenido->>'modalidad_de_contratacion', '(sin modalidad)') AS modalidad,
         count(*)                                               AS contratos,
         sum(nullif(contenido->>'valor_del_contrato','')::numeric) AS valor
  FROM mios GROUP BY 1
)
SELECT modalidad, contratos,
       round(100.0 * contratos / sum(contratos) OVER (), 1)  AS pct_contratos,
       valor::numeric(24,0)                                   AS valor,
       round(100 * valor / nullif(sum(valor) OVER (), 0), 1)  AS pct_valor
FROM resumen
ORDER BY valor DESC NULLS LAST;

-- ---------------------------------------------------------------- 5
-- Prestacion de servicios a personas naturales: la «nomina paralela». Tampoco
-- prueba nada —una entidad puede necesitar peritos— pero su peso dice de que
-- esta hecho el gasto.
\echo ''
\echo '== 5. Prestacion de servicios a personas naturales =='
WITH mios AS (
  SELECT DISTINCT ON (contenido->>'id_contrato') contenido
  FROM crudo_registro
  WHERE dataset = 'contratos'
    AND contenido->>'nit_entidad' = :'nit'
  ORDER BY contenido->>'id_contrato', consultado_en DESC
)
SELECT coalesce(contenido->>'tipo_de_contrato', '(sin tipo)')     AS tipo,
       contenido->>'tipodocproveedor'                             AS tipo_documento,
       count(*)                                                   AS contratos,
       sum(nullif(contenido->>'valor_del_contrato','')::numeric)::numeric(24,0) AS valor
FROM mios
GROUP BY 1, 2
ORDER BY contratos DESC
LIMIT 15;

-- ---------------------------------------------------------------- 6
-- Los contratos mas grandes, uno por uno y con su enlace. Esto es lo que se
-- revisa a mano: una cifra agregada no se puede comprobar, un contrato si.
\echo ''
\echo '== 6. Los 25 contratos mas grandes, con enlace =='
WITH mios AS (
  SELECT DISTINCT ON (contenido->>'id_contrato') contenido
  FROM crudo_registro
  WHERE dataset = 'contratos'
    AND contenido->>'nit_entidad' = :'nit'
  ORDER BY contenido->>'id_contrato', consultado_en DESC
)
SELECT left(contenido->>'fecha_de_firma', 10)                     AS firma,
       nullif(contenido->>'valor_del_contrato','')::numeric(24,0) AS valor,
       coalesce(contenido->>'modalidad_de_contratacion','')       AS modalidad,
       left(coalesce(contenido->>'proveedor_adjudicado',''), 45)  AS proveedor,
       left(coalesce(contenido->>'descripcion_del_proceso',''), 90) AS objeto,
       contenido->'urlproceso'->>'url'                            AS enlace
FROM mios
ORDER BY 2 DESC NULLS LAST
LIMIT 25;

-- ---------------------------------------------------------------- 7
-- Contra que se compara. Las mismas medidas en el resto del orden nacional,
-- para que el numero de arriba signifique algo.
\echo ''
\echo '== 7. El resto del orden nacional, para comparar =='
WITH otros AS (
  SELECT DISTINCT ON (contenido->>'id_contrato') contenido
  FROM crudo_registro
  WHERE dataset = 'contratos'
    AND contenido->>'orden' = 'Nacional'
    AND contenido->>'nit_entidad' <> :'nit'
    AND contenido->>'fecha_de_firma' >= '2026-01-01'
  ORDER BY contenido->>'id_contrato', consultado_en DESC
)
SELECT count(*)                                                       AS contratos_2026,
       round(100.0 * count(*) FILTER (
         WHERE contenido->>'modalidad_de_contratacion' ILIKE '%directa%'
       ) / nullif(count(*), 0), 1)                                    AS pct_directa,
       round(100.0 * count(*) FILTER (
         WHERE contenido->>'tipo_de_contrato' ILIKE '%prestaci%servicio%'
       ) / nullif(count(*), 0), 1)                                    AS pct_prestacion_servicios
FROM otros;

\echo ''
\echo '== 7b. Lo mismo, en la entidad mirada =='
WITH mios AS (
  SELECT DISTINCT ON (contenido->>'id_contrato') contenido
  FROM crudo_registro
  WHERE dataset = 'contratos'
    AND contenido->>'nit_entidad' = :'nit'
    AND contenido->>'fecha_de_firma' >= '2026-01-01'
  ORDER BY contenido->>'id_contrato', consultado_en DESC
)
SELECT count(*)                                                       AS contratos_2026,
       round(100.0 * count(*) FILTER (
         WHERE contenido->>'modalidad_de_contratacion' ILIKE '%directa%'
       ) / nullif(count(*), 0), 1)                                    AS pct_directa,
       round(100.0 * count(*) FILTER (
         WHERE contenido->>'tipo_de_contrato' ILIKE '%prestaci%servicio%'
       ) / nullif(count(*), 0), 1)                                    AS pct_prestacion_servicios
FROM mios;
