SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF COL_LENGTH('dbo.usuarios', 'rol') IS NULL
BEGIN
    ALTER TABLE dbo.usuarios
    ADD rol NVARCHAR(50) NOT NULL
        CONSTRAINT DF_usuarios_rol DEFAULT ('cliente');
END;

IF COL_LENGTH('dbo.usuarios', 'activo') IS NULL
BEGIN
    ALTER TABLE dbo.usuarios
    ADD activo BIT NOT NULL
        CONSTRAINT DF_usuarios_activo DEFAULT (1);
END;

IF OBJECT_ID('dbo.grupos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.grupos (
        id INT IDENTITY(1,1) PRIMARY KEY,
        nombre NVARCHAR(255) NOT NULL,
        creado_por INT NULL,
        creado_en DATETIME2 NOT NULL
            CONSTRAINT DF_grupos_creado_en DEFAULT (SYSDATETIME())
    );
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.foreign_keys
    WHERE name = 'FK_grupos_creado_por'
)
BEGIN
    ALTER TABLE dbo.grupos
    ADD CONSTRAINT FK_grupos_creado_por
    FOREIGN KEY (creado_por) REFERENCES dbo.usuarios(id);
END;

IF OBJECT_ID('dbo.usuarios_grupos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.usuarios_grupos (
        usuario_id INT NOT NULL,
        grupo_id INT NOT NULL,
        puede_eliminar BIT NOT NULL
            CONSTRAINT DF_usuarios_grupos_puede_eliminar DEFAULT (0),
        puede_editar BIT NOT NULL
            CONSTRAINT DF_usuarios_grupos_puede_editar DEFAULT (1),
        CONSTRAINT PK_usuarios_grupos PRIMARY KEY (usuario_id, grupo_id),
        CONSTRAINT FK_usuarios_grupos_usuario
            FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id) ON DELETE CASCADE,
        CONSTRAINT FK_usuarios_grupos_grupo
            FOREIGN KEY (grupo_id) REFERENCES dbo.grupos(id) ON DELETE CASCADE
    );
END;

IF COL_LENGTH('dbo.cajas', 'grupo_id') IS NULL
BEGIN
    ALTER TABLE dbo.cajas ADD grupo_id INT NULL;
END;

IF COL_LENGTH('dbo.cajas', 'is_pendiente') IS NULL
BEGIN
    ALTER TABLE dbo.cajas
    ADD is_pendiente BIT NOT NULL
        CONSTRAINT DF_cajas_is_pendiente DEFAULT (0);
END;

IF COL_LENGTH('dbo.cajas', 'creado_por') IS NULL
BEGIN
    ALTER TABLE dbo.cajas ADD creado_por INT NULL;
END;

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_cajas_grupo')
BEGIN
    ALTER TABLE dbo.cajas
    ADD CONSTRAINT FK_cajas_grupo
    FOREIGN KEY (grupo_id) REFERENCES dbo.grupos(id);
END;

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_cajas_creado_por')
BEGIN
    ALTER TABLE dbo.cajas
    ADD CONSTRAINT FK_cajas_creado_por
    FOREIGN KEY (creado_por) REFERENCES dbo.usuarios(id);
END;

IF COL_LENGTH('dbo.archivos', 'grupo_id') IS NULL
BEGIN
    ALTER TABLE dbo.archivos ADD grupo_id INT NULL;
END;

IF COL_LENGTH('dbo.archivos', 'creado_por') IS NULL
BEGIN
    ALTER TABLE dbo.archivos ADD creado_por INT NULL;
END;

IF COL_LENGTH('dbo.archivos', 'pdf_path') IS NULL
BEGIN
    ALTER TABLE dbo.archivos ADD pdf_path NVARCHAR(500) NULL;
END;

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_archivos_grupo')
BEGIN
    ALTER TABLE dbo.archivos
    ADD CONSTRAINT FK_archivos_grupo
    FOREIGN KEY (grupo_id) REFERENCES dbo.grupos(id);
END;

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_archivos_creado_por')
BEGIN
    ALTER TABLE dbo.archivos
    ADD CONSTRAINT FK_archivos_creado_por
    FOREIGN KEY (creado_por) REFERENCES dbo.usuarios(id);
END;

IF COL_LENGTH('dbo.logs', 'grupo_id') IS NULL
BEGIN
    ALTER TABLE dbo.logs ADD grupo_id INT NULL;
END;

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_logs_grupo')
BEGIN
    ALTER TABLE dbo.logs
    ADD CONSTRAINT FK_logs_grupo
    FOREIGN KEY (grupo_id) REFERENCES dbo.grupos(id);
END;

IF OBJECT_ID('dbo.movimientos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.movimientos (
        id INT IDENTITY(1,1) PRIMARY KEY,
        usuario_id INT NULL,
        grupo_id INT NULL,
        entidad NVARCHAR(100) NOT NULL,
        entidad_id INT NULL,
        accion NVARCHAR(100) NOT NULL,
        datos_antes NVARCHAR(MAX) NULL,
        datos_despues NVARCHAR(MAX) NULL,
        meta NVARCHAR(MAX) NULL,
        fecha DATETIME2 NOT NULL
            CONSTRAINT DF_movimientos_fecha DEFAULT (SYSDATETIME())
    );
END;

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_movimientos_usuario')
BEGIN
    ALTER TABLE dbo.movimientos
    ADD CONSTRAINT FK_movimientos_usuario
    FOREIGN KEY (usuario_id) REFERENCES dbo.usuarios(id);
END;

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_movimientos_grupo')
BEGIN
    ALTER TABLE dbo.movimientos
    ADD CONSTRAINT FK_movimientos_grupo
    FOREIGN KEY (grupo_id) REFERENCES dbo.grupos(id);
END;

IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'archivos_numero_key')
BEGIN
    ALTER TABLE dbo.archivos DROP CONSTRAINT archivos_numero_key;
END;

IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'archivos_numero_key' AND object_id = OBJECT_ID('dbo.archivos'))
BEGIN
    DROP INDEX archivos_numero_key ON dbo.archivos;
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'archivos_grupo_numero_idx'
      AND object_id = OBJECT_ID('dbo.archivos')
)
BEGIN
    CREATE UNIQUE INDEX archivos_grupo_numero_idx
        ON dbo.archivos (grupo_id, numero);
END;

DECLARE @gid INT;
SELECT TOP 1 @gid = id FROM dbo.grupos ORDER BY id;

IF @gid IS NULL
BEGIN
    INSERT INTO dbo.grupos (nombre) VALUES ('General');
    SET @gid = SCOPE_IDENTITY();
END;

UPDATE dbo.cajas SET grupo_id = @gid WHERE grupo_id IS NULL;
UPDATE dbo.archivos SET grupo_id = @gid WHERE grupo_id IS NULL;
UPDATE dbo.logs SET grupo_id = @gid WHERE grupo_id IS NULL;
UPDATE dbo.cajas SET is_pendiente = 1 WHERE id = 0 AND grupo_id = @gid;

MERGE dbo.usuarios_grupos AS target
USING (
    SELECT id AS usuario_id,
           @gid AS grupo_id,
           CASE WHEN rol = 'admin' THEN 1 ELSE 0 END AS puede_eliminar,
           CAST(1 AS BIT) AS puede_editar
    FROM dbo.usuarios
) AS source
ON target.usuario_id = source.usuario_id AND target.grupo_id = source.grupo_id
WHEN NOT MATCHED THEN
    INSERT (usuario_id, grupo_id, puede_eliminar, puede_editar)
    VALUES (source.usuario_id, source.grupo_id, source.puede_eliminar, source.puede_editar);

COMMIT TRANSACTION;
