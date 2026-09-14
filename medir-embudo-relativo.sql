-- La medición que decide si «embudo estrecho» discrimina (§5.4 de la
-- propuesta de cambio del 2026-09-06). SOLO LECTURA.
--
-- LA PREGUNTA. Entre los procesos competitivos adjudicados, ¿los que
-- terminaron con UN solo proveedor recibieron tanta atención como los que
-- terminaron con varios?
--
--   Si las dos distribuciones de visualizaciones se parecen, el embudo
--   relativo tampoco discrimina y la bandera hay que descartarla.
--   Si se separan, el punto donde se separan es el percentil que buscamos.
--
-- Las dos respuestas cierran la historia. La que no sirve es no medirlo.

\pset border 2
\pset numericlocale on

CREATE TEMP TABLE p AS
SELECT contenido->>'modalidad_de_contratacion'                       AS modalidad,
       nullif(contenido->>'visualizaciones_del','')::numeric         AS vistas,
       nullif(contenido->>'proveedores_unicos_con','')::numeric      AS unicos,
       nullif(contenido->>'valor_total_adjudicacion','')::numeric    AS valor
FROM (
    SELECT DISTINCT ON (contenido->>'id_del_proceso', contenido->>'id_adjudicacion')
           contenido
    FROM crudo_registro
    WHERE dataset = 'procesos'
    ORDER BY contenido->>'id_del_proceso', contenido->>'id_adjudicacion',
             consultado_en DESC
) u
WHERE contenido->>'adjudicado' = 'Si'
  AND contenido->>'modalidad_de_contratacion' IN (
      'Licitación pública', 'Licitación pública Obra Publica',
      'Selección Abreviada de Menor Cuantía', 'Selección abreviada subasta inversa',
      'Seleccion Abreviada Menor Cuantia Sin Manifestacion Interes',
      'Concurso de méritos abierto',
      'Enajenación de bienes con sobre cerrado', 'Enajenación de bienes con subasta');

-- 1. LA COMPARACIÓN QUE DECIDE. Si las medianas se parecen, no discrimina.
SELECT CASE WHEN unicos = 1 THEN 'un solo proveedor' ELSE 'varios proveedores' END AS grupo,
       count(*)                                                   AS procesos,
       round(percentile_cont(0.25) WITHIN GROUP (ORDER BY vistas)) AS p25,
       round(percentile_cont(0.50) WITHIN GROUP (ORDER BY vistas)) AS mediana,
       round(percentile_cont(0.75) WITHIN GROUP (ORDER BY vistas)) AS p75,
       round(percentile_cont(0.90) WITHIN GROUP (ORDER BY vistas)) AS p90,
       round(avg(vistas), 1)                                       AS promedio
FROM p WHERE vistas IS NOT NULL AND unicos IS NOT NULL
GROUP BY 1 ORDER BY 1;

-- 2. Lo mismo POR MODALIDAD: el percentil tiene que ser de su modalidad,
--    no del país, igual que el plazo exprés de la 4.5.
SELECT left(modalidad, 38) AS modalidad,
       count(*) FILTER (WHERE unicos = 1)  AS con_uno,
       round(percentile_cont(0.50) WITHIN GROUP (ORDER BY vistas)
             FILTER (WHERE unicos = 1))    AS mediana_con_uno,
       count(*) FILTER (WHERE unicos > 1)  AS con_varios,
       round(percentile_cont(0.50) WITHIN GROUP (ORDER BY vistas)
             FILTER (WHERE unicos > 1))    AS mediana_con_varios
FROM p WHERE vistas IS NOT NULL AND unicos IS NOT NULL
GROUP BY 1 HAVING count(*) FILTER (WHERE unicos > 1) > 0
ORDER BY con_uno DESC;

-- 3. Cuántos quedarían por encima de cada percentil de SU modalidad. Este es
--    el tamaño de la cola para cada opción de umbral, que es lo que hay que
--    tener delante para elegirlo sin inventar.
WITH cortes AS (
    SELECT modalidad,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY vistas) AS c75,
           percentile_cont(0.90) WITHIN GROUP (ORDER BY vistas) AS c90,
           percentile_cont(0.95) WITHIN GROUP (ORDER BY vistas) AS c95
    FROM p WHERE vistas IS NOT NULL GROUP BY 1
)
SELECT count(*) FILTER (WHERE p.unicos = 1)                              AS un_solo_proveedor,
       count(*) FILTER (WHERE p.unicos = 1 AND p.vistas > c.c75)         AS sobre_p75,
       count(*) FILTER (WHERE p.unicos = 1 AND p.vistas > c.c90)         AS sobre_p90,
       count(*) FILTER (WHERE p.unicos = 1 AND p.vistas > c.c95)         AS sobre_p95,
       sum(p.valor) FILTER (WHERE p.unicos = 1 AND p.vistas > c.c90)::numeric(20,0)
                                                                         AS valor_sobre_p90
FROM p JOIN cortes c USING (modalidad)
WHERE p.vistas IS NOT NULL AND p.unicos IS NOT NULL;

DROP TABLE p;
