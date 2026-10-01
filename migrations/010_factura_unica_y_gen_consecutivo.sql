SET XACT_ABORT ON;
BEGIN TRANSACTION;

DECLARE @fecha_legacy DATE = CONVERT(DATE, '20261001', 112);

IF EXISTS (
    SELECT empresa
    FROM dbo.archivo_pdfs
    WHERE fecha_documento = @fecha_legacy
      AND factura = 'GEN0001'
    GROUP BY empresa
    HAVING COUNT(*) > 9999
)
BEGIN
    THROW 51001, 'Hay mas de 9999 PDFs legados para una empresa; no se pueden asignar codigos GEN de cuatro digitos.', 1;
END;

;WITH pdfs_legacy AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY empresa
            ORDER BY archivo_id, id
        ) AS consecutivo
    FROM dbo.archivo_pdfs
    WHERE fecha_documento = @fecha_legacy
      AND factura = 'GEN0001'
)
UPDATE pdfs_legacy
SET factura = 'GEN' + RIGHT('0000' + CONVERT(VARCHAR(4), consecutivo), 4);

IF EXISTS (
    SELECT empresa, factura
    FROM dbo.archivo_pdfs
    GROUP BY empresa, factura
    HAVING COUNT(*) > 1
)
BEGIN
    THROW 51002, 'Quedaron facturas repetidas dentro de una empresa; revise los registros antes de crear el indice unico.', 1;
END;

IF EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UX_archivo_pdfs_expediente'
      AND object_id = OBJECT_ID('dbo.archivo_pdfs')
)
BEGIN
    DROP INDEX UX_archivo_pdfs_expediente ON dbo.archivo_pdfs;
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UX_archivo_pdfs_factura'
      AND object_id = OBJECT_ID('dbo.archivo_pdfs')
)
BEGIN
    CREATE UNIQUE INDEX UX_archivo_pdfs_factura
        ON dbo.archivo_pdfs (empresa, factura);
END;

COMMIT TRANSACTION;