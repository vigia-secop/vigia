-- ¿Quién es el proveedor sin razón social del Panel? (pregunta de Guillermo)
--
-- SOLO LECTURA. Dos preguntas, y la segunda es la que importa:
--   1. ¿Qué dice el contrato?
--   2. ¿La razón social viene vacía DE LA FUENTE, o la perdimos nosotros al
--      normalizar? Culpar a la fuente sin comprobarlo es la forma más cómoda
--      de no encontrar un fallo propio.

\pset border 2
\pset numericlocale on

-- 1. El contrato, tal como quedó normalizado.
SELECT id_contrato, proveedor_tipo, proveedor_numero, proveedor_nombre,
       left(nombre_entidad, 44) AS entidad, nit_entidad,
       valor::numeric(20,0), estado, fecha_de_firma,
       departamento_nombre, orden
FROM contrato
WHERE proveedor_numero = '900445736';

-- 2. LO QUE DIJO LA FUENTE, sin pasar por nuestro código.
SELECT contenido->>'proveedor_adjudicado'   AS razon_social_en_la_fuente,
       contenido->>'documento_proveedor'    AS documento,
       contenido->>'tipodocproveedor'       AS tipo_doc,
       contenido->>'es_grupo'               AS es_grupo,
       contenido->>'estado_contrato'        AS estado,
       contenido->>'nombre_representante_legal' AS representante,
       contenido->>'descripcion_del_proceso'    AS objeto,
       contenido->'urlproceso'->>'url'      AS enlace_secop
FROM crudo_registro
WHERE dataset = 'contratos'
  AND contenido->>'documento_proveedor' = '900445736'
ORDER BY consultado_en DESC
LIMIT 3;

-- 3. ¿Es un caso aislado o un patrón? Cuántos contratos traen documento
--    utilizable Y razón social centinela, y cuánta plata mueven.
SELECT count(*) AS contratos,
       sum(valor)::numeric(20,0) AS valor,
       count(DISTINCT proveedor_numero) AS documentos_distintos
FROM contrato
WHERE proveedor_tipo IS NOT NULL
  AND upper(coalesce(proveedor_nombre,'')) IN
      ('NO DEFINIDO','SIN DESCRIPCION','NO DEFINIDA','NO APLICA','');

-- 4. Los diez mayores de ese patrón: son proveedores identificables por
--    documento a los que la entidad no les escribió el nombre.
SELECT proveedor_numero, left(nombre_entidad, 46) AS entidad,
       valor::numeric(20,0), estado, fecha_de_firma
FROM contrato
WHERE proveedor_tipo IS NOT NULL
  AND upper(coalesce(proveedor_nombre,'')) IN
      ('NO DEFINIDO','SIN DESCRIPCION','NO DEFINIDA','NO APLICA','')
ORDER BY valor DESC NULLS LAST
LIMIT 10;
