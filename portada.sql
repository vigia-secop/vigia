-- LA PORTADA: el registro de un día, listo para internet. SOLO LECTURA.
--
--   psql -v dia="'2026-09-13'" -tA -f portada.sql -o portada.json
--
-- QUÉ ES ESTO Y EN QUÉ SE DIFERENCIA DEL BOLETÍN. `boletin.sql` es el resumen
-- semanal que alimenta el hilo, y su regla es absoluta: **no devuelve el
-- nombre de nadie**, ni de una persona ni de una empresa. Esta consulta es la
-- portada del sitio, se rehace todos los días, y la regla es distinta y más
-- fina:
--
--     **SÍ devuelve el nombre y el NIT de una EMPRESA.**
--     **NUNCA devuelve el documento entero de una PERSONA NATURAL.**
--
-- Y la segunda mitad no es una decisión del generador de HTML: **el
-- enmascarado se hace aquí, en el SQL**. Así, ninguna prisa, ningún cambio de
-- plantilla y ningún error mío al dibujar la página puede sacar una cédula a
-- internet, porque la consulta que alimenta el archivo nunca la tuvo.
--
-- POR QUÉ EL NIT VA COMPLETO. Donde está el poder está el NIT. Una empresa es
-- un actor comercial que pone su NIT en la factura y en la fachada; publicar
-- cuánto le contrató el Estado es control ciudadano sobre dinero público. Una
-- cédula es el número con el que se abre la vida entera de una persona, y el
-- contratista de prestación de servicios de una alcaldía no es el poder.
--
-- POR QUÉ EN LA PORTADA LA PERSONA NATURAL NO VA NI POR NOMBRE. La portada es
-- la superficie más amplificada del proyecto. El mismo renglón que en una
-- página de detalle es consulta, en la portada es señalamiento. Aquí las
-- personas naturales salen como «Persona natural» con su documento
-- enmascarado, y el enlace al SECOP lleva al registro oficial completo, que es
-- donde ese dato se puede defender. Si alguna vez se cambia esto, que sea una
-- decisión escrita, no un descuido.
--
-- EL ORDEN DE LAS SECCIONES NO ES DECORATIVO: la cobertura va antes que
-- cualquier ranking, siempre. Es lo único que casi nadie publica en Colombia y
-- es lo que hace honesto todo lo que viene después.
--
-- SE EXCLUYEN LOS VALORES IMPOSIBLES de todo total, igual que el Panel, y las
-- erratas ×10ⁿ se MARCAN pero no se excluyen: excluirlas sería corregir la
-- fuente a ojo.

\set ON_ERROR_STOP on

-- El destilado de procesos adjudicados con presupuesto utilizable. Sirve para
-- marcar las erratas ×10ⁿ: valor adjudicado que cae exactamente sobre una
-- potencia de diez del presupuesto de su propio proceso.
CREATE TEMP TABLE errata AS
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
  AND abs(razon / power(10::numeric, round(log(razon))) - 1) < 0.001;

CREATE INDEX ON errata (id_del_proceso);

-- Los contratos del día, ya con el valor utilizable. Se materializa porque
-- casi todas las secciones lo recorren.
CREATE TEMP TABLE hoy AS
SELECT * FROM contrato
WHERE fecha_de_firma = :dia::date
  AND valor_fuera_de_escala IS NOT TRUE;


SELECT json_build_object(

  'generado_en', now(),
  'dia', :dia::date,

  -- 1. EL DÍA. Lo básico, sin adjetivos.
  'cifras', (
    SELECT json_build_object(
      'contratos', count(*),
      'valor', coalesce(sum(valor), 0),
      'entidades', count(DISTINCT nit_entidad),
      'proveedores', count(DISTINCT (proveedor_tipo, proveedor_numero))
                     FILTER (WHERE proveedor_provisional IS FALSE),
      'nacional', count(*) FILTER (WHERE orden = 'NACIONAL'),
      'territorial', count(*) FILTER (WHERE orden = 'TERRITORIAL'),
      'mediana', round(percentile_cont(0.5) WITHIN GROUP (ORDER BY valor)::numeric, 0),
      'promedio', round(avg(valor)::numeric, 0)
    ) FROM hoy
  ),

  -- 2. CONTRA QUÉ SE COMPARA. El mismo día de la semana anterior, no «ayer»:
  --    un lunes contra un domingo no dice nada. El generador vuelve a dividir
  --    por días hábiles y descuenta festivos, que el SQL no conoce.
  'comparacion', (
    SELECT json_build_object(
      'dia_anterior', (:dia::date - 7),
      'contratos', count(*),
      'valor', coalesce(sum(valor), 0)
    ) FROM contrato
    WHERE fecha_de_firma = (:dia::date - 7)
      AND valor_fuera_de_escala IS NOT TRUE
  ),

  -- 3. LA COBERTURA, Y VA ANTES QUE CUALQUIER RANKING.
  --    Cuánto de lo que se firmó hoy se puede mirar de verdad.
  'cobertura', (
    SELECT json_build_object(
      'contratos', count(*),
      'valor', coalesce(sum(valor), 0),
      'con_identidad', count(*) FILTER (
          WHERE proveedor_tipo IS NOT NULL AND proveedor_provisional IS FALSE
            AND upper(coalesce(proveedor_nombre,'')) NOT IN
                ('NO DEFINIDO','SIN DESCRIPCION','NO DEFINIDA','NO APLICA','')),
      'valor_con_identidad', coalesce(sum(valor) FILTER (
          WHERE proveedor_tipo IS NOT NULL AND proveedor_provisional IS FALSE
            AND upper(coalesce(proveedor_nombre,'')) NOT IN
                ('NO DEFINIDO','SIN DESCRIPCION','NO DEFINIDA','NO APLICA','')), 0),
      'uniones', count(*) FILTER (WHERE proveedor_provisional),
      'valor_uniones', coalesce(sum(valor) FILTER (WHERE proveedor_provisional), 0),
      'sin_razon_social', count(*) FILTER (
          WHERE proveedor_provisional IS NOT TRUE
            AND upper(coalesce(proveedor_nombre,'')) IN
                ('NO DEFINIDO','SIN DESCRIPCION','NO DEFINIDA','NO APLICA','')),
      'valor_sin_razon_social', coalesce(sum(valor) FILTER (
          WHERE proveedor_provisional IS NOT TRUE
            AND upper(coalesce(proveedor_nombre,'')) IN
                ('NO DEFINIDO','SIN DESCRIPCION','NO DEFINIDA','NO APLICA','')), 0),
      'sin_departamento', count(*) FILTER (WHERE departamento_codigo IS NULL)
    ) FROM hoy
  ),

  -- 4. DÓNDE.
  'departamentos', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(departamento_nombre, 'Sin declarar') AS nombre,
             count(*) AS contratos, coalesce(sum(valor), 0) AS valor
      FROM hoy GROUP BY 1 ORDER BY 3 DESC LIMIT 12
    ) f
  ),

  -- 5. BAJO QUÉ MODALIDAD. Sale del Proceso enlazado; los contratos sin
  --    proceso se cuentan aparte en vez de repartirse.
  'modalidades', (
    SELECT json_agg(f) FROM (
      SELECT coalesce(p.modalidad, 'Sin proceso enlazado') AS nombre,
             count(*) AS contratos, coalesce(sum(h.valor), 0) AS valor
      FROM hoy h LEFT JOIN proceso p USING (id_del_proceso)
      GROUP BY 1 ORDER BY 2 DESC LIMIT 10
    ) f
  ),

  -- 6. DE QUÉ TAMAÑO. La mediana y el promedio se publican juntos a
  --    propósito: cuando se separan mucho, la diferencia ES la noticia.
  'tramos', (
    SELECT json_agg(f) FROM (
      SELECT CASE
               WHEN valor IS NULL      THEN 'g. sin valor'
               WHEN valor < 5e6        THEN 'a. menos de $5 M'
               WHEN valor < 2e7        THEN 'b. $5 M a $20 M'
               WHEN valor < 1e8        THEN 'c. $20 M a $100 M'
               WHEN valor < 1e9        THEN 'd. $100 M a $1.000 M'
               WHEN valor < 1e10       THEN 'e. $1.000 M a $10.000 M'
               ELSE                         'f. mas de $10.000 M'
             END                                   AS tramo,
             count(*)                              AS contratos,
             coalesce(sum(valor), 0)               AS valor
      FROM hoy GROUP BY 1 ORDER BY 1
    ) f
  ),

  -- 7. LOS MAYORES DEL DÍA.
  --
  --    Aquí está la regla de este archivo, hecha SQL. `proveedor` no es la
  --    columna de la base: es una expresión que sustituye el nombre de una
  --    persona natural por la etiqueta genérica, y su documento por la forma
  --    enmascarada. La columna con el número entero no sale de aquí.
  'mayores', (
    SELECT json_agg(f) FROM (
      SELECT h.id_contrato,
             CASE
               WHEN h.proveedor_provisional THEN coalesce(h.proveedor_nombre, 'Unión temporal')
               WHEN h.proveedor_tipo ~* 'c[eé]dula|pasaporte|nuip|tarjeta de identidad|registro civil|permiso (especial|por)'
                 THEN 'Persona natural'
               ELSE coalesce(nullif(h.proveedor_nombre, ''), 'Sin razón social')
             END                                                   AS proveedor,
             CASE
               WHEN h.proveedor_provisional THEN 'sin documento'
               WHEN h.proveedor_numero IS NULL THEN NULL
               WHEN h.proveedor_tipo ~* 'c[eé]dula|pasaporte|nuip|tarjeta de identidad|registro civil|permiso (especial|por)'
                 THEN repeat('•', greatest(length(h.proveedor_numero) - 3, 0))
                      || right(h.proveedor_numero, 3)
               ELSE coalesce(h.proveedor_tipo, '') || ' ' || h.proveedor_numero
             END                                                   AS documento,
             (h.proveedor_provisional IS TRUE)                     AS es_union,
             h.nombre_entidad                                      AS entidad,
             h.departamento_nombre                                 AS departamento,
             h.valor,
             (e.id_del_proceso IS NOT NULL)                        AS errata_probable,
             e.base                                                AS valor_probable,
             (SELECT r.contenido->'urlproceso'->>'url'
              FROM crudo_registro r
              WHERE r.dataset = 'contratos'
                AND r.contenido->>'id_contrato' = h.id_contrato
              ORDER BY r.consultado_en DESC LIMIT 1)               AS enlace
      FROM hoy h LEFT JOIN errata e USING (id_del_proceso)
      WHERE h.valor IS NOT NULL
      ORDER BY h.valor DESC LIMIT 10
    ) f
  ),

  -- 8. LA SERIE. Veintiocho días para que la portada tenga memoria y no sea
  --    una foto. El generador marca cuáles son hábiles: los festivos los sabe
  --    `vigia/calendario.py`, no el motor de la base.
  'serie', (
    SELECT json_agg(f) FROM (
      SELECT d::date AS dia,
             (SELECT count(*) FROM contrato c
              WHERE c.fecha_de_firma = d::date
                AND c.valor_fuera_de_escala IS NOT TRUE)            AS contratos,
             (SELECT coalesce(sum(c.valor), 0) FROM contrato c
              WHERE c.fecha_de_firma = d::date
                AND c.valor_fuera_de_escala IS NOT TRUE)            AS valor
      FROM generate_series(:dia::date - 27, :dia::date, '1 day') d
      ORDER BY 1
    ) f
  ),

  -- 9. LA VENTANA COMPLETA. Sobre cuánta historia se está hablando. Va en la
  --    portada porque «el municipio que más firmó» significa una cosa con 73
  --    días de datos y otra muy distinta con dos años.
  'ventana', (
    SELECT json_build_object(
      'primer_contrato', min(fecha_de_firma),
      'ultimo_contrato', max(fecha_de_firma),
      'contratos', count(*),
      'valor', coalesce(sum(valor), 0),
      'entidades', count(DISTINCT nit_entidad)
    ) FROM contrato WHERE valor_fuera_de_escala IS NOT TRUE
  ),

  -- 10. LA CALIDAD DEL DATO, publicada en la misma página que las cifras.
  --     Un sitio que publica sus propios defectos es más creíble que uno que
  --     publica solo lo que le sale bien.
  'calidad', (
    SELECT json_build_object(
      'erratas_hoy', (SELECT count(*) FROM hoy h JOIN errata e USING (id_del_proceso)),
      'valor_erratas_hoy', (SELECT coalesce(sum(h.valor), 0)
                            FROM hoy h JOIN errata e USING (id_del_proceso)),
      'erratas_ventana', (SELECT count(*) FROM contrato c JOIN errata e USING (id_del_proceso)),
      'imposibles', (SELECT count(*) FROM contrato WHERE valor_fuera_de_escala),
      'huerfanos_hoy', (SELECT count(*) FROM hoy
                        WHERE id_del_proceso IS NULL AND proceso_de_compra IS NOT NULL)
    )
  )
);

DROP TABLE hoy;
DROP TABLE errata;
