BEGIN;

ALTER TABLE archivos ADD COLUMN IF NOT EXISTS tipo_doc TEXT;

UPDATE archivos
SET tipo_doc = 'CC'
WHERE tipo_doc IS NULL OR tipo_doc = '';

ALTER TABLE archivos
ALTER COLUMN tipo_doc SET DEFAULT 'CC';

ALTER TABLE archivos
ALTER COLUMN tipo_doc SET NOT NULL;

ALTER TABLE archivos
DROP CONSTRAINT IF EXISTS archivos_tipo_doc_check;

ALTER TABLE archivos
ADD CONSTRAINT archivos_tipo_doc_check
CHECK (tipo_doc IN ('CC', 'CE', 'TI', 'RC'));

COMMIT;
