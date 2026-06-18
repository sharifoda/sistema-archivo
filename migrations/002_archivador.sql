SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF COL_LENGTH('dbo.cajas', 'grupo_origen_id') IS NULL
BEGIN
    ALTER TABLE dbo.cajas ADD grupo_origen_id INT NULL;
END;

IF COL_LENGTH('dbo.archivos', 'grupo_origen_id') IS NULL
BEGIN
    ALTER TABLE dbo.archivos ADD grupo_origen_id INT NULL;
END;

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_cajas_grupo_origen')
BEGIN
    ALTER TABLE dbo.cajas
    ADD CONSTRAINT FK_cajas_grupo_origen
    FOREIGN KEY (grupo_origen_id) REFERENCES dbo.grupos(id);
END;

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_archivos_grupo_origen')
BEGIN
    ALTER TABLE dbo.archivos
    ADD CONSTRAINT FK_archivos_grupo_origen
    FOREIGN KEY (grupo_origen_id) REFERENCES dbo.grupos(id);
END;

COMMIT TRANSACTION;
