-- ¿CUÁNTAS IDENTIDADES DE PROVEEDOR SON FANTASMAS? SOLO LECTURA.
--
--     psql -tA -f fantasmas.sql -o fantasmas.json
--
-- QUÉ SE PREGUNTA Y POR QUÉ. La tabla `proveedor` se escribe con
-- `ON CONFLICT DO UPDATE`: se inserta y se actualiza, pero **nunca se borra
-- nada**. Eso es correcto mientras las identidades solo nazcan; deja de serlo
-- en cuanto una regla de identidad cambia.
--
-- Y cambió. El 2026-09-05 se añadió la regla de que un documento hecho de un
-- solo carácter repetido —`000000000`— no es un documento. Desde entonces
-- ningún contrato nuevo se le asigna. Pero **la fila vieja sigue ahí**, con
-- sus contadores congelados en lo que valían el día anterior, y las páginas
-- que leen `proveedor` la siguen mostrando como si existiera.
--
-- Hay un segundo caso más silencioso: los contadores `contratos` y
-- `variantes` se guardan, no se calculan al leer. Si un contrato cambia de
-- proveedor, el contador del proveedor viejo no se decrementa nunca, porque
-- ese proveedor no vuelve a pasar por la escritura.
--
-- Esta consulta NO arregla nada. Cuenta, para decidir con el número delante
-- si hace falta arreglarlo y de qué tamaño es.

SELECT json_build_object(

  'generado_en', now(),

  -- 1. FANTASMAS: identidades sin un solo contrato que las apunte hoy.
  'fantasmas', (
    SELECT json_build_object(
      'cuantos', count(*),
      'contratos_que_dicen_tener', coalesce(sum(p.contratos), 0)
    )
    FROM proveedor p
    WHERE NOT EXISTS (
      SELECT 1 FROM contrato c
      WHERE c.proveedor_tipo = p.tipo_documento
        AND c.proveedor_numero = p.numero
    )
  ),

  -- 2. Los quince fantasmas más grandes según su propio contador. Si el mayor
  --    dice tener muchos contratos, la fila lleva tiempo mintiendo.
  'fantasmas_mayores', (
    SELECT json_agg(f) FROM (
      SELECT p.tipo_documento AS tipo, p.numero, p.nombre_principal,
             p.contratos, p.variantes, p.normalizado_en
      FROM proveedor p
      WHERE NOT EXISTS (
        SELECT 1 FROM contrato c
        WHERE c.proveedor_tipo = p.tipo_documento
          AND c.proveedor_numero = p.numero
      )
      ORDER BY p.contratos DESC, p.variantes DESC
      LIMIT 15
    ) f
  ),

  -- 3. CONTADORES DESCUADRADOS: el `contratos` guardado contra el real.
  --    Se excluyen los fantasmas, que ya se contaron arriba.
  'contadores', (
    SELECT json_build_object(
      'identidades_vivas', count(*),
      'descuadradas', count(*) FILTER (WHERE r.reales <> p.contratos),
      'guardado_de_mas', count(*) FILTER (WHERE p.contratos > r.reales),
      'guardado_de_menos', count(*) FILTER (WHERE p.contratos < r.reales)
    )
    FROM proveedor p
    JOIN LATERAL (
      SELECT count(*) AS reales FROM contrato c
      WHERE c.proveedor_tipo = p.tipo_documento
        AND c.proveedor_numero = p.numero
    ) r ON TRUE
    WHERE r.reales > 0
  ),

  -- 4. El caso concreto que destapó todo esto, para verlo con nombre propio.
  'documentos_de_un_solo_caracter', (
    SELECT json_agg(f) FROM (
      SELECT p.tipo_documento AS tipo, p.numero, p.nombre_principal,
             p.contratos AS contratos_guardados,
             (SELECT count(*) FROM contrato c
              WHERE c.proveedor_tipo = p.tipo_documento
                AND c.proveedor_numero = p.numero) AS contratos_reales,
             p.variantes
      FROM proveedor p
      -- «un solo carácter distinto en todo el número», escrito en SQL.
      WHERE length(regexp_replace(p.numero, '(.)\1*', '\1', 'g')) = 1
      ORDER BY p.contratos DESC
      LIMIT 20
    ) f
  )

);
