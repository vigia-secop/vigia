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

-- LAS ERRATAS x10^n: FUERA DE LOS TOTALES, PERO PUBLICADAS APARTE.
--
-- El 2026-09-15 el Panel publico dejo a FUNDACION MIL COLORES MAS en el
-- segundo puesto de «Proveedores por valor» con $433,5 mil millones. De esos,
-- $431,3 mil millones son el contrato de Tipacoque, que es una errata de
-- tecleo: el presupuesto de su proceso eran $431.340.000.
--
-- El primer intento fue marcarlas y dejarlas en el ranking. No alcanzo: de
-- una tabla se lee el puesto, y «segundo mayor contratista del pais» es un
-- senalamiento aunque tenga una etiqueta al lado.
--
-- La regla quedo en dos mitades, y las dos son necesarias:
--
--   1. FUERA de todos los totales y rankings, porque sumarlas es afirmar una
--      cifra que no se puede sostener.
--   2. PUBLICADAS EN SU PROPIA SECCION, una por una, con nombre, con las dos
--      cifras y con el enlace al SECOP -- porque un valor mal tecleado en una
--      base publica ES algo que vale la pena mirar, y esconderlo detras de un
--      conteo seria el mismo pecado que sumarlo.
--
-- Vigia no corrige la fuente ni adivina el valor verdadero. Aparta lo que no
-- puede sostener, dice cuanto aparto, y enlaza la ficha para que cualquiera
-- vaya a ver.
WITH errata_panel AS MATERIALIZED (
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

-- EL UNIVERSO SOBRE EL QUE SE CALCULA TODO LO DEMAS.
--
-- Una errata x10^n no es un hallazgo sobre nadie: es un defecto de la fuente.
-- Marcarla al lado del renglon no alcanzaba. El 2026-09-15 FUNDACION MIL
-- COLORES MAS quedo segunda entre los proveedores del pais por $433,5 mil
-- millones, de los cuales $431,3 mil millones eran un contrato de Tipacoque
-- tecleado con tres ceros de mas. La etiqueta estaba; el puesto tambien. Y
-- lo que la gente lee de una tabla es el puesto.
--
-- Asi que se tratan igual que los valores imposibles, que es la regla que ya
-- tenia esta pagina: FUERA de todos los totales y rankings, DECLARADOS en
-- cobertura con su cifra tal como la fuente la publica, y listados uno por
-- uno en la pagina de revision. Vigia no corrige la fuente ni adivina el
-- valor verdadero: aparta lo que no puede sostener, y dice cuanto aparto.
publicable AS (
  SELECT c.* FROM contrato c
  WHERE NOT EXISTS (
    SELECT 1 FROM errata_panel e WHERE e.id_del_proceso = c.id_del_proceso
  )
)
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
    ) FROM publicable WHERE valor_fuera_de_escala IS NOT TRUE
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
        coalesce(sum(valor) FILTER (WHERE valor_fuera_de_escala), 0),
      -- LAS ERRATAS x10^n, POR LA MISMA RAZON Y EN EL MISMO SITIO.
      -- El valor adjudicado es EXACTAMENTE una potencia de diez del
      -- presupuesto de su propio proceso: la firma de una tecla, no la de
      -- un sobrecosto. `declarado` es lo que sumarian si no se apartaran.
      'errata_potencia_diez', count(*) FILTER (WHERE tiene_errata),
      'valor_declarado_errata',
        coalesce(sum(valor) FILTER (WHERE tiene_errata), 0)
    ) FROM (
      SELECT c.*, (e.id_del_proceso IS NOT NULL) AS tiene_errata
      FROM contrato c
      LEFT JOIN errata_panel e USING (id_del_proceso)
    ) c
  ),

  -- LOS APARTADOS, UNO POR UNO, CON NOMBRE Y CON ENLACE.
  --
  -- Apartar un contrato de los rankings NO es dejar de publicarlo, y esa
  -- distincion es el corazon de esta pagina. Si el aviso dijera solo «4
  -- contratos, $653,5 mil millones», estariamos escondiendo un hallazgo
  -- detras de un conteo: quien lee no sabria a quien mirar, y un valor mal
  -- tecleado en una base publica ES algo que vale la pena mirar. Puede ser una
  -- tecla; tambien puede ser que alguien registro mal una cifra que importa.
  --
  -- La diferencia con tenerlo en el ranking no es el dato, es la afirmacion.
  -- En «Proveedores por valor» el renglon dice «este es de los que mas
  -- contrata del pais», y eso es falso. Aqui dice «este numero no cuadra con
  -- el presupuesto de su propio proceso, ve y abre la ficha», que es lo unico
  -- que se puede sostener. Mismo dato, afirmacion distinta.
  --
  -- Van TODOS y no solo el mayor: son pocos por definicion, y elegir cual
  -- mostrar seria volver a decidir por el lector.
  --
  -- El nombre del proveedor sale solo si es una EMPRESA. Si el contratista es
  -- persona natural se publica «Persona natural»: el interes publico esta en
  -- la entidad que firmo y en la cifra, no en el nombre de un particular.
  'erratas', (
    SELECT json_agg(f) FROM (
      SELECT c.id_contrato,
             c.nombre_entidad                AS entidad,
             c.departamento_nombre           AS departamento,
             CASE
               WHEN c.proveedor_tipo ~* 'c[eé]dula|pasaporte|nuip|tarjeta de identidad|registro civil|permiso (especial|por)'
                 THEN 'Persona natural'
               ELSE coalesce(nullif(c.proveedor_nombre, ''), 'Sin razón social')
             END                             AS proveedor,
             c.valor,
             e.base                          AS presupuesto_del_proceso,
             round(c.valor / nullif(e.base, 0))::bigint AS veces,
             -- SIN `LIMIT 1`, Y ESO NO ES UN DESCUIDO. Ver la explicacion
             -- larga en `banderas.sql`: con LIMIT, el planificador agarra el
             -- indice de fecha y tarda 14 segundos POR CONTRATO; sin LIMIT
             -- usa el indice del id y tarda 1,1 ms. Aqui son 50 contratos:
             -- once minutos contra cero. Medido el 2026-09-20.
             (SELECT (array_agg(r.contenido->'urlproceso'->>'url'
                                ORDER BY r.consultado_en DESC))[1]
              FROM crudo_registro r
              WHERE r.dataset = 'contratos'
                AND r.contenido->>'id_contrato' = c.id_contrato) AS enlace
      FROM contrato c JOIN errata_panel e USING (id_del_proceso)
      WHERE c.valor IS NOT NULL
      ORDER BY c.valor DESC
      LIMIT 50
    ) f
  ),

  -- Concentración por proveedor. EXCLUYE las identidades provisionales a
  -- propósito: cada una vale por un solo contrato, así que aparecerían con
  -- una concentración de 1 que no significa nada. Su total va aparte, arriba.
  'proveedores', (
    SELECT json_agg(f) FROM (
      SELECT c.proveedor_nombre AS nombre,
             c.proveedor_tipo AS tipo, c.proveedor_numero AS numero,
             count(*) AS contratos,
             coalesce(sum(c.valor), 0) AS valor,
             count(DISTINCT c.nit_entidad) AS entidades
      FROM publicable c
      WHERE c.proveedor_provisional IS FALSE AND c.valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1, 2, 3
      ORDER BY sum(c.valor) DESC NULLS LAST
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
      FROM publicable
      WHERE proveedor_provisional AND valor_fuera_de_escala IS NOT TRUE
      ORDER BY valor DESC NULLS LAST
      LIMIT 15
    ) f
  ),

  'ordenes', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(orden, 'SIN DECLARAR') AS orden,
             count(*) AS contratos, coalesce(sum(valor), 0) AS valor
      FROM publicable WHERE valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1 ORDER BY sum(valor) DESC NULLS LAST
    ) f
  ),

  'departamentos', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(departamento_codigo, '--') AS codigo,
             coalesce(departamento_nombre, 'SIN DEPARTAMENTO') AS nombre,
             count(*) AS contratos, coalesce(sum(valor), 0) AS valor
      FROM publicable WHERE valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1, 2 ORDER BY sum(valor) DESC NULLS LAST
    ) f
  ),

  'entidades', (
    SELECT json_agg(f) FROM (
      SELECT c.nombre_entidad AS nombre, c.nit_entidad AS nit,
             count(*) AS contratos, coalesce(sum(c.valor), 0) AS valor,
             count(DISTINCT (c.proveedor_tipo, c.proveedor_numero))
               FILTER (WHERE c.proveedor_provisional IS FALSE) AS proveedores
      FROM publicable c
      WHERE c.nombre_entidad IS NOT NULL
        AND c.valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1, 2 ORDER BY sum(c.valor) DESC NULLS LAST LIMIT 20
    ) f
  ),

  'modalidades', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(p.modalidad, '(sin modalidad)') AS modalidad,
             count(*) AS contratos, coalesce(sum(c.valor), 0) AS valor
      FROM publicable c JOIN proceso p USING (id_del_proceso)
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
        FROM publicable WHERE valor_fuera_de_escala IS NOT TRUE
      ) t GROUP BY tramo, orden ORDER BY orden
    ) f
  ),

  -- LOS QUINCE MAYORES, YA SIN LAS ERRATAS.
  --
  -- El 2026-09-11 el primero de esta lista era la ALCALDIA DE TIPACOQUE
  -- -municipio de unos 3.000 habitantes- con $431.340.000.000. El presupuesto
  -- del proceso era $431.340.000: el mismo numero con TRES CEROS DE MAS.
  --
  -- El techo de valores imposibles (1e14) no lo atajo y nunca pudo: 431 mil
  -- millones es un contrato posible. Durante cuatro dias la fila encabezo el
  -- ranking. Primero se marco; desde el 2026-09-15 se aparta, como los
  -- imposibles, y la cifra apartada se declara en cobertura. Un renglon
  -- marcado en un ranking sigue siendo un renglon en un ranking.
  'contratos_mayores', (
    SELECT json_agg(f) FROM (
      SELECT c.id_contrato, c.proveedor_nombre AS proveedor,
             c.nombre_entidad AS entidad, c.valor, c.estado,
             c.departamento_nombre AS departamento,
             c.proveedor_provisional AS es_union_temporal
      FROM publicable c
      WHERE c.valor IS NOT NULL
        AND c.valor_fuera_de_escala IS NOT TRUE
      ORDER BY c.valor DESC LIMIT 15
    ) f
  ),

  'por_dia', (
    SELECT json_agg(f) FROM (
      SELECT fecha_de_firma AS dia, count(*) AS contratos,
             coalesce(sum(valor), 0) AS valor
      FROM publicable WHERE fecha_de_firma IS NOT NULL
        AND valor_fuera_de_escala IS NOT TRUE
      GROUP BY 1 ORDER BY 1
    ) f
  )

) AS panel;

