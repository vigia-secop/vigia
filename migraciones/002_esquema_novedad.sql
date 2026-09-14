-- Campos que la fuente empezó a declarar y que nadie ha revisado todavía.
--
-- Un campo nuevo no detiene el Ciclo (a diferencia de uno que desaparece),
-- pero tampoco se pierde: queda aquí con la fecha en que se vio por primera
-- vez y la última en que seguía apareciendo. La primera responde «desde
-- cuándo»; la última, «sigue ahí».

CREATE TABLE IF NOT EXISTS esquema_novedad (
    dataset            text        NOT NULL,
    campo              text        NOT NULL,
    primera_deteccion  timestamptz NOT NULL,
    ultima_deteccion   timestamptz NOT NULL,
    revisada           boolean     NOT NULL DEFAULT false,
    PRIMARY KEY (dataset, campo),
    CONSTRAINT esquema_novedad_orden_de_deteccion
        CHECK (ultima_deteccion >= primera_deteccion)
);

COMMENT ON TABLE esquema_novedad IS
    'Campos declarados por la fuente que no están en el esquema esperado del repositorio.';
COMMENT ON COLUMN esquema_novedad.primera_deteccion IS
    'Nunca se sobrescribe: es la respuesta a «desde cuándo la fuente trae este campo».';
COMMENT ON COLUMN esquema_novedad.revisada IS
    'La marca el equipo cuando decide qué hacer con el campo. El sistema no la toca.';

-- Lo que el equipo consulta es «qué falta por mirar», no la tabla entera.
CREATE INDEX IF NOT EXISTS esquema_novedad_sin_revisar_idx
    ON esquema_novedad (dataset, ultima_deteccion DESC)
    WHERE NOT revisada;
