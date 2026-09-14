-- EL BOLETÍN: los números de un período, listos para publicar. SOLO LECTURA.
--
--   psql -v desde="'2026-08-31'" -v hasta="'2026-09-06'" -tA -f boletin.sql -o boletin.json
--
-- LA REGLA DE ESTE ARCHIVO, Y ES LA QUE LO DEFINE:
--
--     **NO DEVUELVE EL NOMBRE NI EL DOCUMENTO DE NADIE.**
--
-- Ni de una persona, ni de una empresa, ni de una entidad. Solo agregados,
-- distribuciones y conteos.
--
-- No es timidez: es la única garantía que no depende de que alguien se acuerde.
-- Un boletín se publica en internet y no se puede despublicar. Si la consulta
-- que lo alimenta **no puede** devolver un nombre, entonces ninguna prisa,
-- ningún cambio de última hora y ningún error mío puede hacer que salga uno.
-- La lista de revisión —que sí lleva nombres— se queda en el escritorio, que
-- es donde debe estar mientras no haya una Regla calibrada detrás.
--
-- Lo geográfico sí entra: un departamento no es una persona y no se defiende
-- de una cifra. Las modalidades tampoco.
--
-- SE EXCLUYEN LOS VALORES IMPOSIBLES de todo total, igual que el Panel.

SELECT json_build_object(

  'generado_en', now(),
  'periodo', json_build_object('desde', :desde::date, 'hasta', :hasta::date),
  'anterior', json_build_object(
      'desde', (:desde::date - (:hasta::date - :desde::date) - 1),
      'hasta', (:desde::date - 1)),

  'actual', (
    SELECT json_build_object(
      'contratos', count(*),
      'valor', coalesce(sum(valor), 0),
      'entidades', count(DISTINCT nit_entidad),
      'proveedores', count(DISTINCT (proveedor_tipo, proveedor_numero))
        FILTER (WHERE proveedor_provisional IS FALSE),
      'nacional', count(*) FILTER (WHERE orden = 'NACIONAL'),
      'territorial', count(*) FILTER (WHERE orden = 'TERRITORIAL'),
      'valor_nacional', coalesce(sum(valor) FILTER (WHERE orden = 'NACIONAL'), 0),
      'valor_territorial', coalesce(sum(valor) FILTER (WHERE orden = 'TERRITORIAL'), 0)
    ) FROM contrato
    WHERE fecha_de_firma BETWEEN :desde::date AND :hasta::date
      AND valor_fuera_de_escala IS NOT TRUE
  ),

  'anterior_cifras', (
    SELECT json_build_object(
      'contratos', count(*),
      'valor', coalesce(sum(valor), 0),
      'entidades', count(DISTINCT nit_entidad),
      'proveedores', count(DISTINCT (proveedor_tipo, proveedor_numero))
        FILTER (WHERE proveedor_provisional IS FALSE),
      'nacional', count(*) FILTER (WHERE orden = 'NACIONAL'),
      'territorial', count(*) FILTER (WHERE orden = 'TERRITORIAL'),
      'valor_nacional', coalesce(sum(valor) FILTER (WHERE orden = 'NACIONAL'), 0),
      'valor_territorial', coalesce(sum(valor) FILTER (WHERE orden = 'TERRITORIAL'), 0)
    ) FROM contrato
    WHERE fecha_de_firma
          BETWEEN (:desde::date - (:hasta::date - :desde::date) - 1)
              AND (:desde::date - 1)
      AND valor_fuera_de_escala IS NOT TRUE
  ),

  -- LO QUE NO SE PUEDE VER. Va en el boletín, no en una nota al pie. Un
  -- número de contratación pública sin su cobertura al lado es la clase de
  -- cifra que se cita mal, y publicarla sin ella sería exactamente lo que
  -- este proyecto reprocha a los demás.
  'cobertura', (
    SELECT json_build_object(
      'contratos', count(*),
      'uniones', count(*) FILTER (WHERE proveedor_provisional),
      'valor_uniones', coalesce(sum(valor) FILTER (WHERE proveedor_provisional), 0),
      'sin_identidad', count(*) FILTER (WHERE proveedor_tipo IS NULL),
      'huerfanos', count(*) FILTER (WHERE id_del_proceso IS NULL
                                      AND proceso_de_compra IS NOT NULL),
      'sin_departamento', count(*) FILTER (WHERE departamento_codigo IS NULL),
      'sin_valor', count(*) FILTER (WHERE valor IS NULL),
      'imposibles', count(*) FILTER (WHERE valor_fuera_de_escala)
    ) FROM contrato
    WHERE fecha_de_firma BETWEEN :desde::date AND :hasta::date
  ),

  -- HASTA DÓNDE LLEGAN NUESTROS DATOS. Sin esto, un período anterior vacío
  -- se lee como «no se contrató nada», cuando lo que pasa es que **no lo
  -- hemos traído**. Es la misma distinción que sostiene el modo calibración:
  -- «se miró y no había» no es «no se miró», y confundirlas en una página
  -- publicada es afirmar una caída que no ocurrió.
  --
  -- Con esto, quien dibuja puede callarse la comparación en vez de inventarla.
  'cobertura_temporal', (
    SELECT json_build_object(
      'primer_contrato', min(fecha_de_firma),
      'ultimo_contrato', max(fecha_de_firma),
      'contratos_en_total', count(*)
    ) FROM contrato WHERE fecha_de_firma IS NOT NULL
  ),

  -- Geografía: un departamento no es una persona.
  'departamentos', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(departamento_nombre, 'SIN DEPARTAMENTO') AS nombre,
             count(*) AS contratos, coalesce(sum(valor), 0) AS valor
      FROM contrato
      WHERE fecha_de_firma BETWEEN :desde::date AND :hasta::date
        AND valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1 ORDER BY sum(valor) DESC NULLS LAST LIMIT 8
    ) f
  ),

  -- Modalidades: cómo se contrata, que es la pregunta que casi nadie hace.
  'modalidades', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(p.modalidad, '(sin modalidad)') AS modalidad,
             count(*) AS contratos, coalesce(sum(c.valor), 0) AS valor
      FROM contrato c JOIN proceso p USING (id_del_proceso)
      WHERE c.fecha_de_firma BETWEEN :desde::date AND :hasta::date
        AND c.valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1 ORDER BY count(*) DESC LIMIT 8
    ) f
  ),

  -- La forma del gasto: cuántos contratos y cuánta plata en cada tramo. Es el
  -- dato que convierte «$12 billones» en algo que se entiende.
  'tramos', (
    SELECT json_agg(f) FROM (
      SELECT tramo, orden, count(*) AS contratos, coalesce(sum(valor), 0) AS valor
      FROM (
        SELECT valor,
          CASE WHEN valor IS NULL          THEN 'sin valor'
               WHEN valor <     1000000    THEN 'menos de 1 millon'
               WHEN valor <    10000000    THEN '1 a 10 millones'
               WHEN valor <   100000000    THEN '10 a 100 millones'
               WHEN valor <  1000000000    THEN '100 a 1000 millones'
               WHEN valor < 10000000000    THEN '1000 a 10 mil millones'
               ELSE 'mas de 10 mil millones' END AS tramo,
          CASE WHEN valor IS NULL THEN 0
               WHEN valor <     1000000 THEN 1 WHEN valor <    10000000 THEN 2
               WHEN valor <   100000000 THEN 3 WHEN valor <  1000000000 THEN 4
               WHEN valor < 10000000000 THEN 5 ELSE 6 END AS orden
        FROM contrato
        WHERE fecha_de_firma BETWEEN :desde::date AND :hasta::date
          AND valor_fuera_de_escala IS NOT TRUE
      ) t GROUP BY tramo, orden ORDER BY orden
    ) f
  )

) AS boletin;
