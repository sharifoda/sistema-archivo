BEGIN;

ALTER TABLE logs ALTER COLUMN usuario_id DROP NOT NULL;
DO $$
DECLARE
    conname text;
BEGIN
    SELECT c.conname INTO conname
    FROM pg_constraint c
    WHERE c.conrelid = 'logs'::regclass
      AND c.contype = 'f'
      AND c.confrelid = 'usuarios'::regclass;
    IF conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE logs DROP CONSTRAINT %I', conname);
    END IF;
END $$;
ALTER TABLE logs
    ADD CONSTRAINT logs_usuario_id_fkey
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL;

ALTER TABLE movimientos ALTER COLUMN usuario_id DROP NOT NULL;
DO $$
DECLARE
    conname text;
BEGIN
    SELECT c.conname INTO conname
    FROM pg_constraint c
    WHERE c.conrelid = 'movimientos'::regclass
      AND c.contype = 'f'
      AND c.confrelid = 'usuarios'::regclass;
    IF conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE movimientos DROP CONSTRAINT %I', conname);
    END IF;
END $$;
ALTER TABLE movimientos
    ADD CONSTRAINT movimientos_usuario_id_fkey
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL;

ALTER TABLE grupos ALTER COLUMN creado_por DROP NOT NULL;
DO $$
DECLARE
    conname text;
BEGIN
    SELECT c.conname INTO conname
    FROM pg_constraint c
    WHERE c.conrelid = 'grupos'::regclass
      AND c.contype = 'f'
      AND c.confrelid = 'usuarios'::regclass;
    IF conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE grupos DROP CONSTRAINT %I', conname);
    END IF;
END $$;
ALTER TABLE grupos
    ADD CONSTRAINT grupos_creado_por_fkey
    FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL;

ALTER TABLE cajas ALTER COLUMN creado_por DROP NOT NULL;
DO $$
DECLARE
    conname text;
BEGIN
    SELECT c.conname INTO conname
    FROM pg_constraint c
    WHERE c.conrelid = 'cajas'::regclass
      AND c.contype = 'f'
      AND c.confrelid = 'usuarios'::regclass;
    IF conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE cajas DROP CONSTRAINT %I', conname);
    END IF;
END $$;
ALTER TABLE cajas
    ADD CONSTRAINT cajas_creado_por_fkey
    FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL;

ALTER TABLE archivos ALTER COLUMN creado_por DROP NOT NULL;
DO $$
DECLARE
    conname text;
BEGIN
    SELECT c.conname INTO conname
    FROM pg_constraint c
    WHERE c.conrelid = 'archivos'::regclass
      AND c.contype = 'f'
      AND c.confrelid = 'usuarios'::regclass;
    IF conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE archivos DROP CONSTRAINT %I', conname);
    END IF;
END $$;
ALTER TABLE archivos
    ADD CONSTRAINT archivos_creado_por_fkey
    FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL;

COMMIT;
