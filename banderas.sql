-- LOS GRUPOS PARA LA PAGINA PUBLICA DE BANDERAS. SOLO LECTURA.
--
--     psql -tA -f banderas.sql -o banderas.json
--
-- Es la misma consulta de `calibrar-fraccionamiento.sql` con una diferencia:
-- trae el DETALLE DE CADA CONTRATO —valor, fecha y enlace al SECOP—, porque
-- una ficha publicada tiene que poder comprobarse sin creernos nada. En la
-- calibración basta con los identificadores; aquí no.
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
-- EL DOCUMENTO DEL PROVEEDOR VA ENTERO EN ESTE JSON, Y ESTE JSON NO SE
-- PUBLICA: está en `.gitignore`. El enmascaramiento lo hace el generador de
-- la página, con la misma función que el resto del sitio — de una persona
-- natural no sale ni el nombre ni el documento completo.

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
         array_agg(id_contrato ORDER BY valor DESC) AS contratos_ids,
         -- Los contratos del grupo SIN el enlace. El enlace se busca abajo y
         -- solo para los grupos que de verdad se publican — ver el comentario
         -- de `con_enlace`.
         json_agg(json_build_object(
           'id_contrato', id_contrato,
           'valor', valor,
           'fecha', fecha_de_firma
         ) ORDER BY valor DESC)                    AS detalle
  FROM m
  GROUP BY 1, 3, 4, 5
),

-- LOS QUE PUEDEN LLEGAR A PUBLICARSE, SEPARADOS ANTES DE BUSCAR NINGUN ENLACE.
--
-- Un contrato solo no es un grupo. Son el 85,1 % de las minimas cuantias y no
-- pueden encender por definicion, asi que todo lo que se haga por ellos de
-- aqui en adelante es trabajo tirado.
--
-- Este CTE existe para que ESO SEA UNA CERTEZA Y NO UNA ESPERANZA. La version
-- anterior dejaba el `WHERE g.contratos > 1` despues del `CROSS JOIN LATERAL`
-- y confiaba en que el planificador lo empujara hacia abajo. Normalmente lo
-- hace; «normalmente» no es una garantia, y el precio de que no lo haga son
-- 9.423 busquedas por expresion sobre JSON en vez de 1.400. Ese fue el paso
-- que se quedo pegado ocho minutos el 2026-09-19.
publicables AS (
  SELECT * FROM grupo WHERE contratos > 1
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
             g.contratos_ids, con_enlace.detalle
      FROM publicables g JOIN techo t USING (nit_entidad)
      -- EL ENLACE SE BUSCA AQUI Y NO ARRIBA, Y LA DIFERENCIA ES DE MINUTOS.
      --
      -- La primera version lo metia dentro de `grupo`, que recorre las 9.423
      -- minimas cuantias. Cada enlace es una busqueda en `crudo_registro` por
      -- una EXPRESION sobre JSON, asi que eran 9.423 recorridos de una tabla
      -- de cientos de miles de documentos. El 2026-09-19 el paso de banderas
      -- llevaba mas de cinco minutos cuando el resto del sitio entero tardaba
      -- ocho.
      --
      -- Colgado de `publicables`, se busca solo para los ~1.400 grupos de dos
      -- o mas, que son los unicos que pueden salir publicados.
      CROSS JOIN LATERAL (
        SELECT json_agg(json_build_object(
                 'id_contrato', c->>'id_contrato',
                 'valor', (c->>'valor')::numeric,
                 'fecha', c->>'fecha',
                 -- EL `LIMIT 1` QUE COSTABA CATORCE SEGUNDOS POR CONTRATO.
                 --
                 -- Esta busqueda decia antes `ORDER BY consultado_en DESC
                 -- LIMIT 1`, que es la forma obvia de pedir «el registro mas
                 -- reciente de este contrato». Medido el 2026-09-20 con
                 -- EXPLAIN ANALYZE sobre la base de verdad:
                 --
                 --     con LIMIT 1 : 14.004 ms   POR CADA CONTRATO
                 --     sin LIMIT   :      1,1 ms
                 --
                 -- POR QUE. El `LIMIT 1` le hace creer al planificador que va
                 -- a parar temprano, asi que agarra el indice de FECHA y lo
                 -- recorre esperando toparse con el contrato. No se topa:
                 -- descartaba 270.888 filas antes de encontrarlo. Sin LIMIT
                 -- no tiene esa ilusion, tiene que traer las dos o tres filas
                 -- de ese contrato, y para eso usa el indice del ID, que es
                 -- el que sirve. El orden se hace despues, dentro del array.
                 --
                 -- Da exactamente lo mismo: la fila mas reciente, o NULL si
                 -- no hay ninguna. Se comprobo columna contra columna.
                 --
                 -- Banderas hace unas 4.000 de estas. A 14 segundos eran
                 -- quince horas y media: por eso el paso no terminaba nunca.
                 'enlace', (
                   SELECT (array_agg(r.contenido->'urlproceso'->>'url'
                                     ORDER BY r.consultado_en DESC))[1]
                   FROM crudo_registro r
                   WHERE r.dataset = 'contratos'
                     AND r.contenido->>'id_contrato' = c->>'id_contrato'
                 )
               ) ORDER BY (c->>'valor')::numeric DESC) AS detalle
        FROM json_array_elements(g.detalle) AS c
      ) con_enlace
    ) f
  )
) AS banderas;
