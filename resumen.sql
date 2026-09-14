-- Resumen de un período contra el anterior. SOLO LECTURA.
--
--   psql -v desde="'2026-08-26'" -v hasta="'2026-09-02'" -tA -f resumen.sql -o resumen.json
--
-- Devuelve los dos períodos crudos. La comparación NO se hace aquí: se hace en
-- `vigia/resumen.py`, que divide por DÍAS HÁBILES. Comparar conteos crudos de
-- dos semanas es lo que casi produce una caída falsa del 45,7 % el 2026-09-03.

SELECT json_build_object(
  'generado_en', now(),
  'periodo', json_build_object('desde', :desde::date, 'hasta', :hasta::date),
  'anterior', json_build_object(
      'desde', (:desde::date - (:hasta::date - :desde::date) - 1),
      'hasta', (:desde::date - 1)),

  'actual', (
    SELECT json_build_object(
      'contratos', count(*), 'valor', coalesce(sum(valor),0),
      'entidades', count(DISTINCT nit_entidad),
      'proveedores', count(DISTINCT (proveedor_tipo, proveedor_numero))
        FILTER (WHERE proveedor_provisional IS FALSE),
      'uniones', count(*) FILTER (WHERE proveedor_provisional),
      'valor_uniones', coalesce(sum(valor) FILTER (WHERE proveedor_provisional),0),
      'huerfanos', count(*) FILTER (WHERE id_del_proceso IS NULL AND proceso_de_compra IS NOT NULL),
      'nacional', count(*) FILTER (WHERE orden = 'NACIONAL'),
      'territorial', count(*) FILTER (WHERE orden = 'TERRITORIAL'),
      'car', count(*) FILTER (WHERE orden = 'CORPORACION AUTONOMA'),
      'valor_nacional', coalesce(sum(valor) FILTER (WHERE orden='NACIONAL'),0),
      'valor_territorial', coalesce(sum(valor) FILTER (WHERE orden='TERRITORIAL'),0)
    ) FROM contrato
    WHERE fecha_de_firma BETWEEN :desde::date AND :hasta::date
  ),

  'anterior_cifras', (
    SELECT json_build_object(
      'contratos', count(*), 'valor', coalesce(sum(valor),0),
      'entidades', count(DISTINCT nit_entidad),
      'proveedores', count(DISTINCT (proveedor_tipo, proveedor_numero))
        FILTER (WHERE proveedor_provisional IS FALSE),
      'uniones', count(*) FILTER (WHERE proveedor_provisional),
      'valor_uniones', coalesce(sum(valor) FILTER (WHERE proveedor_provisional),0),
      'huerfanos', count(*) FILTER (WHERE id_del_proceso IS NULL AND proceso_de_compra IS NOT NULL),
      'nacional', count(*) FILTER (WHERE orden = 'NACIONAL'),
      'territorial', count(*) FILTER (WHERE orden = 'TERRITORIAL'),
      'car', count(*) FILTER (WHERE orden = 'CORPORACION AUTONOMA'),
      'valor_nacional', coalesce(sum(valor) FILTER (WHERE orden='NACIONAL'),0),
      'valor_territorial', coalesce(sum(valor) FILTER (WHERE orden='TERRITORIAL'),0)
    ) FROM contrato
    WHERE fecha_de_firma BETWEEN
          (:desde::date - (:hasta::date - :desde::date) - 1) AND (:desde::date - 1)
  ),

  'departamentos', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(departamento_nombre,'SIN DEPARTAMENTO') AS nombre,
             coalesce(departamento_codigo,'--') AS codigo,
             count(*) AS contratos, coalesce(sum(valor),0) AS valor
      FROM contrato WHERE fecha_de_firma BETWEEN :desde::date AND :hasta::date
      GROUP BY 1,2 ORDER BY sum(valor) DESC NULLS LAST LIMIT 10
    ) f
  ),

  'proveedores', (
    SELECT json_agg(f) FROM (
      SELECT proveedor_nombre AS nombre, proveedor_numero AS numero,
             count(*) AS contratos, coalesce(sum(valor),0) AS valor,
             count(DISTINCT nit_entidad) AS entidades
      FROM contrato
      WHERE proveedor_provisional IS FALSE
        AND fecha_de_firma BETWEEN :desde::date AND :hasta::date
      GROUP BY 1,2 ORDER BY sum(valor) DESC NULLS LAST LIMIT 10
    ) f
  ),

  'uniones', (
    SELECT json_agg(f) FROM (
      SELECT proveedor_nombre AS nombre, nombre_entidad AS entidad, valor, estado
      FROM contrato
      WHERE proveedor_provisional
        AND fecha_de_firma BETWEEN :desde::date AND :hasta::date
      ORDER BY valor DESC NULLS LAST LIMIT 8
    ) f
  )
) AS resumen;
