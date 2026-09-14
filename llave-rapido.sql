-- La pregunta que decide el arreglo de la llave, y SOLO esa.
-- SOLO LECTURA.  psql -tA -f llave-rapido.sql -o llave.json
--
-- La versión completa (revisar-llave.sql) incluía conteos `DISTINCT` sobre
-- las 357 000 filas de procesos y llevaba más de cinco minutos sin terminar.
-- Aquí queda solo lo que hace falta para decidir, sobre una muestra de 300
-- contratos duplicados. Si UNO SOLO trae una diferencia de negocio, la
-- hipótesis se cae y el arreglo es otro.

WITH plataforma AS (
  SELECT array_agg(k) AS ks FROM (
    SELECT DISTINCT jsonb_object_keys(contenido) AS k
    FROM (SELECT contenido FROM crudo_registro WHERE dataset = 'contratos' LIMIT 50) m
  ) t WHERE k LIKE ':%'
),
muestra AS (
  SELECT contenido ->> 'id_contrato' AS negocio
  FROM crudo_registro WHERE dataset = 'contratos'
  GROUP BY 1 HAVING count(*) > 1
  ORDER BY 1 LIMIT 300
),
copias AS (
  SELECT c.contenido ->> 'id_contrato' AS negocio, c.contenido, c.consultado_en
  FROM crudo_registro c
  JOIN muestra m ON m.negocio = c.contenido ->> 'id_contrato'
  WHERE c.dataset = 'contratos'
)
SELECT json_build_object(

  'campos_de_plataforma', (SELECT coalesce(to_json(ks), '[]'::json) FROM plataforma),
  'muestra', (SELECT count(*) FROM muestra),
  'copias_en_la_muestra', (SELECT count(*) FROM copias),

  -- Quitando los campos de plataforma, ¿cuántas versiones realmente distintas
  -- queda de cada contrato? Si sale «1 versión, 300 contratos», la hipótesis
  -- se confirma: lo único que cambia es la plataforma.
  'versiones_reales', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT versiones, count(*) AS contratos FROM (
        SELECT negocio,
               count(DISTINCT md5((contenido - (SELECT ks FROM plataforma))::text)) AS versiones
        FROM copias GROUP BY 1
      ) t GROUP BY versiones ORDER BY versiones
    ) f
  ),

  -- Y si alguna difiere de verdad, en qué campo. Sin esto la conclusión sería
  -- una corazonada con formato de dato.
  'diferencias_reales', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT campo, count(*) AS contratos FROM (
        SELECT v.negocio, k.campo
        FROM (
          SELECT negocio,
                 (array_agg(contenido ORDER BY consultado_en))[1] AS vieja,
                 (array_agg(contenido ORDER BY consultado_en DESC))[1] AS nueva
          FROM copias GROUP BY negocio
        ) v
        CROSS JOIN LATERAL jsonb_object_keys(v.vieja || v.nueva) AS k(campo)
        WHERE k.campo NOT LIKE ':%'
          AND v.vieja ->> k.campo IS DISTINCT FROM v.nueva ->> k.campo
      ) t GROUP BY campo ORDER BY contratos DESC LIMIT 15
    ) f
  )

) AS llave;
