SET XACT_ABORT ON;
BEGIN TRANSACTION;

/*
    SQL Server no tiene equivalente directo a pg_trgm.
    Dejamos índices normales para acelerar búsquedas por igualdad y prefijos.
    Si luego quieres similitud real por texto, toca evaluar:
    - Full-Text Search
    - SOUNDEX / DIFFERENCE
    - lógica de similitud en aplicación
*/

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'archivos_nombre_idx'
      AND object_id = OBJECT_ID('dbo.archivos')
)
BEGIN
    CREATE INDEX archivos_nombre_idx
        ON dbo.archivos (nombre);
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'archivos_numero_idx'
      AND object_id = OBJECT_ID('dbo.archivos')
)
BEGIN
    CREATE INDEX archivos_numero_idx
        ON dbo.archivos (numero);
END;

COMMIT TRANSACTION;
