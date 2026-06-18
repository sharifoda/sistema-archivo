SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF COL_LENGTH('dbo.archivos', 'tipo_doc') IS NULL
BEGIN
    ALTER TABLE dbo.archivos ADD tipo_doc NVARCHAR(10) NULL;
END;

UPDATE dbo.archivos
SET tipo_doc = 'CC'
WHERE tipo_doc IS NULL OR LTRIM(RTRIM(tipo_doc)) = '';

IF EXISTS (
    SELECT 1
    FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.archivos')
      AND parent_column_id = COLUMNPROPERTY(OBJECT_ID('dbo.archivos'), 'tipo_doc', 'ColumnId')
)
BEGIN
    DECLARE @df_tipo_doc NVARCHAR(200);
    SELECT @df_tipo_doc = dc.name
    FROM sys.default_constraints dc
    WHERE dc.parent_object_id = OBJECT_ID('dbo.archivos')
      AND dc.parent_column_id = COLUMNPROPERTY(OBJECT_ID('dbo.archivos'), 'tipo_doc', 'ColumnId');
    EXEC('ALTER TABLE dbo.archivos DROP CONSTRAINT ' + QUOTENAME(@df_tipo_doc));
END;

ALTER TABLE dbo.archivos
ADD CONSTRAINT DF_archivos_tipo_doc DEFAULT ('CC') FOR tipo_doc;

ALTER TABLE dbo.archivos
ALTER COLUMN tipo_doc NVARCHAR(10) NOT NULL;

IF EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = 'archivos_tipo_doc_check'
      AND parent_object_id = OBJECT_ID('dbo.archivos')
)
BEGIN
    ALTER TABLE dbo.archivos DROP CONSTRAINT archivos_tipo_doc_check;
END;

ALTER TABLE dbo.archivos
ADD CONSTRAINT archivos_tipo_doc_check
CHECK (tipo_doc IN ('CC', 'CE', 'TI', 'RC'));

COMMIT TRANSACTION;
