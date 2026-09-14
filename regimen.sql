-- ¿Se nota el cambio de gobierno del 7 de agosto de 2026 en los datos?
--
-- SOLO LECTURA.  psql -tA -f regimen.sql -o regimen.json
--
-- QUÉ SE PUEDE Y QUÉ NO
-- Los CONTRATOS ingeridos son del 26 de agosto al 2 de septiembre: todos
-- posteriores al cambio. No sirven para comparar. Los PROCESOS van del 1 de
-- julio al 2 de septiembre y sí cruzan la frontera, así que toda la
-- comparación de abajo es sobre procesos publicados.
--
-- DOS SALVEDADES QUE HAY QUE LEER CON EL RESULTADO
-- 1. El SECOP publica con retraso: los últimos días del rango están
--    incompletos por construcción. Por eso los promedios se calculan hasta el
--    30 de agosto y la serie diaria completa se devuelve aparte, para que la
--    caída del final se vea y no se confunda con un efecto real.
-- 2. El cambio del 7 de agosto es NACIONAL. Alcaldes y gobernadores siguen en
--    el periodo 2024-2027 y no cambiaron. Sin clasificar entidades por nivel
--    -que es la historia 1.6- este corte mezcla las dos cosas.

SELECT json_build_object(

  'corte', '2026-08-07',
  'fin_confiable', '2026-08-30',

  'rango', (
    SELECT json_build_object('desde', min(fecha_de_publicacion),
                             'hasta', max(fecha_de_publicacion),
                             'sin_fecha', count(*) FILTER (WHERE fecha_de_publicacion IS NULL))
    FROM proceso
  ),

  'por_dia', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT fecha_de_publicacion AS dia,
             count(*) AS procesos,
             extract(isodow FROM fecha_de_publicacion)::int AS dow
      FROM proceso
      WHERE fecha_de_publicacion IS NOT NULL
      GROUP BY 1 ORDER BY 1
    ) f
  ),

  -- Promedios sobre DÍAS HÁBILES y hasta el 30 de agosto, para no comparar
  -- un tramo con fines de semana contra otro con más o menos.
  'regimen', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT CASE WHEN fecha_de_publicacion < DATE '2026-08-07'
                  THEN 'antes' ELSE 'despues' END AS tramo,
             count(*) AS procesos,
             count(DISTINCT fecha_de_publicacion) AS dias,
             round(count(*)::numeric / nullif(count(DISTINCT fecha_de_publicacion),0), 1) AS por_dia,
             count(DISTINCT nit_entidad) AS entidades
      FROM proceso
      WHERE fecha_de_publicacion IS NOT NULL
        AND fecha_de_publicacion <= DATE '2026-08-30'
        AND extract(isodow FROM fecha_de_publicacion) <= 5
      GROUP BY 1 ORDER BY 1
    ) f
  ),

  -- La semana anterior al cambio contra la semana posterior. Es el contraste
  -- más limpio: mismo número de días hábiles, sin el ruido de dos meses.
  'semanas', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT CASE
               WHEN fecha_de_publicacion BETWEEN DATE '2026-07-27' AND DATE '2026-08-06' THEN 'once dias antes'
               ELSE 'once dias despues' END AS ventana,
             count(*) AS procesos,
             count(DISTINCT nit_entidad) AS entidades
      FROM proceso
      WHERE fecha_de_publicacion BETWEEN DATE '2026-07-27' AND DATE '2026-08-17'
      GROUP BY 1 ORDER BY 1
    ) f
  ),

  'modalidad_por_regimen', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT coalesce(modalidad, '(sin modalidad)') AS modalidad,
             count(*) FILTER (WHERE fecha_de_publicacion <  DATE '2026-08-07') AS antes,
             count(*) FILTER (WHERE fecha_de_publicacion >= DATE '2026-08-07') AS despues,
             count(*) AS total
      FROM proceso
      WHERE fecha_de_publicacion IS NOT NULL
        AND fecha_de_publicacion <= DATE '2026-08-30'
      GROUP BY 1 ORDER BY total DESC LIMIT 10
    ) f
  ),

  -- Entidades que más cambiaron su ritmo de publicación. Descriptivo: un
  -- cambio de ritmo no es una irregularidad, es dónde mirar.
  'entidades_que_cambiaron', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT nombre_entidad AS entidad, nit_entidad AS nit, antes, despues,
             (despues - antes) AS diferencia
      FROM (
        SELECT nombre_entidad, nit_entidad,
               count(*) FILTER (WHERE fecha_de_publicacion <  DATE '2026-08-07') AS antes,
               count(*) FILTER (WHERE fecha_de_publicacion >= DATE '2026-08-07') AS despues
        FROM proceso
        WHERE fecha_de_publicacion IS NOT NULL
          AND fecha_de_publicacion <= DATE '2026-08-30'
          AND nombre_entidad IS NOT NULL
        GROUP BY 1, 2
        HAVING count(*) >= 100
      ) t
      ORDER BY abs(despues - antes) DESC
      LIMIT 12
    ) f
  ),

  -- ¿Los contratos que sí tenemos (todos post-7 de agosto) vienen de procesos
  -- de antes o de después? Es la única forma de tocar el tema con contratos.
  'contratos_por_origen', (
    SELECT json_build_object(
      'de_proceso_anterior', count(*) FILTER (WHERE p.fecha_de_publicacion <  DATE '2026-08-07'),
      'de_proceso_posterior', count(*) FILTER (WHERE p.fecha_de_publicacion >= DATE '2026-08-07'),
      'valor_anterior',  coalesce(sum(c.valor) FILTER (WHERE p.fecha_de_publicacion <  DATE '2026-08-07'), 0),
      'valor_posterior', coalesce(sum(c.valor) FILTER (WHERE p.fecha_de_publicacion >= DATE '2026-08-07'), 0),
      'sin_proceso', (SELECT count(*) FROM contrato WHERE id_del_proceso IS NULL)
    )
    FROM contrato c JOIN proceso p USING (id_del_proceso)
  )

) AS regimen;
