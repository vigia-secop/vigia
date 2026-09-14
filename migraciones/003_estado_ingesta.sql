-- Estado de la ingesta entre Ciclos (AD-4).
--
-- Dos tablas con vidas distintas: `ingesta_marca` es un puntero mutable —una
-- fila por dataset, hasta dónde se leyó— y `ciclo` es un histórico de solo
-- inserción de qué pasó en cada intento.
--
-- El cursor va sobre la FECHA DEL HECHO (firma del contrato, publicación del
-- proceso), no sobre una marca de actualización de la fuente: el SECOP no
-- publica una fiable. Medido el 2026-09-02: `ultima_actualizacion` viene vacío
-- en ~40% de los contratos y en la totalidad de los más recientes, y el
-- `:updated_at` de la plataforma se mueve entero en cada recarga del dataset.

CREATE TABLE IF NOT EXISTS ingesta_marca (
    dataset        text        PRIMARY KEY,
    fecha_hecho    date        NOT NULL,
    actualizada_en timestamptz NOT NULL
);

COMMENT ON TABLE ingesta_marca IS
    'Hasta qué fecha de hecho se leyó cada dataset. Avanza solo tras un Ciclo completo.';
COMMENT ON COLUMN ingesta_marca.fecha_hecho IS
    'Fecha del hecho, no de la lectura: es el único campo que la fuente llena siempre.';

CREATE TABLE IF NOT EXISTS ciclo (
    id                           bigserial   PRIMARY KEY,
    dataset                      text        NOT NULL,
    cursor_entrada               date,
    cursor_salida                date,
    desde                        date        NOT NULL,
    hasta                        date        NOT NULL,
    estado                       text        NOT NULL,
    inicio                       timestamptz NOT NULL,
    fin                          timestamptz NOT NULL,
    paginas                      integer     NOT NULL DEFAULT 0,
    vistos                       integer     NOT NULL DEFAULT 0,
    insertados                   integer     NOT NULL DEFAULT 0,
    duplicados                   integer     NOT NULL DEFAULT 0,
    recuperados_por_solapamiento integer     NOT NULL DEFAULT 0,
    en_borde_de_ventana          integer     NOT NULL DEFAULT 0,
    sin_fecha_de_hecho           integer     NOT NULL DEFAULT 0,
    -- La 1.4 la llenará; hoy el Ciclo todavía no sabe de huérfanos.
    huerfanos                    integer,
    causa                        text,
    novedades                    text[]      NOT NULL DEFAULT '{}',
    -- Con qué configuración corrió: sin esto no se puede calibrar la ventana
    -- leyendo el histórico, que es justo para lo que existe.
    ventana_dias                 integer,
    desde_derivado               boolean     NOT NULL DEFAULT false,
    CONSTRAINT ciclo_estado_conocido
        CHECK (estado IN ('completo', 'fallido')),
    -- Un Ciclo fallido sin causa es un Ciclo del que no se aprende nada.
    CONSTRAINT ciclo_fallido_con_causa
        CHECK (estado <> 'fallido' OR causa IS NOT NULL),
    -- Un Ciclo completo sin cursor de salida dejaría la marca sin a dónde ir.
    CONSTRAINT ciclo_completo_con_cursor
        CHECK (estado <> 'completo' OR cursor_salida IS NOT NULL),
    -- Solo se exige al completo: un fallido registra lo que se INTENTÓ, y un
    -- rango invertido es precisamente una de las causas por las que se falla.
    CONSTRAINT ciclo_rango_ordenado
        CHECK (estado <> 'completo' OR hasta >= desde),
    CONSTRAINT ciclo_intervalo_ordenado
        CHECK (fin >= inicio),
    CONSTRAINT ciclo_conteos_no_negativos
        CHECK (
            paginas >= 0 AND vistos >= 0 AND insertados >= 0 AND duplicados >= 0
            AND recuperados_por_solapamiento >= 0 AND en_borde_de_ventana >= 0
            AND sin_fecha_de_hecho >= 0
        ),
    CONSTRAINT ciclo_conteos_coherentes
        CHECK (insertados + duplicados = vistos),
    CONSTRAINT ciclo_senales_dentro_de_lo_insertado
        CHECK (
            recuperados_por_solapamiento <= insertados
            AND en_borde_de_ventana <= insertados
            AND sin_fecha_de_hecho <= insertados
        )
);

COMMENT ON TABLE ciclo IS
    'Histórico de ejecuciones de ingesta. Solo inserción. Un Ciclo vacío y uno fallido son ambos registros válidos.';
COMMENT ON COLUMN ciclo.cursor_entrada IS
    'La marca con la que arrancó el Ciclo. NULL en el primer Ciclo de un dataset.';
COMMENT ON COLUMN ciclo.en_borde_de_ventana IS
    'Registros nuevos con fecha de hecho en el día más viejo de la ventana. Si no es cero, la ventana se está quedando corta.';
COMMENT ON COLUMN ciclo.recuperados_por_solapamiento IS
    'Registros nuevos anteriores a la marca previa: los que se habrían perdido sin ventana.';
COMMENT ON COLUMN ciclo.desde_derivado IS
    'true si `desde` salió de la marca menos la ventana; false si lo pidió una persona. La señal de ventana corta solo tiene sentido cuando es true.';

-- Lo que se consulta es «cómo va este dataset», casi siempre el último Ciclo.
CREATE INDEX IF NOT EXISTS ciclo_dataset_inicio_idx
    ON ciclo (dataset, inicio DESC);

-- Y, cuando algo va mal, «cuáles fallaron».
CREATE INDEX IF NOT EXISTS ciclo_fallidos_idx
    ON ciclo (dataset, inicio DESC)
    WHERE estado = 'fallido';
