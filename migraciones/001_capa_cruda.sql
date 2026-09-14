-- Capa cruda (AD-1): la respuesta de la fuente tal como llegó, nunca modificada.
--
-- La llave primaria compuesta es la identidad determinista del registro crudo:
-- reingerir contenido idéntico no inserta fila, y un registro que cambió en la
-- fuente entra como fila nueva sin tocar la anterior. La idempotencia es una
-- garantía del motor, no una comprobación de la aplicación.
--
-- Esta tabla es de solo inserción. No hay UPDATE ni DELETE sobre ella.

CREATE TABLE IF NOT EXISTS crudo_registro (
    dataset        text        NOT NULL,
    id_fila_fuente text        NOT NULL,
    hash_contenido text        NOT NULL,
    contenido      jsonb       NOT NULL,
    consultado_en  timestamptz NOT NULL,
    PRIMARY KEY (dataset, id_fila_fuente, hash_contenido)
);

COMMENT ON TABLE crudo_registro IS
    'Capa cruda: respuesta de la API del SECOP sin transformar, con fecha de consulta. Solo inserción.';
COMMENT ON COLUMN crudo_registro.id_fila_fuente IS
    'Campo de sistema :id de Socrata. Estable por fila y cláusula de orden para paginar.';
COMMENT ON COLUMN crudo_registro.hash_contenido IS
    'SHA-256 del contenido serializado en JSON canónico (claves ordenadas, UTF-8, sin espacios).';
COMMENT ON COLUMN crudo_registro.consultado_en IS
    'Fecha y hora UTC de la respuesta HTTP que trajo el registro. Requisito del Expediente.';

-- Recorrer lo ingerido por dataset y ventana de consulta es la consulta de
-- operación más frecuente: qué trajo el Ciclo de ayer, qué trajo el de hoy.
CREATE INDEX IF NOT EXISTS crudo_registro_dataset_consultado_en_idx
    ON crudo_registro (dataset, consultado_en DESC);
