SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID('dbo.archivo_pdfs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.archivo_pdfs (
        id INT IDENTITY(1,1) PRIMARY KEY,
        archivo_id INT NOT NULL,
        empresa INT NOT NULL,
        numero_documento BIGINT NOT NULL,
        fecha_documento DATE NOT NULL,
        factura NVARCHAR(16) NOT NULL,
        pdf_path NVARCHAR(500) NOT NULL,
        creado_por INT NULL,
        creado_en DATETIME2 NOT NULL
            CONSTRAINT DF_archivo_pdfs_creado_en DEFAULT (SYSDATETIME()),
        CONSTRAINT FK_archivo_pdfs_archivo
            FOREIGN KEY (archivo_id) REFERENCES dbo.archivos(id) ON DELETE CASCADE
    );
END;

IF COL_LENGTH('dbo.archivo_pdfs', 'grupo_id') IS NOT NULL
   AND COL_LENGTH('dbo.archivo_pdfs', 'empresa') IS NULL
BEGIN
    EXEC sys.sp_rename 'dbo.archivo_pdfs.grupo_id', 'empresa', 'COLUMN';
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UX_archivo_pdfs_expediente'
      AND object_id = OBJECT_ID('dbo.archivo_pdfs')
)
BEGIN
    CREATE UNIQUE INDEX UX_archivo_pdfs_expediente
        ON dbo.archivo_pdfs (empresa, numero_documento, fecha_documento, factura);
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_archivo_pdfs_listado'
      AND object_id = OBJECT_ID('dbo.archivo_pdfs')
)
BEGIN
    CREATE INDEX IX_archivo_pdfs_listado
        ON dbo.archivo_pdfs (empresa, numero_documento, fecha_documento DESC, factura DESC);
END;

;WITH pdfs_existentes AS (
    SELECT
        a.id AS archivo_id,
        a.empresa,
        a.numero,
        a.pdf_path,
        a.creado_por,
        ROW_NUMBER() OVER (
            PARTITION BY a.empresa, a.numero
            ORDER BY a.id
        ) AS fila
        FROM dbo.archivos a
        WHERE a.empresa IS NOT NULL
            AND a.pdf_path IS NOT NULL
      AND LTRIM(RTRIM(a.pdf_path)) <> ''
)
INSERT INTO dbo.archivo_pdfs (
    archivo_id, empresa, numero_documento, fecha_documento, factura, pdf_path, creado_por
)
SELECT
    p.archivo_id,
    p.empresa,
    p.numero,
    CONVERT(DATE, '20261001', 112),
    'GEN0001',
    p.pdf_path,
    p.creado_por
FROM pdfs_existentes p
WHERE p.fila = 1
  AND NOT EXISTS (
      SELECT 1
      FROM dbo.archivo_pdfs existing
            WHERE existing.empresa = p.empresa
                AND existing.numero_documento = p.numero
        AND existing.fecha_documento = CONVERT(DATE, '20261001', 112)
        AND existing.factura = 'GEN0001'
  );

COMMIT TRANSACTION;