SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = 'usuarios_rol_check'
      AND parent_object_id = OBJECT_ID('dbo.usuarios')
)
BEGIN
    ALTER TABLE dbo.usuarios DROP CONSTRAINT usuarios_rol_check;
END;

ALTER TABLE dbo.usuarios
ADD CONSTRAINT usuarios_rol_check
CHECK (rol IN ('admin', 'supervisor', 'usuario', 'cliente'));

COMMIT TRANSACTION;
