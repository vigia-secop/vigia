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
-- Y DESDE EL 2026-09-16, TAMBIEN LAS ERRATAS x10^n. Ver abajo.

-- LAS ERRATAS DE TECLEO, Y POR QUE ESTE ARCHIVO ERA EL MAS PELIGROSO DE LOS TRES
--
-- Un contrato cuyo valor adjudicado es EXACTAMENTE mil o diez mil veces el
-- presupuesto de su propio proceso no es un sobrecosto: es una tecla de mas.
-- El caso que lo enseno fue Tipacoque, $431.340.000.000 sobre un presupuesto
-- de $431.340.000.
--
-- El Panel ya las apartaba. Este archivo NO las mencionaba ni una sola vez, y
-- es el que alimenta `semana.html` y el hilo que se publica en X. Un boletin
-- con una errata adentro diria una cifra inflada sin ninguna advertencia, y
-- un post publicado no se puede retirar. De los tres sitios donde faltaba,
-- este era el unico irreversible.
--
-- Misma regla que los imposibles: FUERA de todo total y de toda distribucion,
-- DECLARADAS en cobertura con la cifra tal como la fuente la publica. No se
-- corrige la fuente ni se adivina el valor verdadero.
WITH errata AS MATERIALIZED (
  SELECT id_del_proceso
  FROM (
    SELECT contenido->>'id_del_proceso'                       AS id_del_proceso,
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

-- El universo sobre el que se calcula todo lo que sale publicado.
publicable AS (
  SELECT c.* FROM contrato c
  WHERE NOT EXISTS (
    SELECT 1 FROM errata e WHERE e.id_del_proceso = c.id_del_proceso
  )
)

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
    ) FROM publicable
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
    ) FROM publicable
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
      'imposibles', count(*) FILTER (WHERE valor_fuera_de_escala),
      -- LAS ERRATAS DEL PERIODO. Van aqui y no en un ranking porque no son un
      -- hallazgo sobre nadie: son un defecto de la fuente que obliga a decir
      -- sobre cuanto NO se esta calculando. `valor_erratas` es lo que
      -- sumarian si no se apartaran, y se ensena a proposito.
      'erratas', count(*) FILTER (WHERE tiene_errata),
      'valor_erratas', coalesce(sum(valor) FILTER (WHERE tiene_errata), 0)
    ) FROM (
      SELECT c.*, (e.id_del_proceso IS NOT NULL) AS tiene_errata
      FROM contrato c
      LEFT JOIN errata e USING (id_del_proceso)
      WHERE c.fecha_de_firma BETWEEN :desde::date AND :hasta::date
    ) c
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
      FROM publicable
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
      FROM publicable c JOIN proceso p USING (id_del_proceso)
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
        FROM publicable
        WHERE fecha_de_firma BETWEEN :desde::date AND :hasta::date
          AND valor_fuera_de_escala IS NOT TRUE
      ) t GROUP BY tramo, orden ORDER BY orden
    ) f
  )

) AS boletin;
