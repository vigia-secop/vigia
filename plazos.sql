-- «Plazo exprés» (historia 4.5): días entre la publicación del Proceso y la
-- firma del Contrato. Es la ÚNICA de las diez banderas del catálogo que se
-- puede calcular hoy con lo que hay en la base.
--
-- SOLO LECTURA.  psql -tA -f plazos.sql -o plazos.json
--
-- SESGO QUE HAY QUE DECLARAR. Solo entran los contratos ENLAZADOS, y enlazar
-- exige que su Proceso esté dentro de la ventana ingerida (desde el 1 de
-- julio). Un contrato cuyo Proceso se publicó en marzo es hoy un huérfano, no
-- un plazo largo. Es decir: la distribución de abajo está recortada por
-- arriba y el plazo real es MAYOR que el que se mide. Sirve para ver la forma
-- y para descubrir que un umbral absoluto no sirve; no sirve todavía para
-- fijar el umbral.

WITH p AS (
  SELECT c.id_contrato, c.nombre_entidad, c.valor, c.fecha_de_firma,
         pr.modalidad, pr.fecha_de_publicacion,
         (c.fecha_de_firma - pr.fecha_de_publicacion) AS dias
  FROM contrato c JOIN proceso pr USING (id_del_proceso)
  WHERE c.fecha_de_firma IS NOT NULL AND pr.fecha_de_publicacion IS NOT NULL
)
SELECT json_build_object(

  'universo', (
    SELECT json_build_object(
      'con_plazo_medible', count(*),
      'contratos_totales', (SELECT count(*) FROM contrato),
      'negativos',   count(*) FILTER (WHERE dias < 0),
      'mismo_dia',   count(*) FILTER (WHERE dias = 0),
      'un_dia',      count(*) FILTER (WHERE dias = 1)
    ) FROM p
  ),

  'percentiles', (
    SELECT json_build_object(
      'p01', percentile_cont(0.01) WITHIN GROUP (ORDER BY dias),
      'p05', percentile_cont(0.05) WITHIN GROUP (ORDER BY dias),
      'p10', percentile_cont(0.10) WITHIN GROUP (ORDER BY dias),
      'p25', percentile_cont(0.25) WITHIN GROUP (ORDER BY dias),
      'p50', percentile_cont(0.50) WITHIN GROUP (ORDER BY dias),
      'p75', percentile_cont(0.75) WITHIN GROUP (ORDER BY dias),
      'p90', percentile_cont(0.90) WITHIN GROUP (ORDER BY dias),
      'maximo', max(dias)
    ) FROM p WHERE dias >= 0
  ),

  'histograma', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT dias, count(*) AS contratos
      FROM p WHERE dias BETWEEN 0 AND 45
      GROUP BY 1 ORDER BY 1
    ) f
  ),

  -- El punto entero de la historia 4.5: el umbral es POR MODALIDAD. Una
  -- contratación directa de tres días es normal; una licitación pública de
  -- tres días no lo es. Un umbral único los mezcla y no sirve para nada.
  'por_modalidad', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT modalidad, count(*) AS contratos,
             min(dias) AS minimo,
             percentile_cont(0.05) WITHIN GROUP (ORDER BY dias) AS p05,
             percentile_cont(0.50) WITHIN GROUP (ORDER BY dias) AS mediana,
             percentile_cont(0.95) WITHIN GROUP (ORDER BY dias) AS p95,
             count(*) FILTER (WHERE dias <= 1) AS en_un_dia_o_menos
      FROM p WHERE dias >= 0 AND modalidad IS NOT NULL
      GROUP BY 1 HAVING count(*) >= 30
      ORDER BY contratos DESC
    ) f
  ),

  -- Cuánta alerta produciría cada umbral. Es el número que decide si una
  -- Regla es usable: 20 000 alertas al día no las revisa nadie.
  'costo_de_umbral', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT u AS umbral_dias,
             count(*) FILTER (WHERE dias <= u) AS alertas,
             round(100.0 * count(*) FILTER (WHERE dias <= u) / nullif(count(*),0), 1) AS pct
      FROM p, (VALUES (0),(1),(2),(3),(5),(7),(10)) AS t(u)
      WHERE dias >= 0
      GROUP BY u ORDER BY u
    ) f
  ),

  -- Firmado ANTES de publicarse el proceso. No es una bandera del catálogo:
  -- es imposible, y por eso hay que mirarlo. O la fuente trae fechas mal, o
  -- hay algo que explicar.
  'imposibles', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT id_contrato, nombre_entidad AS entidad, modalidad,
             fecha_de_publicacion AS publicado, fecha_de_firma AS firmado,
             dias, valor
      FROM p WHERE dias < 0 ORDER BY dias ASC LIMIT 10
    ) f
  ),

  'imposibles_por_modalidad', (
    SELECT coalesce(json_agg(f), '[]'::json) FROM (
      SELECT coalesce(modalidad,'(sin modalidad)') AS modalidad,
             count(*) AS contratos, min(dias) AS peor
      FROM p WHERE dias < 0 GROUP BY 1 ORDER BY contratos DESC LIMIT 8
    ) f
  )

) AS plazos;
