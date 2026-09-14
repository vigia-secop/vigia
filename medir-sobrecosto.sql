-- LOS 119 QUE ADJUDICAN POR ENCIMA DE SU PROPIO PRESUPUESTO. SOLO LECTURA.
--
--     psql -f medir-sobrecosto.sql
--
-- POR QUÉ ESTOS Y NO OTROS. Dos mediciones seguidas mataron dos banderas por
-- la misma razón: describían la mayoría. El 52,8 % de los competitivos
-- termina con un solo oferente; el 62,4 % de los adjudicados adjudica entre el
-- 99,90 % y el 100 % de su presupuesto. Marcar eso es marcar el país.
--
-- Estos son distintos por dos motivos, y los dos importan:
--
--   1. **Son el 1,1 %.** No la norma: la excepción, medida.
--   2. **No hay umbral que inventar.** «El valor adjudicado supera el precio
--      base publicado» es un hecho categórico, sí o no. No es un percentil
--      elegido, ni un corte escogido porque da una cola de tamaño cómodo. Es
--      la trampa que mató a las dos anteriores, y aquí no existe.
--
-- ANTES DE CONSTRUIR NADA HAY QUE DESCARTAR LA EXPLICACIÓN ABURRIDA. La
-- comprobación del `precio_base` encontró que 56 procesos revisaron su
-- presupuesto al alza ANTES de adjudicar, 6 de ellos más del doble. Si alguno
-- de los 119 es simplemente una foto vieja —el presupuesto subió después y
-- nosotros guardamos el número de antes— entonces no adjudicó por encima de
-- nada, y contarlo sería inventar el caso.
--
-- Esta consulta separa las dos cosas.

\pset border 2
\pset numericlocale on

CREATE TEMP TABLE s AS
SELECT contenido->>'id_del_proceso'                               AS proceso,
       coalesce(contenido->>'id_adjudicacion','')                 AS adjudicacion,
       contenido->>'entidad'                                      AS entidad,
       contenido->>'modalidad_de_contratacion'                    AS modalidad,
       contenido->'urlproceso'->>'url'                            AS enlace,
       consultado_en,
       nullif(contenido->>'precio_base','')::numeric              AS base,
       nullif(contenido->>'valor_total_adjudicacion','')::numeric AS adjudicado
FROM crudo_registro
WHERE dataset = 'procesos' AND contenido->>'adjudicado' = 'Si'
  AND nullif(contenido->>'precio_base','') IS NOT NULL;

-- 1. ¿CUÁNTOS SIGUEN POR ENCIMA MIRANDO SU FOTO MÁS RECIENTE, y cuántos se
--    caen porque en alguna foto posterior el presupuesto ya era mayor?
WITH ultima AS (
    SELECT DISTINCT ON (proceso, adjudicacion) *
    FROM s ORDER BY proceso, adjudicacion, consultado_en DESC
), maxima AS (
    SELECT proceso, adjudicacion, max(base) AS base_mayor_vista
    FROM s GROUP BY 1, 2
)
SELECT count(*) FILTER (WHERE u.adjudicado > u.base)                    AS por_encima_en_la_ultima_foto,
       count(*) FILTER (WHERE u.adjudicado > m.base_mayor_vista)        AS por_encima_de_TODA_base_vista,
       count(*) FILTER (WHERE u.adjudicado > u.base
                          AND u.adjudicado <= m.base_mayor_vista)       AS se_explican_por_foto_vieja
FROM ultima u JOIN maxima m USING (proceso, adjudicacion)
WHERE u.base > 0 AND u.adjudicado > 0;

-- 2. LOS QUE SOBREVIVEN, por cuánto se pasan. Un 0,01 % es redondeo; un 40 %
--    no lo es. La forma de esta columna decide si la Regla lleva un mínimo.
WITH ultima AS (
    SELECT DISTINCT ON (proceso, adjudicacion) *
    FROM s ORDER BY proceso, adjudicacion, consultado_en DESC
), maxima AS (
    SELECT proceso, adjudicacion, max(base) AS base_mayor_vista
    FROM s GROUP BY 1, 2
), vivos AS (
    SELECT u.*, u.adjudicado / u.base AS razon
    FROM ultima u JOIN maxima m USING (proceso, adjudicacion)
    WHERE u.base > 0 AND u.adjudicado > m.base_mayor_vista
)
SELECT CASE
         WHEN razon > 2.00 THEN 'e. mas del doble'
         WHEN razon > 1.20 THEN 'd. entre 20 % y 100 % por encima'
         WHEN razon > 1.05 THEN 'c. entre 5 % y 20 %'
         WHEN razon > 1.01 THEN 'b. entre 1 % y 5 %'
         ELSE                   'a. menos del 1 % (puede ser redondeo)'
       END                                                AS franja,
       count(*)                                           AS procesos,
       sum(adjudicado - base)::numeric(24,0)              AS pesos_por_encima
FROM vivos GROUP BY 1 ORDER BY 1;

-- 3. LOS VEINTE MAYORES, con enlace para ir a mirarlos al SECOP.
WITH ultima AS (
    SELECT DISTINCT ON (proceso, adjudicacion) *
    FROM s ORDER BY proceso, adjudicacion, consultado_en DESC
), maxima AS (
    SELECT proceso, adjudicacion, max(base) AS base_mayor_vista
    FROM s GROUP BY 1, 2
)
SELECT u.proceso, left(u.entidad, 34) AS entidad, left(u.modalidad, 26) AS modalidad,
       u.base, u.adjudicado,
       round(100 * (u.adjudicado / u.base - 1), 1) AS pct_por_encima
FROM ultima u JOIN maxima m USING (proceso, adjudicacion)
WHERE u.base > 0 AND u.adjudicado > m.base_mayor_vista
ORDER BY (u.adjudicado - u.base) DESC
LIMIT 20;

DROP TABLE s;
