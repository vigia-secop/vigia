-- ¿EL PRESUPUESTO ES UN PRESUPUESTO, O ES EL RESULTADO ESCRITO ANTES? SOLO LECTURA.
--
--     psql -f medir-precio-base.sql
--
-- DE DÓNDE SALE ESTA PREGUNTA. La medición del 2026-09-06 encontró que el
-- **62,4 %** de los procesos adjudicados adjudican entre el 99,90 % y el
-- 100 % de su `precio_base`, con mediana exactamente 1,0000. En contratación
-- directa con ofertas son el **95 %**.
--
-- Eso admite dos lecturas y NO se pueden distinguir mirando solo la razón:
--
--   (a) En Colombia se adjudica pegado al techo presupuestal, de verdad.
--   (b) `precio_base` no es una estimación previa e independiente: para una
--       parte de los procesos se diligencia CON el valor adjudicado, o se
--       reescribe después de adjudicar.
--
-- Hay un indicio a favor de (b) que no encaja con (a): **119 procesos
-- adjudican POR ENCIMA del presupuesto**. Un techo que se puede pasar no es
-- un techo.
--
-- LA PRUEBA. La capa cruda guarda una fila por cada vez que se vio el
-- registro, con su `consultado_en`. Si para un mismo proceso el `precio_base`
-- CAMBIA entre dos consultas —y sobre todo si termina igual al valor
-- adjudicado— entonces (b) está probado y la Regla 4.2 no se puede construir
-- sobre este campo.
--
-- Si en cambio `precio_base` nunca se mueve, (b) queda descartado por este
-- camino y la razón mide algo del mundo.
--
-- Esta es exactamente la clase de pregunta para la que existe la capa cruda:
-- no es un respaldo, es la única forma de saber si un campo se reescribe.

\pset border 2
\pset numericlocale on

-- Un proceso puede tener varias adjudicaciones; la llave es el par.
CREATE TEMP TABLE h AS
SELECT contenido->>'id_del_proceso'                           AS proceso,
       coalesce(contenido->>'id_adjudicacion','')             AS adjudicacion,
       consultado_en,
       nullif(contenido->>'precio_base','')::numeric          AS base,
       nullif(contenido->>'valor_total_adjudicacion','')::numeric AS adjudicado,
       contenido->>'adjudicado'                               AS esta_adjudicado
FROM crudo_registro
WHERE dataset = 'procesos'
  AND nullif(contenido->>'precio_base','') IS NOT NULL;

-- 1. ¿CUÁNTOS PROCESOS TIENEN MÁS DE UNA FOTO? Sin dos fotos no hay nada que
--    comparar, y decirlo es parte del resultado.
SELECT count(*)                                        AS pares_proceso_adjudicacion,
       count(*) FILTER (WHERE fotos > 1)               AS con_mas_de_una_foto,
       round(100.0 * count(*) FILTER (WHERE fotos > 1)
             / nullif(count(*), 0), 1)                 AS pct
FROM (SELECT proceso, adjudicacion, count(*) AS fotos
      FROM h GROUP BY 1, 2) t;

-- 2. DE LOS QUE TIENEN VARIAS FOTOS, ¿A CUÁNTOS SE LES MOVIÓ EL PRECIO BASE?
WITH v AS (
    SELECT proceso, adjudicacion,
           count(DISTINCT base)                     AS valores_distintos,
           min(base)                                AS menor,
           max(base)                                AS mayor,
           count(*)                                 AS fotos
    FROM h GROUP BY 1, 2 HAVING count(*) > 1
)
SELECT count(*)                                        AS comparables,
       count(*) FILTER (WHERE valores_distintos > 1)   AS cambio_el_precio_base,
       round(100.0 * count(*) FILTER (WHERE valores_distintos > 1)
             / nullif(count(*), 0), 1)                 AS pct,
       count(*) FILTER (WHERE mayor > menor)           AS subio,
       count(*) FILTER (WHERE menor < mayor AND mayor / nullif(menor,0) > 2)
                                                       AS mas_que_duplico
FROM v;

-- 3. LA PRUEBA DE FUEGO. De los que cambiaron, ¿el ÚLTIMO valor del
--    `precio_base` acabó siendo exactamente el valor adjudicado? Si sí, el
--    campo se está reescribiendo con el resultado y la lectura (b) queda
--    probada.
WITH ultimos AS (
    SELECT DISTINCT ON (proceso, adjudicacion)
           proceso, adjudicacion, base, adjudicado
    FROM h
    ORDER BY proceso, adjudicacion, consultado_en DESC
), cambiaron AS (
    SELECT proceso, adjudicacion FROM h
    GROUP BY 1, 2 HAVING count(*) > 1 AND count(DISTINCT base) > 1
)
SELECT count(*)                                                   AS cambiaron,
       count(*) FILTER (WHERE u.base = u.adjudicado)              AS terminaron_igual_al_adjudicado,
       round(100.0 * count(*) FILTER (WHERE u.base = u.adjudicado)
             / nullif(count(*), 0), 1)                            AS pct
FROM ultimos u JOIN cambiaron c USING (proceso, adjudicacion);

-- 4. QUINCE CASOS CON NOMBRE, para poder ir a mirarlos al SECOP.
WITH cambiaron AS (
    SELECT proceso, adjudicacion, min(base) AS primer_base, max(base) AS ultimo_base,
           count(*) AS fotos
    FROM h GROUP BY 1, 2 HAVING count(*) > 1 AND count(DISTINCT base) > 1
)
SELECT c.proceso, c.fotos, c.primer_base, c.ultimo_base,
       u.adjudicado,
       (u.base = u.adjudicado) AS base_final_igual_al_adjudicado
FROM cambiaron c
JOIN (SELECT DISTINCT ON (proceso, adjudicacion) proceso, adjudicacion, base, adjudicado
      FROM h ORDER BY proceso, adjudicacion, consultado_en DESC) u
  USING (proceso, adjudicacion)
ORDER BY u.adjudicado DESC NULLS LAST
LIMIT 15;

DROP TABLE h;
