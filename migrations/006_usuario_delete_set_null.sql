SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'logs_usuario_id_fkey')
BEGIN
    ALTER TABLE dbo.logs DROP CONSTRAINT logs_usuario_id_fkey;
END;
IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_logs_usuario')
BEGIN
    ALTER TABLE dbo.logs DROP CONSTRAINT FK_logs_usuario;
END;
ALTER TABLE dbo.logs ALTER COLUMN usuario_id INT NULL;
ALTER TABLE dbo.logs
    ADD CONSTRAINT logs_usuario_id_fkey
    FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id) ON DELETE SET NULL;

IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'movimientos_usuario_id_fkey')
BEGIN
    ALTER TABLE dbo.movimientos DROP CONSTRAINT movimientos_usuario_id_fkey;
END;
IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_movimientos_usuario')
BEGIN
    ALTER TABLE dbo.movimientos DROP CONSTRAINT FK_movimientos_usuario;
END;
ALTER TABLE dbo.movimientos ALTER COLUMN usuario_id INT NULL;
ALTER TABLE dbo.movimientos
    ADD CONSTRAINT movimientos_usuario_id_fkey
    FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id) ON DELETE SET NULL;

IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'grupos_creado_por_fkey')
BEGIN
    ALTER TABLE dbo.grupos DROP CONSTRAINT grupos_creado_por_fkey;
END;
IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_grupos_creado_por')
BEGIN
    ALTER TABLE dbo.grupos DROP CONSTRAINT FK_grupos_creado_por;
END;
ALTER TABLE dbo.grupos ALTER COLUMN creado_por INT NULL;
ALTER TABLE dbo.grupos
    ADD CONSTRAINT grupos_creado_por_fkey
    FOREIGN KEY (creado_por) REFERENCES dbo.usuarios(id) ON DELETE SET NULL;

IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'cajas_creado_por_fkey')
BEGIN
    ALTER TABLE dbo.cajas DROP CONSTRAINT cajas_creado_por_fkey;
END;
IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_cajas_creado_por')
BEGIN
    ALTER TABLE dbo.cajas DROP CONSTRAINT FK_cajas_creado_por;
END;
ALTER TABLE dbo.cajas ALTER COLUMN creado_por INT NULL;
ALTER TABLE dbo.cajas
    ADD CONSTRAINT cajas_creado_por_fkey
    FOREIGN KEY (creado_por) REFERENCES dbo.usuarios(id) ON DELETE SET NULL;

IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'archivos_creado_por_fkey')
BEGIN
    ALTER TABLE dbo.archivos DROP CONSTRAINT archivos_creado_por_fkey;
END;
IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_archivos_creado_por')
BEGIN
    ALTER TABLE dbo.archivos DROP CONSTRAINT FK_archivos_creado_por;
END;
ALTER TABLE dbo.archivos ALTER COLUMN creado_por INT NULL;
ALTER TABLE dbo.archivos
    ADD CONSTRAINT archivos_creado_por_fkey
    FOREIGN KEY (creado_por) REFERENCES dbo.usuarios(id) ON DELETE SET NULL;

COMMIT TRANSACTION;
