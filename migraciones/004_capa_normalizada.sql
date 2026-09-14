-- Capa normalizada: Contratos y Procesos tipados, y el cruce entre ellos (FR-2).
--
-- Se deriva de la capa cruda y nunca de la fuente. El crudo es el registro de
-- lo que llegó; esto es una lectura de ese registro, y por eso se puede
-- reconstruir entera desde él sin volver a pedirle nada al SECOP.
--
-- LA LLAVE DE CRUCE. `contrato.proceso_de_compra` (espacio `CO1.BDOS.`) se une
-- contra `proceso.id_del_portafolio`, NO contra `proceso.id_del_proceso`, que
-- vive en el espacio `CO1.REQ.` y no comparte un solo valor con Contratos.
-- El PRD decía lo contrario. Medido y corregido el 2026-09-03; la evidencia
-- está en `sprint-change-proposal-2026-09-03.md`.
--
-- EL GRANO DE PROCESOS. El dataset `p6dx-8zbt` tiene una fila por
-- ADJUDICACIÓN, no por Proceso: un procedimiento de varios lotes con varios
-- adjudicatarios aparece muchas veces (medido: 21 filas para
-- `CO1.REQ.10772032`). Por eso `proceso` se llena deduplicando y `ciclo`
-- cuenta cuántas filas colapsó. El detalle por adjudicatario se queda en el
-- crudo hasta la historia 1.5.

CREATE TABLE IF NOT EXISTS proceso (
    id_del_proceso        text        PRIMARY KEY,
    id_del_portafolio     text,
    referencia            text,
    nit_entidad           text,
    nombre_entidad        text,
    fecha_de_publicacion  date,
    modalidad             text,
    estado                text,
    adjudicado            boolean,
    -- Procedencia: de qué fila cruda salió esta. Sin esto, la capa normalizada
    -- es una afirmación sin respaldo, y el Expediente que exige INV-1 no se
    -- puede armar.
    id_fila_fuente        text        NOT NULL,
    hash_contenido        text        NOT NULL,
    normalizado_en        timestamptz NOT NULL
);

COMMENT ON TABLE proceso IS
    'Procesos de contratación, deduplicados: el dataset trae una fila por adjudicación.';
COMMENT ON COLUMN proceso.id_del_portafolio IS
    'Identificador CO1.BDOS.*. Es el lado de Procesos de la llave de cruce con Contratos.';
COMMENT ON COLUMN proceso.hash_contenido IS
    'Huella de la fila cruda de la que se derivó. Permite rehacer la normalización y comprobarla.';

-- El cruce va del contrato al portafolio, así que este índice es el que sostiene
-- la consulta principal de la 1.4. No es único a propósito: no está medido si
-- un portafolio puede tener varios procesos, y una restricción de unicidad
-- basada en una suposición rompe la ingesta el día que la suposición falle.
CREATE INDEX IF NOT EXISTS proceso_portafolio_idx
    ON proceso (id_del_portafolio)
    WHERE id_del_portafolio IS NOT NULL;


CREATE TABLE IF NOT EXISTS contrato (
    id_contrato            text        PRIMARY KEY,
    -- La llave de cruce, tal como viene de Contratos. Puede faltar: se cuenta
    -- aparte de los huérfanos porque es un fallo distinto, con causa distinta.
    proceso_de_compra      text,
    -- Resultado del cruce. NULL con `proceso_de_compra` poblado = huérfano.
    id_del_proceso         text        REFERENCES proceso (id_del_proceso),
    referencia             text,
    nit_entidad            text,
    nombre_entidad         text,
    valor                  numeric,
    fecha_de_firma         date,
    estado                 text,
    id_fila_fuente         text        NOT NULL,
    hash_contenido         text        NOT NULL,
    normalizado_en         timestamptz NOT NULL,

    -- Un contrato sin llave no puede tener proceso enlazado: si lo tuviera,
    -- el enlace se habría inventado en alguna parte.
    CONSTRAINT contrato_enlace_exige_llave
        CHECK (id_del_proceso IS NULL OR proceso_de_compra IS NOT NULL)
);

COMMENT ON TABLE contrato IS
    'Contratos tipados, enlazados a su Proceso cuando la llave de cruce encuentra uno.';
COMMENT ON COLUMN contrato.proceso_de_compra IS
    'Identificador CO1.BDOS.* que trae Contratos. Pese al nombre, NO es un id_del_proceso.';
COMMENT ON COLUMN contrato.id_del_proceso IS
    'Proceso enlazado, o NULL. NULL con proceso_de_compra poblado significa huérfano: se conserva y es consultable, nunca se descarta.';

-- «Cuáles quedaron huérfanos» es la consulta de calidad de datos de cada
-- Ciclo. Parcial, porque solo interesan esos.
CREATE INDEX IF NOT EXISTS contrato_huerfanos_idx
    ON contrato (fecha_de_firma DESC)
    WHERE id_del_proceso IS NULL AND proceso_de_compra IS NOT NULL;

-- Las reglas de las épicas 2 y 4 recorren por entidad y por fecha.
CREATE INDEX IF NOT EXISTS contrato_entidad_fecha_idx
    ON contrato (nit_entidad, fecha_de_firma DESC);


-- Señales de la normalización, en el registro del Ciclo que ya existe.
--
-- `huerfanos` estaba reservada desde la 003 y la llena esta historia. Las
-- otras tres son nuevas y responden a preguntas que se confunden con
-- facilidad: cuántos contratos ni siquiera traían la llave, cuántos Procesos
-- quedaron tras deduplicar, y cuántas filas se colapsaron al hacerlo.
ALTER TABLE ciclo ADD COLUMN IF NOT EXISTS normalizados integer;
ALTER TABLE ciclo ADD COLUMN IF NOT EXISTS sin_llave_de_cruce integer;
ALTER TABLE ciclo ADD COLUMN IF NOT EXISTS procesos_colapsados integer;

COMMENT ON COLUMN ciclo.huerfanos IS
    'Contratos CON llave de cruce que no encontraron Proceso. Su proporción sobre `normalizados` es el indicador de FR-2.';
COMMENT ON COLUMN ciclo.sin_llave_de_cruce IS
    'Contratos SIN proceso_de_compra poblado. Se cuenta aparte de los huérfanos: un campo declarado que llega vacío es otro fallo, y sumarlos lo esconde.';
COMMENT ON COLUMN ciclo.procesos_colapsados IS
    'Filas crudas de Procesos descartadas por deduplicación. Una deduplicación silenciosa es indistinguible de una pérdida de datos.';

-- Los conteos de normalización no pueden ser negativos ni superar el total
-- normalizado. Es la misma disciplina que ya tienen las señales de la 1.2:
-- que la base rechace lo incoherente en vez de confiar en quien escribe.
ALTER TABLE ciclo DROP CONSTRAINT IF EXISTS ciclo_conteos_de_normalizacion;
ALTER TABLE ciclo ADD CONSTRAINT ciclo_conteos_de_normalizacion CHECK (
    (normalizados        IS NULL OR normalizados        >= 0) AND
    (huerfanos           IS NULL OR huerfanos           >= 0) AND
    (sin_llave_de_cruce  IS NULL OR sin_llave_de_cruce  >= 0) AND
    (procesos_colapsados IS NULL OR procesos_colapsados >= 0) AND
    (normalizados IS NULL OR huerfanos          IS NULL OR huerfanos          <= normalizados) AND
    (normalizados IS NULL OR sin_llave_de_cruce IS NULL OR sin_llave_de_cruce <= normalizados)
);
