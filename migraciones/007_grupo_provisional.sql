-- Identidad provisional de Uniones Temporales y Consorcios (historia 1.5b).
--
-- EL PROBLEMA QUE ARREGLA. La 006 dejaba sin identidad a todo contrato cuyo
-- documento fuera un centinela, y los contaba como «no vigilables». Al medirlo
-- (2026-09-04) resultó que esa población son dos cosas muy distintas:
--
--   * 160 543 borradores y cancelados: papeles que NUNCA adjudicaron a nadie.
--     No tienen proveedor porque no hay proveedor. Siguen sin identidad, y
--     está bien: inventárselo sería peor.
--   * 15 291 contratos de verdad, de los cuales el 99,99 % traen
--     `es_grupo = 'Si'`: Uniones Temporales y Consorcios a los que la entidad
--     no les diligenció el documento. Estos SÍ son un hueco de vigilancia.
--
-- QUÉ SE HACE. Al segundo grupo se le da una identidad propia por contrato,
-- marcada como provisional. No funde a nadie con nadie —cada contrato es su
-- propia identidad— y por eso no puede inventar una concentración. Lo que
-- consigue es que esos contratos se cuenten, se sumen y se vean, en vez de
-- desaparecer del reporte.
--
-- POR QUÉ COLUMNA GENERADA Y NO UNA BANDERA QUE ESCRIBA PYTHON. Porque una
-- bandera que se escribe puede quedar desincronizada del tipo, y entonces la
-- base diría una cosa y el código otra. Generada, no puede: es el tipo.

-- En `proveedor` la columna es booleana pura: toda identidad tiene tipo.
ALTER TABLE proveedor ADD COLUMN IF NOT EXISTS provisional boolean
    GENERATED ALWAYS AS (
        tipo_documento = 'UNION TEMPORAL O CONSORCIO SIN DOCUMENTO'
    ) STORED;

COMMENT ON COLUMN proveedor.provisional IS
    'La identidad identifica a un contrato, no a un contratista: es una Unión Temporal o Consorcio sin documento. No puede concentrar nada, y «concentración por proveedor» (4.3) debe excluirla del ranking y reportarla aparte.';

-- En `contrato` son TRES estados, y los tres significan cosas distintas:
--   true  -> unión temporal o consorcio, contada pero no vigilable por 4.3
--   false -> identidad real, vigilable
--   NULL  -> sin identidad ninguna (casi siempre borrador o cancelado)
ALTER TABLE contrato ADD COLUMN IF NOT EXISTS proveedor_provisional boolean
    GENERATED ALWAYS AS (
        proveedor_tipo = 'UNION TEMPORAL O CONSORCIO SIN DOCUMENTO'
    ) STORED;

COMMENT ON COLUMN contrato.proveedor_provisional IS
    'true = unión temporal o consorcio sin documento (se cuenta, no se puede vigilar concentración); false = identidad real; NULL = sin identidad.';

-- La población que 4.3 no puede vigilar es la unión de dos: NULL y true.
-- Índice parcial para poder medirla sin recorrer la tabla entera.
CREATE INDEX IF NOT EXISTS contrato_proveedor_provisional_idx
    ON contrato (id_contrato) WHERE proveedor_provisional;

ALTER TABLE ciclo ADD COLUMN IF NOT EXISTS contratos_provisionales integer;
ALTER TABLE ciclo ADD COLUMN IF NOT EXISTS proveedores_provisionales integer;

COMMENT ON COLUMN ciclo.contratos_provisionales IS
    'Contratos de unión temporal o consorcio sin documento en este Ciclo. Sube = más plata fuera del alcance de la 4.3.';
