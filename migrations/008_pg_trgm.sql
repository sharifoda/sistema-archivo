BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS archivos_nombre_trgm_idx
ON archivos USING GIN (nombre gin_trgm_ops);

CREATE INDEX IF NOT EXISTS archivos_numero_trgm_idx
ON archivos USING GIN ((numero::text) gin_trgm_ops);

COMMIT;
