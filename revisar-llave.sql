-- ¿Qué hay que cambiar exactamente para que la capa cruda vuelva a ser
-- idempotente? SOLO LECTURA.  psql -tA -f revisar-llave.sql -o llave.json
--
-- Hipótesis a comprobar, no a asumir:
--   (a) el mismo contrato entró dos veces con `:id` distinto;
--   (b) lo único que cambia entre las dos copias son campos de plataforma de
--       Socrata, los que empiezan por «:»;
--   (c) por tanto, llave de negocio + hash sin campos de plataforma devuelve
--       la idempotencia.
-- Si (b) es falso, el arreglo es otro y hay que saberlo ANTES de migrar una
-- tabla de 400 000 filas.
--
-- SOBRE LA MUESTRA. Los conteos globales van sobre todo. Las dos consultas
-- caras -las que comparan copia contra copia- van sobre una MUESTRA de 300
-- contratos duplicados, porque `contenido ->> 'id_contrato'` no tiene indice
-- y compararlos todos es cuadratico: la primera version de este archivo llevaba
-- cuatro minutos corriendo cuando la corte, el 2026-09-03. Trescientos casos
-- sobran para responder si la diferencia esta solo en campos de plataforma:
-- si UNO SOLO trae diferencia de negocio, la hipotesis (b) ya es falsa.

WITH claves AS (
  SELECT DISTINCT jsonb_object_keys(contenido) AS k
  FROM crudo_registro WHERE dataset = 'contratos' LIMIT 200
),
plataforma AS (
  SELECT array_agg(k) AS ks FROM claves WHERE k LIKE ':%'
),
dup AS (
  SELECT contenido ->> 'id_contrato' AS negocio, count(*) AS filas
  FROM crudo_registro WHERE dataset = 'contratos'
  GROUP BY 1 HAVING count(*) > 1
),
muestra AS (
  SELECT negocio FROM dup ORDER BY negocio LIMIT 300
),
copias AS (
  SELECT c.contenido ->> 'id_contrato' AS negocio, c.contenido, c.consultado_en
  FROM crudo_registro c
  JOIN muestra m ON m.negocio = c.contenido ->> 'id_contrato'
  WHERE c.dataset = 'contratos'
)
SELECT json_build_object(

  'campos_de_plataforma', (SELECT coalesce(to_json(ks), '[]'::json) FROM plataforma),

  'contratos', (
    SELECT json_build_object(
      'filas_crudas', count(*),
      'ids_de_socrata_distintos', count(DISTINCT id_fila_fuente),
      'contratos_de_negocio_distintos', count(DISTINCT contenido ->> 'id_contrato'),
      'sin_id_de_negocio', count(*) FILTER (WHERE contenido ->> 'id_contrato' IS NULL)
    ) FROM crudo_registro WHERE dataset = 'contratos'
  ),

  'con_mas_de_una_copia', (SELECT count(*) FROM dup),

  -- LA CONSULTA QUE DECIDE. Quitando los campos de plataforma, ¿cuántas
  -- versiones REALMENTE distintas quedan de cada contrato duplicado?
  'muestra', (SELECT count(*) FROM muestra),

  'versiones_reales', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT versiones, count(*) AS contratos FROM (
        SELECT negocio,
               count(DISTINCT md5((contenido - (SELECT ks FROM plataforma))::text)) AS versiones
        FROM copias GROUP BY 1
      ) t GROUP BY versiones ORDER BY versiones
    ) f
  ),

  -- Y si alguna versión sí difiere de verdad, en QUÉ campo. Sin esto la
  -- conclusión sería una corazonada con formato de dato.
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
  ),

  'procesos', (
    SELECT json_build_object(
      'filas_crudas', count(*),
      'ids_de_socrata_distintos', count(DISTINCT id_fila_fuente),
      'procesos_distintos', count(DISTINCT contenido ->> 'id_del_proceso'),
      'adjudicaciones_distintas', count(DISTINCT (contenido ->> 'id_del_proceso') || '|' || coalesce(contenido ->> 'id_adjudicacion', '')),
      'sin_id_adjudicacion', count(*) FILTER (WHERE contenido ->> 'id_adjudicacion' IS NULL)
    ) FROM crudo_registro WHERE dataset = 'procesos'
  )

) AS llave;
