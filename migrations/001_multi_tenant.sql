BEGIN;

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol TEXT DEFAULT 'cliente';
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS grupos (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    creado_por INTEGER REFERENCES usuarios(id),
    creado_en TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usuarios_grupos (
    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
    grupo_id INTEGER REFERENCES grupos(id) ON DELETE CASCADE,
    puede_eliminar BOOLEAN NOT NULL DEFAULT FALSE,
    puede_editar BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (usuario_id, grupo_id)
);

ALTER TABLE cajas ADD COLUMN IF NOT EXISTS grupo_id INTEGER REFERENCES grupos(id);
ALTER TABLE cajas ADD COLUMN IF NOT EXISTS is_pendiente BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE cajas ADD COLUMN IF NOT EXISTS creado_por INTEGER REFERENCES usuarios(id);

ALTER TABLE archivos ADD COLUMN IF NOT EXISTS grupo_id INTEGER REFERENCES grupos(id);
ALTER TABLE archivos ADD COLUMN IF NOT EXISTS creado_por INTEGER REFERENCES usuarios(id);
ALTER TABLE archivos ADD COLUMN IF NOT EXISTS pdf_path TEXT;

ALTER TABLE logs ADD COLUMN IF NOT EXISTS grupo_id INTEGER REFERENCES grupos(id);

CREATE TABLE IF NOT EXISTS movimientos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    grupo_id INTEGER REFERENCES grupos(id),
    entidad TEXT NOT NULL,
    entidad_id INTEGER,
    accion TEXT NOT NULL,
    datos_antes JSONB,
    datos_despues JSONB,
    meta JSONB,
    fecha TIMESTAMP NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'archivos_numero_key'
    ) THEN
        ALTER TABLE archivos DROP CONSTRAINT archivos_numero_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS archivos_grupo_numero_idx
    ON archivos (grupo_id, numero);

DO $$
DECLARE gid INTEGER;
BEGIN
    SELECT id INTO gid FROM grupos ORDER BY id LIMIT 1;
    IF gid IS NULL THEN
        INSERT INTO grupos (nombre) VALUES ('General') RETURNING id INTO gid;
    END IF;

    UPDATE cajas SET grupo_id = gid WHERE grupo_id IS NULL;
    UPDATE archivos SET grupo_id = gid WHERE grupo_id IS NULL;
    UPDATE logs SET grupo_id = gid WHERE grupo_id IS NULL;

    UPDATE cajas SET is_pendiente = TRUE WHERE id = 0 AND grupo_id = gid;

    INSERT INTO usuarios_grupos (usuario_id, grupo_id, puede_eliminar, puede_editar)
    SELECT u.id, gid, (u.rol = 'admin'), TRUE
    FROM usuarios u
    ON CONFLICT (usuario_id, grupo_id) DO NOTHING;
END $$;

COMMIT;
