-- ¿SE PUEDE MEDIR «ADJUDICACIÓN PEGADA AL PRESUPUESTO»? SOLO LECTURA.
--
--     psql -f medir-presupuesto.sql
--
-- POR QUÉ ESTA HISTORIA Y NO OTRA. La 2.4 murió porque su umbral había que
-- inventarlo: nada en los datos decía que 20 visualizaciones fueran el corte,
-- y se elegía porque daba un número que cabía en una cola. Esta no tiene ese
-- problema. La cantidad es
--
--     valor adjudicado ÷ presupuesto oficial
--
-- y la zona que interesa está en **1,00 exacto**. Ese número sale del mundo
-- —es el techo del presupuesto— y no de nosotros. Un proceso que adjudica al
-- 99,8 % del presupuesto no es igual que uno que adjudica al 70 %, y la
-- diferencia no depende de ninguna elección nuestra.
--
-- PERO PRIMERO HAY QUE SABER SI EL CAMPO LLEGA. Esta consulta NO construye la
-- Regla. Hace dos preguntas, en este orden, porque la segunda no significa
-- nada sin la primera:
--
--   1. ¿Qué campo trae el presupuesto y en qué porcentaje viene poblado?
--   2. Si viene, ¿cómo se reparte la razón adjudicado/presupuesto?
--
-- Si el campo llega en el 25 % de los casos —como pasó con
-- `proveedores_invitados`— la historia se para aquí y se dice, en vez de
-- construir una Regla sobre un cuarto del país y presentarla como si midiera
-- el país.

\pset border 2
\pset numericlocale on

-- Una sola fila por (proceso, adjudicación), la más reciente. Es el mismo
-- destilado que usan las otras mediciones.
CREATE TEMP TABLE q AS
SELECT contenido
FROM (
    SELECT DISTINCT ON (contenido->>'id_del_proceso', contenido->>'id_adjudicacion')
           contenido
    FROM crudo_registro WHERE dataset = 'procesos'
    ORDER BY contenido->>'id_del_proceso', contenido->>'id_adjudicacion',
             consultado_en DESC
) u
WHERE contenido->>'adjudicado' = 'Si';

-- 1. CENSO DE CAMPOS. Todo campo cuyo nombre huela a plata, con cuántos
--    procesos adjudicados lo traen con un número mayor que cero. No se
--    adivina el nombre: se pregunta.
SELECT k AS campo,
       count(*)                                                   AS lo_traen,
       count(*) FILTER (WHERE nullif(v,'') IS NOT NULL
                          AND v ~ '^[0-9.]+$' AND v::numeric > 0) AS con_numero,
       round(100.0 * count(*) FILTER (WHERE nullif(v,'') IS NOT NULL
                          AND v ~ '^[0-9.]+$' AND v::numeric > 0)
             / nullif((SELECT count(*) FROM q), 0), 1)                       AS pct_del_total
FROM q, jsonb_each_text(contenido) AS e(k, v)
WHERE k ~* 'precio|presupu|valor|cuantia|estimad'
GROUP BY k
HAVING count(*) > 0
ORDER BY con_numero DESC;

-- 2. LA RAZÓN. Solo sobre los procesos donde los dos números llegan. La
--    columna `sin_los_dos` es tan importante como el resto: dice sobre qué
--    parte del universo se está hablando.
WITH r AS (
    SELECT contenido->>'modalidad_de_contratacion' AS modalidad,
           nullif(contenido->>'precio_base','')::numeric            AS base,
           nullif(contenido->>'valor_total_adjudicacion','')::numeric AS adjudicado
    FROM q
)
SELECT count(*)                                            AS adjudicados,
       count(*) FILTER (WHERE base IS NULL OR base = 0
                           OR adjudicado IS NULL)          AS sin_los_dos,
       count(*) FILTER (WHERE base > 0 AND adjudicado > 0) AS medibles,
       round((percentile_cont(0.25) WITHIN GROUP (ORDER BY adjudicado / base)
             FILTER (WHERE base > 0 AND adjudicado > 0))::numeric, 4) AS p25,
       round((percentile_cont(0.50) WITHIN GROUP (ORDER BY adjudicado / base)
             FILTER (WHERE base > 0 AND adjudicado > 0))::numeric, 4) AS mediana,
       round((percentile_cont(0.90) WITHIN GROUP (ORDER BY adjudicado / base)
             FILTER (WHERE base > 0 AND adjudicado > 0))::numeric, 4) AS p90,
       round((percentile_cont(0.99) WITHIN GROUP (ORDER BY adjudicado / base)
             FILTER (WHERE base > 0 AND adjudicado > 0))::numeric, 4) AS p99
FROM r;

-- 3. LA FORMA DE LA COLA ALTA. Cuántos procesos caen en cada franja pegada al
--    presupuesto. Si «entre 99 % y 100 %» resulta ser la mitad del país,
--    estamos otra vez ante la norma y esta historia también se cae. Si es una
--    franja delgada, ahí hay algo que mirar.
WITH r AS (
    SELECT nullif(contenido->>'precio_base','')::numeric            AS base,
           nullif(contenido->>'valor_total_adjudicacion','')::numeric AS adjudicado
    FROM q
), z AS (
    SELECT adjudicado / base AS razon FROM r WHERE base > 0 AND adjudicado > 0
)
SELECT CASE
         WHEN razon > 1.0000 THEN 'e. por ENCIMA del presupuesto'
         WHEN razon >= 0.9990 THEN 'd. 99,90 % a 100 %'
         WHEN razon >= 0.9900 THEN 'c. 99,0 % a 99,9 %'
         WHEN razon >= 0.9500 THEN 'b. 95 % a 99 %'
         ELSE                      'a. por debajo del 95 %'
       END                                          AS franja,
       count(*)                                     AS procesos,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
FROM z GROUP BY 1 ORDER BY 1;

-- 4. LO MISMO POR MODALIDAD, que es la lección que dejó la 2.4: un umbral
--    global puede describir la norma en unas modalidades y la excepción en
--    otras, y promediarlas esconde las dos.
WITH r AS (
    SELECT contenido->>'modalidad_de_contratacion' AS modalidad,
           nullif(contenido->>'precio_base','')::numeric            AS base,
           nullif(contenido->>'valor_total_adjudicacion','')::numeric AS adjudicado
    FROM q
)
SELECT modalidad,
       count(*) FILTER (WHERE base > 0 AND adjudicado > 0)          AS medibles,
       round((percentile_cont(0.50) WITHIN GROUP (ORDER BY adjudicado / base)
             FILTER (WHERE base > 0 AND adjudicado > 0))::numeric, 4)         AS mediana,
       count(*) FILTER (WHERE base > 0 AND adjudicado / base >= 0.999) AS casi_exacto
FROM r GROUP BY 1
HAVING count(*) FILTER (WHERE base > 0 AND adjudicado > 0) > 0
ORDER BY medibles DESC LIMIT 15;

DROP TABLE q;
