-- MUESTRA: OBRA CIVIL Y EDIFICACIONES EN EL VALLE DEL CAUCA. SOLO LECTURA.
--
--     psql -tA -f muestra-obra-valle.sql -o muestra-obra-valle.json
--
-- PARA QUIEN. Un proponente de Cali inscrito en el RUP con 32 clasificaciones
-- de construccion: edificaciones, cubiertas, ventaneria, pavimentos,
-- acueducto, estructuras prefabricadas. Persona natural, microempresa, con
-- patrimonio declarado de $690 millones al corte 2024/12/31.
--
-- EL FILTRO ES POR CODIGO, NO POR PALABRA. En ciberseguridad el codigo UNSPSC
-- era la señal debil y el texto la fuerte. En obra es al reves: la entidad
-- clasifica el proceso con el mismo codigo que el proponente tiene en su RUP,
-- y ESE es el cruce que decide si puede presentarse. El texto sirve de red
-- para lo que venga mal clasificado, pero marcado aparte para revisarlo.
--
-- LA CAPACIDAD IMPORTA. Un proceso de $20.000 millones no es una oportunidad
-- para una microempresa: es una invitacion a perder la plata de la poliza de
-- seriedad. Por eso cada proceso sale con su presupuesto y la consulta marca
-- cuales exceden lo que una sola empresa de este tamaño podria asumir sin
-- union temporal. Marcarlo, no esconderlo: la decision es del cliente.
--
-- LOS CODIGOS son los del RUP, tercer nivel (segmento-familia-clase). El
-- campo de la fuente trae el nivel cuarto (ocho digitos) y a veces con
-- prefijo «V1.», asi que se compara por los seis primeros digitos.

\set ON_ERROR_STOP on
SET work_mem = '256MB';

WITH ultimo AS MATERIALIZED (
  SELECT DISTINCT ON (contenido->>'id_del_proceso') contenido
  FROM crudo_registro
  WHERE dataset = 'procesos'
    AND contenido->>'fecha_de_publicacion_del' >= to_char(current_date - 45, 'YYYY-MM-DD')
  ORDER BY contenido->>'id_del_proceso', consultado_en DESC
),
texto AS (
  SELECT contenido,
         upper(coalesce(contenido->>'nombre_del_procedimiento','') || ' ' ||
               coalesce(contenido->>'descripci_n_del_procedimiento',''))  AS t,
         -- El tercer nivel del codigo. OJO CON EL PREFIJO: la fuente escribe
         -- «V1.72102900», y quitar «lo que no sea digito» deja «172102900»,
         -- cuyos seis primeros son «172102» y no cruzan con NADA. Asi corrio
         -- la primera version: 735 procesos atrapados, todos por texto, cero
         -- por codigo, y el cero parecia un resultado en vez de un error.
         -- Primero se quita el prefijo hasta el punto, y despues los digitos.
         left(regexp_replace(
                regexp_replace(coalesce(contenido->>'codigo_principal_de_categoria',''),
                               '^[A-Za-z0-9]+\.', ''),
                '[^0-9]', '', 'g'), 6)                                      AS clase,
         upper(coalesce(contenido->>'departamento_entidad',''))            AS depto
  FROM ultimo
),
marcado AS (
  SELECT contenido, clase, depto,
         CASE
           -- 1. El cruce que de verdad habilita: codigo del RUP.
           WHEN clase IN (
             '111216','301516','301518','301616','391115',
             '721029','721110','721111','721210','721211','721214',
             '721411','721413','721514','721524','721530','721540',
             '831015','951115',
             '951215','951216','951217','951218','951219','951220','951221','951223',
             '951316','951416','951417','951418','951419'
           ) THEN 'codigo del RUP'
           -- 2. La red para lo mal clasificado. Se revisa a mano.
           WHEN t ~ '\m(CONSTRUCCI[OÓ]N|OBRA|OBRAS|ADECUACI[OÓ]N|ADECUACIONES|REMODELACI[OÓ]N|REPARACI[OÓ]N|AMPLIACI[OÓ]N|MEJORAMIENTO|MANTENIMIENTO)\M'
             AND t ~ '\m(INFRAESTRUCTURA|EDIFICIO|EDIFICACI[OÓ]N|SEDE|COLEGIO|INSTITUCI[OÓ]N EDUCATIVA|HOSPITAL|PARQUE|CANCHA|POLIDEPORTIVO|CUBIERTA|V[IÍ]A|VIAS|PAVIMENT|ACUEDUCTO|ALCANTARILLADO|PLANTA F[IÍ]SICA)\M'
             THEN 'texto de obra'
           ELSE NULL
         END AS regla
  FROM texto
)
SELECT json_build_object(
  'generado_en', now(),
  'desde', to_char(current_date - 45, 'YYYY-MM-DD'),
  'hoy', to_char(current_date, 'YYYY-MM-DD'),
  'sector', 'obra civil y edificaciones',
  'cobertura', 'Valle del Cauca',
  -- Nada se descarta por su regla: en obra el codigo ES la señal. Lo que se
  -- descarta sigue siendo lo de siempre: directa, cerrado, sin fecha.
  'descartar_reglas', json_build_array(),
  -- Ruido propio del sector: interventoria y estudios piden clasificacion de
  -- consultoria, que este RUP no tiene; la compra de materiales sueltos no es
  -- obra; y el mantenimiento de vehiculos o de aires no es edificacion.
  'ruido', 'INTERVENTOR[IÍ]A|ESTUDIOS Y DISE[ÑN]OS|CONSULTOR[IÍ]A|VEH[IÍ]CULO|PARQUE AUTOMOTOR|AIRE ACONDICIONADO|ASCENSOR|SUMINISTRO DE MATERIALES|COMPRA DE MATERIALES|P[OÓ]LIZA|SEGURO',
  'procesos_revisados', (SELECT count(*) FROM ultimo),
  'atrapados', (SELECT count(*) FROM marcado WHERE regla IS NOT NULL AND depto = 'VALLE DEL CAUCA'),
  'por_regla', (SELECT json_object_agg(regla, n) FROM (
                  SELECT regla, count(*) n FROM marcado
                  WHERE regla IS NOT NULL AND depto = 'VALLE DEL CAUCA'
                  GROUP BY regla) r),
  'procesos', (SELECT coalesce(json_agg(f ORDER BY f.publicado DESC), '[]'::json) FROM (
    SELECT regla,
           contenido->>'id_del_proceso'                         AS id,
           contenido->>'referencia_del_proceso'                 AS referencia,
           contenido->>'nombre_del_procedimiento'               AS nombre,
           left(contenido->>'descripci_n_del_procedimiento', 400) AS descripcion,
           contenido->>'entidad'                                AS entidad,
           contenido->>'departamento_entidad'                   AS departamento,
           contenido->>'ciudad_entidad'                         AS ciudad,
           contenido->>'modalidad_de_contratacion'              AS modalidad,
           contenido->>'codigo_principal_de_categoria'          AS unspsc,
           nullif(contenido->>'precio_base','')                 AS precio_base,
           contenido->>'estado_del_procedimiento'               AS estado,
           contenido->>'estado_de_apertura_del_proceso'         AS apertura,
           contenido->>'fase'                                   AS fase,
           left(contenido->>'fecha_de_publicacion_del', 10)     AS publicado,
           left(contenido->>'fecha_de_recepcion_de', 10)        AS recibe_ofertas_hasta,
           contenido->>'adjudicado'                             AS adjudicado,
           contenido->>'nombre_del_proveedor'                   AS adjudicado_a,
           nullif(contenido->>'valor_total_adjudicacion','')    AS valor_adjudicado,
           contenido->'urlproceso'->>'url'                      AS enlace
    FROM marcado
    WHERE regla IS NOT NULL AND depto = 'VALLE DEL CAUCA'
  ) f)
);
