SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF COL_LENGTH('dbo.grupos', 'archivado') IS NULL
BEGIN
    ALTER TABLE dbo.grupos
    ADD archivado BIT NOT NULL
        CONSTRAINT DF_grupos_archivado DEFAULT (0);
END;

IF COL_LENGTH('dbo.grupos', 'archivado_en') IS NULL
BEGIN
    ALTER TABLE dbo.grupos
    ADD archivado_en DATETIME2 NULL;
END;

COMMIT TRANSACTION;
