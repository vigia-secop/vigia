-- Un único objeto JSON con todo lo que el Panel necesita.
--
-- SOLO LECTURA. No modifica nada.
--     psql -tA -f panel.sql -o panel.json
--
-- REGLA DE ESTE ARCHIVO: nada que no se pueda sostener con un conteo. Ninguna
-- sección "estima", "proyecta" ni rellena huecos con ceros. Lo que no se puede
-- medir con los datos de hoy no aparece — y lo que se mide a medias aparece
-- en el bloque de cobertura, que existe para que nadie lea el resto sin saber
-- sobre cuánto está mirando.

SELECT json_build_object(

  'generado_en', now(),

  'ventana', (
    SELECT json_build_object(
      'desde', min(fecha_de_firma), 'hasta', max(fecha_de_firma),
      'contratos', count(*),
      'valor', coalesce(sum(valor), 0),
      'entidades', count(DISTINCT nit_entidad),
      'proveedores', count(DISTINCT (proveedor_tipo, proveedor_numero))
        FILTER (WHERE proveedor_provisional IS FALSE)
    -- SIN LOS IMPOSIBLES. Un solo contrato con tres ceros de más convierte
    -- este total en mentira y nadie se entera, porque el número no falla:
    -- sale, se lee, y está mal. Se excluyen aquí y se declaran abajo.
    ) FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE
  ),

  -- LO PRIMERO, NO LO ÚLTIMO. Cuánto de la ventana queda fuera del alcance de
  -- cada cosa. Un ranking de contratistas sin este bloque al lado es un
  -- ranking sobre una parte del universo que el lector no conoce.
  'cobertura', (
    SELECT json_build_object(
      'contratos', count(*),
      'con_proveedor_real', count(*) FILTER (WHERE proveedor_provisional IS FALSE),
      'union_temporal_sin_documento', count(*) FILTER (WHERE proveedor_provisional),
      'valor_union_temporal', coalesce(sum(valor) FILTER (WHERE proveedor_provisional), 0),
      'sin_identidad_de_proveedor', count(*) FILTER (WHERE proveedor_tipo IS NULL),
      'enlazados_a_proceso', count(id_del_proceso),
      'huerfanos', count(*) FILTER (WHERE id_del_proceso IS NULL AND proceso_de_compra IS NOT NULL),
      'sin_departamento', count(*) FILTER (WHERE departamento_codigo IS NULL),
      'sin_orden', count(*) FILTER (WHERE orden IS NULL),
      'sin_valor', count(*) FILTER (WHERE valor IS NULL),
      -- LOS IMPOSIBLES. Van en cobertura y no en un ranking porque no son un
      -- hallazgo sobre nadie: son un defecto de la fuente que nos obliga a
      -- decir sobre cuánto NO estamos calculando. `valor_declarado` es la
      -- suma tal como la fuente la publica, y se muestra a propósito: enseña
      -- de qué tamaño sería la mentira si no los excluyéramos.
      'valor_fuera_de_escala', count(*) FILTER (WHERE valor_fuera_de_escala),
      'valor_declarado_fuera_de_escala',
        coalesce(sum(valor) FILTER (WHERE valor_fuera_de_escala), 0)
    ) FROM contrato
  ),

  -- Concentración por proveedor. EXCLUYE las identidades provisionales a
  -- propósito: cada una vale por un solo contrato, así que aparecerían con
  -- una concentración de 1 que no significa nada. Su total va aparte, arriba.
  'proveedores', (
    SELECT json_agg(f) FROM (
      SELECT proveedor_nombre AS nombre,
             proveedor_tipo AS tipo, proveedor_numero AS numero,
             count(*) AS contratos,
             coalesce(sum(valor), 0) AS valor,
             count(DISTINCT nit_entidad) AS entidades
      FROM contrato
      WHERE proveedor_provisional IS FALSE AND valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1, 2, 3
      ORDER BY sum(valor) DESC NULLS LAST
      LIMIT 20
    ) f
  ),

  -- Un mismo documento con varias razones sociales. No es una alerta: es un
  -- hecho que el Expediente de la épica 2 tendrá que mostrar.
  'proveedores_con_varios_nombres', (
    SELECT json_agg(f) FROM (
      SELECT p.numero, p.nombre_principal, p.variantes, p.contratos
      FROM proveedor p
      WHERE p.variantes > 1 AND NOT p.provisional
      ORDER BY p.variantes DESC, p.contratos DESC
      LIMIT 10
    ) f
  ),

  'uniones_temporales', (
    SELECT json_agg(f) FROM (
      SELECT proveedor_nombre AS nombre, nombre_entidad AS entidad,
             valor, estado, departamento_nombre AS departamento
      FROM contrato
      WHERE proveedor_provisional AND valor_fuera_de_escala IS NOT TRUE
      ORDER BY valor DESC NULLS LAST
      LIMIT 15
    ) f
  ),

  'ordenes', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(orden, 'SIN DECLARAR') AS orden,
             count(*) AS contratos, coalesce(sum(valor), 0) AS valor
      FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1 ORDER BY sum(valor) DESC NULLS LAST
    ) f
  ),

  'departamentos', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(departamento_codigo, '--') AS codigo,
             coalesce(departamento_nombre, 'SIN DEPARTAMENTO') AS nombre,
             count(*) AS contratos, coalesce(sum(valor), 0) AS valor
      FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1, 2 ORDER BY sum(valor) DESC NULLS LAST
    ) f
  ),

  'entidades', (
    SELECT json_agg(f) FROM (
      SELECT nombre_entidad AS nombre, nit_entidad AS nit,
             count(*) AS contratos, coalesce(sum(valor), 0) AS valor,
             count(DISTINCT (proveedor_tipo, proveedor_numero))
               FILTER (WHERE proveedor_provisional IS FALSE) AS proveedores
      FROM contrato WHERE nombre_entidad IS NOT NULL
        AND valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1, 2 ORDER BY sum(valor) DESC NULLS LAST LIMIT 20
    ) f
  ),

  'modalidades', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(p.modalidad, '(sin modalidad)') AS modalidad,
             count(*) AS contratos, coalesce(sum(c.valor), 0) AS valor
      FROM contrato c JOIN proceso p USING (id_del_proceso)
      WHERE c.valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1 ORDER BY count(*) DESC LIMIT 12
    ) f
  ),

  'tramos', (
    SELECT json_agg(f) FROM (
      SELECT tramo, orden, count(*) AS contratos, coalesce(sum(valor), 0) AS valor
      FROM (
        SELECT valor,
          CASE WHEN valor IS NULL THEN 'sin valor'
               WHEN valor <     1000000 THEN 'menos de 1 M'
               WHEN valor <    10000000 THEN '1 M - 10 M'
               WHEN valor <   100000000 THEN '10 M - 100 M'
               WHEN valor <  1000000000 THEN '100 M - 1000 M'
               WHEN valor < 10000000000 THEN '1000 M - 10 mil M'
               ELSE 'mas de 10 mil M' END AS tramo,
          CASE WHEN valor IS NULL THEN 0
               WHEN valor <     1000000 THEN 1
               WHEN valor <    10000000 THEN 2
               WHEN valor <   100000000 THEN 3
               WHEN valor <  1000000000 THEN 4
               WHEN valor < 10000000000 THEN 5
               ELSE 6 END AS orden
        -- Tambien aqui: un imposible caeria en «mas de 10 mil M» e inflaria
        -- la suma de ese tramo, que es justo el que mas se mira.
        FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE
      ) t GROUP BY tramo, orden ORDER BY orden
    ) f
  ),

  -- LOS QUINCE MAYORES, Y LA ADVERTENCIA QUE LES FALTABA.
  --
  -- El 2026-09-11 el primero de esta lista era la ALCALDÍA DE TIPACOQUE
  -- —municipio de unos 3.000 habitantes— con $431.340.000.000. El presupuesto
  -- del proceso era $431.340.000: el mismo número con TRES CEROS DE MÁS.
  --
  -- El techo de valores imposibles (1e14) no lo atajó y nunca pudo: 431 mil
  -- millones es un contrato posible. Así que la fila encabezaba el ranking sin
  -- ninguna marca. `errata_probable` es esa marca: el valor adjudicado es
  -- EXACTAMENTE una potencia de diez del presupuesto de su propio proceso, que
  -- es la firma de una tecla y no la de un sobrecosto.
  --
  -- No se excluyen de la lista. Se marcan. Excluir sería corregir la fuente a
  -- ojo; marcar es decir lo que se sabe.
  'contratos_mayores', (
    SELECT json_agg(f) FROM (
      SELECT c.id_contrato, c.proveedor_nombre AS proveedor,
             c.nombre_entidad AS entidad, c.valor, c.estado,
             c.departamento_nombre AS departamento,
             c.proveedor_provisional AS es_union_temporal,
             (s.id_del_proceso IS NOT NULL)     AS errata_probable,
             s.base                             AS valor_probable
      FROM contrato c
      LEFT JOIN (
        SELECT id_del_proceso, base
        FROM (
          SELECT contenido->>'id_del_proceso' AS id_del_proceso,
                 (contenido->>'precio_base')::numeric AS base,
                 (contenido->>'valor_total_adjudicacion')::numeric
                   / (contenido->>'precio_base')::numeric AS razon
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
      ) s USING (id_del_proceso)
      WHERE c.valor IS NOT NULL
        AND c.valor_fuera_de_escala IS NOT TRUE
      ORDER BY c.valor DESC LIMIT 15
    ) f
  ),

  'por_dia', (
    SELECT json_agg(f) FROM (
      SELECT fecha_de_firma AS dia, count(*) AS contratos,
             coalesce(sum(valor), 0) AS valor
      FROM contrato WHERE fecha_de_firma IS NOT NULL
        AND valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1 ORDER BY 1
    ) f
  )

) AS panel;
