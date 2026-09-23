-- LISTA DE REVISIÓN: qué mirar primero. SOLO LECTURA.
--
--     psql -tA -f revision.sql -o revision.json
--
-- QUÉ ES ESTO Y QUÉ NO ES. No son alertas. Ninguna fila de aquí afirma que
-- haya un problema: son contratos y procesos que **valen la pena mirar antes
-- que los otros**, y cada uno con la razón concreta por la que se lista.
--
-- Todos los criterios de este archivo son HECHOS SOBRE EL DATO, medidos y
-- verificables, no juicios sobre la conducta de nadie:
--
--   · un contrato grande cuya razón social la fuente no diligenció
--   · una unión temporal sin documento moviendo mucha plata
--   · un contrato que trae llave de cruce y no encontró su Proceso
--   · un proceso competitivo de alto valor con un solo oferente
--
-- Que algo esté aquí significa «esto todavía no lo sabemos» o «esto es grande
-- y conviene verlo», nunca «esto está mal». La diferencia es todo el proyecto.

SELECT json_build_object(

  'generado_en', now(),

  'ventana', (
    SELECT json_build_object('desde', min(fecha_de_firma), 'hasta', max(fecha_de_firma),
                             'contratos', count(*), 'valor', coalesce(sum(valor),0))
    FROM contrato
  ),

  -- 1. Contratos grandes sin razón social. El dato existe (hay documento) pero
  --    la entidad no escribió el nombre. El mayor de la ventana es uno de
  --    estos: $118 mil millones de alimentación escolar.
  'sin_razon_social', (
    SELECT json_agg(f) FROM (
      -- EL ENLACE AL SECOP ES LA COLUMNA QUE IMPORTA. Un lector que quiera
      -- comprobar algo no necesita que nosotros le repitamos la cédula: con
      -- el enlace llega a la ficha oficial del contrato, donde está el
      -- nombre, el documento, el objeto y los soportes — en la fuente, que es
      -- donde ese dato se puede defender.
      --
      -- Republicar el documento da MENOS: es un número suelto, sin contexto,
      -- que ya no se puede retirar. El enlace da todo y no publica nada.
      SELECT c.id_contrato, c.proveedor_tipo AS tipo, c.proveedor_numero AS documento,
             c.nombre_entidad AS entidad, c.nit_entidad,
             c.valor, c.estado, c.fecha_de_firma,
             c.departamento_nombre AS departamento,
             -- SIN `LIMIT 1`, y aqui es donde mas se notaba: esta lista trae
             -- unas 53 filas, y a 14 segundos cada enlace eran doce minutos
             -- de los diecisiete que tardaba la pagina entera. Ver la
             -- explicacion en `banderas.sql`. Medido el 2026-09-20.
             (SELECT (array_agg(r.contenido->'urlproceso'->>'url'
                                ORDER BY r.consultado_en DESC))[1]
              FROM crudo_registro r
              WHERE r.dataset = 'contratos'
                AND r.contenido->>'id_contrato' = c.id_contrato) AS enlace
      FROM contrato c
      WHERE c.proveedor_tipo IS NOT NULL
        AND upper(coalesce(c.proveedor_nombre,'')) IN
            ('NO DEFINIDO','SIN DESCRIPCION','NO DEFINIDA','NO APLICA','')
      ORDER BY c.valor DESC NULLS LAST LIMIT 25
    ) f
  ),

  -- 2. Uniones temporales y consorcios sin documento. Se cuentan y se ven,
  --    pero no se les puede medir concentración hasta conocer integrantes.
  'uniones_sin_documento', (
    SELECT json_agg(f) FROM (
      SELECT id_contrato, proveedor_nombre AS nombre, nombre_entidad AS entidad,
             nit_entidad, valor, estado, fecha_de_firma,
             departamento_nombre AS departamento
      FROM contrato WHERE proveedor_provisional
      ORDER BY valor DESC NULLS LAST LIMIT 25
    ) f
  ),

  -- 3. Huérfanos de alto valor: traen la llave de cruce y no encontraron su
  --    Proceso. Sin Proceso no hay modalidad, ni fecha de publicación, ni
  --    plazo que medir — o sea, quedan fuera de casi toda Regla futura.
  'huerfanos_grandes', (
    SELECT json_agg(f) FROM (
      SELECT id_contrato, proceso_de_compra, proveedor_nombre AS proveedor,
             nombre_entidad AS entidad, valor, estado, fecha_de_firma
      FROM contrato
      WHERE id_del_proceso IS NULL AND proceso_de_compra IS NOT NULL
      ORDER BY valor DESC NULLS LAST LIMIT 20
    ) f
  ),

  -- 0. VALORES QUE NO PUEDEN SER CIERTOS. Va PRIMERO en el JSON aunque se
  --    dibuje donde toque, porque es lo único de esta página que no habla de
  --    un contrato sino de nuestra propia capacidad de contar: mientras haya
  --    uno de estos dentro de un total, ese total es falso.
  --
  --    Se listan con su valor TAL COMO LA FUENTE LO PUBLICA. Vigía no corrige
  --    la fuente ni adivina cuál era el número verdadero; enseña el que está
  --    escrito y dice que no puede ser.
  'valores_imposibles', (
    SELECT json_agg(f) FROM (
      SELECT id_contrato, nombre_entidad AS entidad,
             proveedor_nombre AS proveedor, proveedor_numero AS documento,
             valor, estado, fecha_de_firma
      FROM contrato
      WHERE valor_fuera_de_escala
      ORDER BY valor DESC LIMIT 25
    ) f
  ),

  -- 3.bis. LA ERRATA QUE EL TECHO NO ATAJA, Y POR QUÉ ESTÁ AQUÍ.
  --
  --   El 2026-09-11 esta misma lista mostró a la ALCALDÍA DE TIPACOQUE
  --   —municipio de unos 3.000 habitantes— firmando $431.340.000.000 con una
  --   fundación. Leído así, es una bomba. El proceso del que sale ese
  --   contrato tiene un presupuesto de $431.340.000: el mismo número con
  --   TRES CEROS DE MÁS.
  --
  --   El techo de valores imposibles (1e14) no lo atajó y nunca pudo: 431 mil
  --   millones es un contrato perfectamente posible. La errata ×1000 no se
  --   detecta por tamaño, se detecta por PROPORCIÓN — y esa comparación no
  --   estaba hecha, así que la fila salía desnuda y parecía un hallazgo.
  --
  --   La firma de la tecla es que la razón adjudicado ÷ presupuesto cae
  --   EXACTAMENTE sobre una potencia de diez. Un sobrecosto real da 2,3 ó
  --   12,4; una tecla de más da 1.000,000.
  --
  --   Se toma la adjudicación más reciente del proceso. Con varias
  --   adjudicaciones por proceso la comparación es aproximada, y por eso esto
  --   es una lista para mirar y no una corrección: la base guarda lo que la
  --   fuente publicó.
  'erratas_x1000', (
    SELECT json_agg(f) FROM (
      SELECT c.id_contrato, c.nombre_entidad AS entidad,
             c.proveedor_nombre AS proveedor, c.proveedor_tipo AS tipo,
             c.proveedor_numero AS documento,
             c.valor, c.estado, c.fecha_de_firma,
             c.departamento_nombre AS departamento,
             s.base                                          AS valor_probable,
             s.ceros                                         AS ceros_de_mas,
             -- SIN `LIMIT 1`, a proposito: ver `banderas.sql`.
             (SELECT (array_agg(r.contenido->'urlproceso'->>'url'
                                ORDER BY r.consultado_en DESC))[1]
              FROM crudo_registro r
              WHERE r.dataset = 'contratos'
                AND r.contenido->>'id_contrato' = c.id_contrato) AS enlace
      FROM contrato c
      JOIN (
        SELECT id_del_proceso, base, round(log(razon)) AS ceros
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
      ORDER BY c.valor DESC NULLS LAST LIMIT 25
    ) f
  ),

  -- 4. Un mismo documento con varias razones sociales. Puede ser un cambio de
  --    nombre legítimo o puede ser otra cosa; en los dos casos hay que verlo.
  'proveedores_con_varios_nombres', (
    SELECT json_agg(f) FROM (
      SELECT p.numero, p.tipo_documento AS tipo, p.nombre_principal,
             p.variantes, p.contratos,
             (SELECT json_agg(v.nombre ORDER BY v.contratos DESC)
              FROM proveedor_variante v
              WHERE v.tipo_documento = p.tipo_documento AND v.numero = p.numero) AS nombres
      FROM proveedor p
      WHERE p.variantes > 1 AND NOT p.provisional
      ORDER BY p.variantes DESC, p.contratos DESC LIMIT 15
    ) f
  ),

  -- 5. Procesos competitivos con un solo oferente que ADEMÁS recibieron más
  --    atención que el 90 % de los de su misma modalidad.
  --
  --    NO ES UNA BANDERA, y la medición del 2026-09-06 explica por qué con
  --    más fuerza que antes. Se midió la distribución de visualizaciones de
  --    los 2 334 competitivos adjudicados, separando los de un solo proveedor
  --    de los de varios, y las dos distribuciones **sí se separan — al revés
  --    de lo que se esperaba**:
  --
  --        un solo proveedor    mediana 16 visualizaciones
  --        varios proveedores   mediana 32
  --
  --    Un proceso que termina con una sola oferta es, por regla, uno que
  --    NADIE MIRÓ. Solo 30 de 1 239 —el 2,4 %— están por encima del p90 de su
  --    modalidad, cuando por azar serían ~124. Es decir: están
  --    infrarrepresentados en la cola de atención, no sobrerrepresentados.
  --
  --    Esos 30 son los que se listan aquí. No porque haya nada malo en ellos,
  --    sino porque son el caso raro dentro del caso raro, y mirarlos con los
  --    ojos es barato. El `percent_rank` se calcula sobre TODOS los
  --    competitivos adjudicados de la modalidad, no solo sobre los de un
  --    oferente: comparar contra los comparables es todo el punto.
  'competitivos_con_un_oferente', (
    SELECT json_agg(f) FROM (
      SELECT id_del_proceso, entidad, modalidad, valor, visualizaciones,
             invitados, proveedor, enlace,
             round(100 * atencion)::int AS percentil
      FROM (
        SELECT contenido->>'id_del_proceso'                    AS id_del_proceso,
               contenido->>'entidad'                           AS entidad,
               contenido->>'modalidad_de_contratacion'         AS modalidad,
               (contenido->>'valor_total_adjudicacion')::numeric AS valor,
               (contenido->>'visualizaciones_del')::numeric    AS visualizaciones,
               (contenido->>'proveedores_invitados')::numeric  AS invitados,
               contenido->>'nombre_del_proveedor'              AS proveedor,
               contenido->'urlproceso'->>'url'                 AS enlace,
               nullif(contenido->>'proveedores_unicos_con','')::numeric AS unicos,
               percent_rank() OVER (
                   PARTITION BY contenido->>'modalidad_de_contratacion'
                   ORDER BY nullif(contenido->>'visualizaciones_del','')::numeric
               ) AS atencion
        FROM (
          SELECT DISTINCT ON (contenido->>'id_del_proceso', contenido->>'id_adjudicacion')
                 contenido
          FROM crudo_registro WHERE dataset = 'procesos'
          ORDER BY contenido->>'id_del_proceso', contenido->>'id_adjudicacion',
                   consultado_en DESC
        ) u
        WHERE contenido->>'adjudicado' = 'Si'
          AND nullif(contenido->>'visualizaciones_del','') IS NOT NULL
          AND contenido->>'modalidad_de_contratacion' IN (
              'Licitación pública', 'Licitación pública Obra Publica',
              'Selección Abreviada de Menor Cuantía', 'Selección abreviada subasta inversa',
              'Seleccion Abreviada Menor Cuantia Sin Manifestacion Interes',
              'Concurso de méritos abierto',
              'Enajenación de bienes con sobre cerrado', 'Enajenación de bienes con subasta')
      ) c
      WHERE c.unicos = 1 AND c.atencion >= 0.90
      ORDER BY c.valor DESC NULLS LAST
      LIMIT 20
    ) f
  ),


  -- El conteo de erratas va aparte porque necesita el cruce con Procesos, y
  -- `conteos` solo recorre `contrato`. Va sin LÍMITE: la lista de arriba se
  -- corta en 25 filas y este número dice si se cortó.
  'conteo_erratas', (
    SELECT json_build_object('erratas', count(*),
                             'valor_erratas', coalesce(sum(c.valor), 0))
    FROM contrato c
    JOIN (
      SELECT id_del_proceso
      FROM (
        SELECT contenido->>'id_del_proceso' AS id_del_proceso,
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
  ),

  'conteos', (
    SELECT json_build_object(
      'sin_razon_social', count(*) FILTER (
          WHERE proveedor_tipo IS NOT NULL AND upper(coalesce(proveedor_nombre,'')) IN
                ('NO DEFINIDO','SIN DESCRIPCION','NO DEFINIDA','NO APLICA','')),
      'valor_sin_razon_social', coalesce(sum(valor) FILTER (
          WHERE proveedor_tipo IS NOT NULL AND upper(coalesce(proveedor_nombre,'')) IN
                ('NO DEFINIDO','SIN DESCRIPCION','NO DEFINIDA','NO APLICA','')), 0),
      'uniones', count(*) FILTER (WHERE proveedor_provisional),
      'valor_uniones', coalesce(sum(valor) FILTER (WHERE proveedor_provisional), 0),
      'huerfanos', count(*) FILTER (WHERE id_del_proceso IS NULL AND proceso_de_compra IS NOT NULL),
      'valor_huerfanos', coalesce(sum(valor) FILTER (
          WHERE id_del_proceso IS NULL AND proceso_de_compra IS NOT NULL), 0),
      'imposibles', count(*) FILTER (WHERE valor_fuera_de_escala),
      'valor_imposibles', coalesce(sum(valor) FILTER (WHERE valor_fuera_de_escala), 0)
    ) FROM contrato
  )

) AS revision;
