-- LOS GRUPOS QUE VA A EVALUAR LA REGLA DE FRACCIONAMIENTO. SOLO LECTURA.
--
--     psql -tA -f calibrar-fraccionamiento.sql -o calibracion-fraccionamiento.json
--
-- Esta consulta NO decide nada: arma los grupos con todo lo que la Regla
-- necesita para decidir —contratos, suma, techo de la entidad, su percentil 95
-- y cuántas mínimas cuantías tiene— y los entrega. El umbral vive en la
-- versión de la Regla, no aquí, que es lo que exige la historia 2.1.
--
-- Una sola sentencia, a propósito: con `CREATE TEMP TABLE` delante, psql
-- escribe «SELECT 4» dentro del archivo de salida y el JSON deja de ser JSON.
--
-- SE DEVUELVEN TAMBIÉN LOS GRUPOS QUE NO SE VAN A PODER MIRAR, y eso es
-- deliberado. Una entidad con un techo imposible —una errata, una modalidad
-- mal puesta— tiene un tope inalcanzable: ningún grupo suyo encenderá nunca.
-- Si se filtraran aquí, la calibración diría «evalué 600 grupos» cuando en
-- realidad hay 700 y a 100 no las pudo mirar. Quien llama los separa y los
-- CUENTA: son la cobertura de la bandera.
--
-- EL DOCUMENTO DEL PROVEEDOR VA ENTERO Y ESTE ARCHIVO NO SE PUBLICA. Es
-- material de calibración, se queda en el escritorio, y está en `.gitignore`.
-- Lo que llegue a publicarse pasará por la misma regla de enmascaramiento que
-- el resto del sitio.

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

-- Las mínimas cuantías medibles: con proveedor real, valor útil, fecha, y sin
-- las erratas de tecleo. La modalidad vive en `proceso`, así que solo entran
-- las que cruzaron con el suyo.
m AS MATERIALIZED (
  SELECT c.id_contrato, c.nit_entidad, c.nombre_entidad,
         c.proveedor_tipo, c.proveedor_numero,
         c.fecha_de_firma, c.valor
  FROM contrato c
  JOIN proceso p USING (id_del_proceso)
  WHERE p.modalidad ILIKE '%m_nima cuant_a%'
    AND c.proveedor_tipo IS NOT NULL
    AND c.proveedor_provisional IS FALSE
    AND c.valor_fuera_de_escala IS NOT TRUE
    AND c.valor > 0
    AND c.fecha_de_firma IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM errata e WHERE e.id_del_proceso = c.id_del_proceso
    )
),

-- El techo de cada entidad, leído de su propia conducta, y su percentil 95,
-- que es contra lo que se juzga si ese techo es creíble.
techo AS (
  SELECT nit_entidad,
         max(valor)                                                  AS techo,
         round((percentile_cont(0.95) WITHIN GROUP (ORDER BY valor))::numeric, 0) AS p95,
         count(*)                                                    AS minimas
  FROM m GROUP BY 1
),

-- Un grupo = misma entidad, mismo proveedor, mismo mes calendario.
grupo AS (
  SELECT nit_entidad,
         max(nombre_entidad)                       AS nombre_entidad,
         proveedor_tipo, proveedor_numero,
         date_trunc('month', fecha_de_firma)::date AS mes,
         count(*)                                  AS contratos,
         sum(valor)                                AS suma,
         array_agg(id_contrato ORDER BY valor DESC) AS contratos_ids
  FROM m
  GROUP BY 1, 3, 4, 5
)

SELECT json_build_object(
  'generado_en', now(),
  'recorte', json_build_object(
    'minimas_medibles', (SELECT count(*) FROM m),
    'entidades', (SELECT count(*) FROM techo),
    'grupos', (SELECT count(*) FROM grupo),
    'desde', (SELECT min(fecha_de_firma) FROM m),
    'hasta', (SELECT max(fecha_de_firma) FROM m)
  ),
  -- Solo los grupos de dos o más: un contrato solo no es un grupo, y son el
  -- 85,1 % de las mínimas cuantías. Mandarlos sería inflar el denominador de
  -- la calibración con registros que no pueden encender por definición.
  'grupos', (
    SELECT coalesce(json_agg(f ORDER BY f.suma DESC), '[]'::json) FROM (
      SELECT g.nit_entidad, g.nombre_entidad,
             g.proveedor_tipo, g.proveedor_numero,
             g.mes, g.contratos, g.suma,
             t.techo, t.p95 AS p95_entidad, t.minimas AS minimas_entidad,
             g.contratos_ids
      FROM grupo g JOIN techo t USING (nit_entidad)
      WHERE g.contratos > 1
    ) f
  )
) AS calibracion;
