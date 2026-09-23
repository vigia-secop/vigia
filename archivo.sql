-- EL ARCHIVO: todo lo ingerido, por día, por semana y por mes. SOLO LECTURA.
--
--   psql -tA -f archivo.sql -o archivo.json
--
-- Una sola sentencia, a propósito: con `CREATE TEMP TABLE` delante, psql
-- escribe «SELECT 4» dentro del archivo de salida y el JSON deja de ser JSON.
-- Costó una publicación el 2026-09-15. Un CTE no imprime nada.
--
-- POR QUÉ EXISTE. `index.html` es el día de hoy y `semana.html` el período
-- recién cerrado. Entre los dos no había forma de preguntar «¿y el martes
-- pasado?» ni «¿cómo fue agosto entero?». Los datos estaban; el recorrido no.
--
-- ESTE ARCHIVO NO DEVUELVE EL DOCUMENTO DE NINGUNA PERSONA NATURAL. El nombre
-- de una empresa sí —es información pública de un contrato público—; el de un
-- particular se reemplaza por la etiqueta genérica dentro de la propia
-- consulta, que es la única forma de que no dependa de que alguien se acuerde.
--
-- LAS ERRATAS ×10ⁿ SE APARTAN DE TODAS LAS CIFRAS Y SE DECLARAN APARTE, que es
-- la regla del resto del sitio. Un contrato tecleado con tres ceros de más
-- convierte un día de $790 millones en uno de $432 mil millones, y la página
-- no falla: sale, se lee, y está 547 veces mal.

WITH errata AS MATERIALIZED (
  SELECT id_del_proceso, base
  FROM (
    SELECT contenido->>'id_del_proceso'                       AS id_del_proceso,
           (contenido->>'precio_base')::numeric               AS base,
           (contenido->>'valor_total_adjudicacion')::numeric
             / (contenido->>'precio_base')::numeric           AS razon
    FROM (
      SELECT DISTINCT ON (contenido->>'id_del_proceso') contenido
      FROM crudo_registro
      WHERE dataset = 'procesos'
        AND contenido->>'adjudicado' = 'Si'
        AND contenido->>'precio_base' ~ '^[0-9]+(\.[0-9]+)?$'
        AND contenido->>'valor_total_adjudicacion' ~ '^[0-9]+(\.[0-9]+)?$'
        AND (contenido->>'precio_base')::numeric > 0
      ORDER BY contenido->>'id_del_proceso', consultado_en DESC
    ) u
  ) z
  WHERE razon >= 100
    AND abs(razon / power(10::numeric, round(log(razon))) - 1) < 0.001
),

-- Cada contrato con fecha, ya etiquetado con su semana y su mes, y marcado si
-- es errata. Se calcula una sola vez y de aquí salen las tres granularidades:
-- que el día, la semana y el mes vengan de la misma fila es lo que garantiza
-- que sumen igual. Dos consultas parecidas son dos consultas que un día se
-- separan sin que nadie lo note.
fechado AS MATERIALIZED (
  SELECT c.id_contrato,
         c.fecha_de_firma                                  AS dia,
         date_trunc('week',  c.fecha_de_firma)::date        AS semana,
         date_trunc('month', c.fecha_de_firma)::date        AS mes,
         c.valor,
         c.nit_entidad,
         c.nombre_entidad,
         c.departamento_nombre,
         c.proveedor_tipo,
         c.proveedor_numero,
         c.proveedor_provisional,
         CASE
           WHEN c.proveedor_provisional
             THEN coalesce(nullif(c.proveedor_nombre, ''), 'Unión temporal')
           WHEN c.proveedor_tipo ~* 'c[eé]dula|pasaporte|nuip|tarjeta de identidad|registro civil|permiso (especial|por)'
             THEN 'Persona natural'
           ELSE coalesce(nullif(c.proveedor_nombre, ''), 'Sin razón social')
         END                                                AS proveedor,
         (e.id_del_proceso IS NOT NULL)                     AS es_errata,
         e.base                                             AS presupuesto_del_proceso
  FROM contrato c
  LEFT JOIN errata e USING (id_del_proceso)
  WHERE c.fecha_de_firma IS NOT NULL
    AND c.valor_fuera_de_escala IS NOT TRUE
),

-- Lo publicable: sin las erratas. Todas las cifras salen de aquí.
publicable AS (SELECT * FROM fechado WHERE NOT es_errata)

SELECT json_build_object(

  'generado_en', now(),

  'rango', (
    SELECT json_build_object(
      'desde', min(dia), 'hasta', max(dia),
      'contratos', count(*), 'valor', coalesce(sum(valor), 0)
    ) FROM publicable
  ),

  -- Por día. Van solo los días CON contratos: los huecos los dibuja el
  -- generador, que es quien sabe de festivos. Un cero en la fuente y un día
  -- que no existe en la fuente no son lo mismo, y la página lo dice.
  'dias', (
    SELECT json_agg(f ORDER BY f.dia) FROM (
      SELECT dia,
             count(*)                         AS contratos,
             coalesce(sum(valor), 0)          AS valor,
             count(DISTINCT nit_entidad)      AS entidades,
             count(DISTINCT (proveedor_tipo, proveedor_numero))
               FILTER (WHERE proveedor_provisional IS FALSE) AS proveedores
      FROM publicable GROUP BY dia
    ) f
  ),

  'semanas', (
    SELECT json_agg(f ORDER BY f.desde) FROM (
      SELECT semana                           AS desde,
             (semana + 6)                     AS hasta,
             count(*)                         AS contratos,
             coalesce(sum(valor), 0)          AS valor,
             count(DISTINCT nit_entidad)      AS entidades,
             count(DISTINCT (proveedor_tipo, proveedor_numero))
               FILTER (WHERE proveedor_provisional IS FALSE) AS proveedores,
             min(dia)                         AS primer_dia_con_datos,
             max(dia)                         AS ultimo_dia_con_datos
      FROM publicable GROUP BY semana
    ) f
  ),

  'meses', (
    SELECT json_agg(f ORDER BY f.desde) FROM (
      SELECT mes                              AS desde,
             (mes + interval '1 month - 1 day')::date AS hasta,
             count(*)                         AS contratos,
             coalesce(sum(valor), 0)          AS valor,
             count(DISTINCT nit_entidad)      AS entidades,
             count(DISTINCT (proveedor_tipo, proveedor_numero))
               FILTER (WHERE proveedor_provisional IS FALSE) AS proveedores,
             min(dia)                         AS primer_dia_con_datos,
             max(dia)                         AS ultimo_dia_con_datos
      FROM publicable GROUP BY mes
    ) f
  ),

  -- LOS CINCO MAYORES DE CADA PERÍODO, en las tres granularidades.
  --
  -- Van en el mismo JSON y no en una consulta por cada clic: la página se
  -- publica como HTML quieto en GitHub Pages, sin nada que responda del otro
  -- lado. Todo lo que el lector pueda pedir tiene que estar ya adentro.
  'mayores', (
    SELECT json_object_agg(clave, filas) FROM (
      SELECT clave, json_agg(f ORDER BY f.valor DESC) AS filas
      FROM (
        SELECT clave, id_contrato, proveedor, entidad, departamento, valor,
               row_number() OVER (PARTITION BY clave ORDER BY valor DESC) AS puesto
        FROM (
          SELECT 'd' || dia    AS clave, id_contrato, proveedor,
                 nombre_entidad AS entidad, departamento_nombre AS departamento, valor
          FROM publicable WHERE valor IS NOT NULL
          UNION ALL
          SELECT 's' || semana, id_contrato, proveedor,
                 nombre_entidad, departamento_nombre, valor
          FROM publicable WHERE valor IS NOT NULL
          UNION ALL
          SELECT 'm' || mes, id_contrato, proveedor,
                 nombre_entidad, departamento_nombre, valor
          FROM publicable WHERE valor IS NOT NULL
        ) t
      ) f
      WHERE puesto <= 5
      GROUP BY clave
    ) g
  ),

  -- LAS APARTADAS, POR PERÍODO. Apartar no es tapar: cada período dice
  -- cuántas se le quitaron y cuánto sumaban, con el mismo detalle con que
  -- dice sus propias cifras. Sin esto, el lector no sabe si el total que ve
  -- las incluye, y una cobertura que no se declara no es cobertura.
  'erratas', (
    SELECT json_object_agg(clave, datos) FROM (
      SELECT clave,
             json_build_object(
               'cuantas', count(*),
               'valor', coalesce(sum(valor), 0),
               'filas', json_agg(json_build_object(
                 'id_contrato', id_contrato, 'proveedor', proveedor,
                 'entidad', entidad, 'valor', valor,
                 'presupuesto_del_proceso', presupuesto_del_proceso,
                 'veces', round(valor / nullif(presupuesto_del_proceso, 0))
               ) ORDER BY valor DESC)
             ) AS datos
      FROM (
        SELECT 'd' || dia AS clave, id_contrato, proveedor,
               nombre_entidad AS entidad, valor, presupuesto_del_proceso
        FROM fechado WHERE es_errata
        UNION ALL
        SELECT 's' || semana, id_contrato, proveedor, nombre_entidad, valor,
               presupuesto_del_proceso FROM fechado WHERE es_errata
        UNION ALL
        SELECT 'm' || mes, id_contrato, proveedor, nombre_entidad, valor,
               presupuesto_del_proceso FROM fechado WHERE es_errata
      ) t
      GROUP BY clave
    ) g
  )

) AS archivo;
