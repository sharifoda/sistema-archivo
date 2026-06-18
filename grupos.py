from db import get_db


def _sincronizar_usuario_registrado(cur, usuario_id, grupo_id):
    cur.execute(
        """
        MERGE usuariosregistrados AS target
        USING (
            SELECT
                u.id AS usuarioid,
                e.id AS empresa,
                u.rol AS rol,
                u.usuario AS nombreusuario,
                e.nombre AS nombreempresa
            FROM usuarios u
            JOIN empresas e ON e.id = %s
            WHERE u.id = %s
        ) AS source
        ON target.usuarioid = source.usuarioid AND target.empresa = source.empresa
        WHEN MATCHED THEN
            UPDATE SET
                rol = source.rol,
                nombreusuario = source.nombreusuario,
                nombreempresa = source.nombreempresa
        WHEN NOT MATCHED THEN
            INSERT (usuarioid, empresa, rol, fecha, nombreusuario, nombreempresa)
            VALUES (
                source.usuarioid,
                source.empresa,
                source.rol,
                SYSDATETIME(),
                source.nombreusuario,
                source.nombreempresa
            );
        """,
        (grupo_id, usuario_id)
    )


def sincronizar_registros_usuario(usuario_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE ur
        SET
            rol = u.rol,
            nombreusuario = u.usuario,
            nombreempresa = e.nombre
        FROM usuariosregistrados ur
        JOIN usuarios u ON u.id = ur.usuarioid
        JOIN empresas e ON e.id = ur.empresa
        WHERE ur.usuarioid = %s
        """,
        (usuario_id,)
    )

    cur.execute(
        """
        INSERT INTO usuariosregistrados (usuarioid, empresa, rol, fecha, nombreusuario, nombreempresa)
        SELECT
            u.id,
            e.id,
            u.rol,
            SYSDATETIME(),
            u.usuario,
            e.nombre
        FROM usuariosempresas ue
        JOIN usuarios u ON u.id = ue.usuarioid
        JOIN empresas e ON e.id = ue.empresa
        WHERE ue.usuarioid = %s
          AND NOT EXISTS (
              SELECT 1
              FROM usuariosregistrados ur
              WHERE ur.usuarioid = ue.usuarioid AND ur.empresa = ue.empresa
          )
        """,
        (usuario_id,)
    )

    conn.commit()
    cur.close()
    conn.close()


def eliminar_registros_usuario(usuario_id, grupo_id=None):
    conn = get_db()
    cur = conn.cursor()

    if grupo_id is None:
        cur.execute("DELETE FROM usuariosregistrados WHERE usuarioid = %s", (usuario_id,))
    else:
        cur.execute(
            "DELETE FROM usuariosregistrados WHERE usuarioid = %s AND empresa = %s",
            (usuario_id, grupo_id)
        )

    conn.commit()
    cur.close()
    conn.close()


def crear_grupo(nombre, creado_por=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO grupos (nombre, creado_por) VALUES (%s, %s) RETURNING id",
        (nombre, creado_por)
    )
    grupo_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return grupo_id


def agregar_usuario_a_grupo(usuario_id, grupo_id, puede_eliminar=False, puede_editar=True):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        MERGE usuariosempresas AS target
        USING (SELECT %s AS usuarioid, %s AS empresa, %s AS eliminar, %s AS editar) AS source
        ON target.usuarioid = source.usuarioid AND target.empresa = source.empresa
        WHEN MATCHED THEN
            UPDATE SET
                eliminar = source.eliminar,
                editar = source.editar
        WHEN NOT MATCHED THEN
            INSERT (usuarioid, empresa, eliminar, editar)
            VALUES (source.usuarioid, source.empresa, source.eliminar, source.editar);
        """,
        (usuario_id, grupo_id, puede_eliminar, puede_editar)
    )

    _sincronizar_usuario_registrado(cur, usuario_id, grupo_id)

    conn.commit()
    cur.close()
    conn.close()


def obtener_grupos_usuario(usuario_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT e.id, e.nombre, ue.eliminar, ue.editar
        FROM usuariosempresas ue
        JOIN empresas e ON e.id = ue.empresa
        WHERE ue.usuarioid = %s AND (e.archivado = 0 OR e.archivado IS NULL)
        ORDER BY e.nombre
        """,
        (usuario_id,)
    )
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def obtener_todos_grupos():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, nombre FROM grupos WHERE archivado = 0 ORDER BY nombre")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def usuario_puede_eliminar(usuario_id, grupo_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT eliminar
        FROM usuariosempresas
        WHERE usuarioid = %s AND empresa = %s
        """,
        (usuario_id, grupo_id)
    )
    row = cur.fetchone()

    cur.close()
    conn.close()

    return bool(row[0]) if row else False


def obtener_miembros_grupo(grupo_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT u.id, u.usuario, u.rol, ue.eliminar, ue.editar
        FROM usuariosempresas ue
        JOIN usuarios u ON u.id = ue.usuarioid
        WHERE ue.empresa = %s
        ORDER BY u.usuario
        """,
        (grupo_id,)
    )
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def buscar_usuario_por_nombre(usuario):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, usuario FROM usuarios WHERE usuario = %s",
        (usuario,)
    )
    row = cur.fetchone()

    cur.close()
    conn.close()

    return row


def quitar_usuario_de_grupo(usuario_id, grupo_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM usuariosempresas WHERE usuarioid = %s AND empresa = %s",
        (usuario_id, grupo_id)
    )
    cur.execute(
        "DELETE FROM usuariosregistrados WHERE usuarioid = %s AND empresa = %s",
        (usuario_id, grupo_id)
    )

    cur.execute(
        "SELECT COUNT(*) FROM usuariosempresas WHERE usuarioid = %s",
        (usuario_id,)
    )
    count = cur.fetchone()[0]

    if count == 0:
        cur.execute("SELECT usuario FROM usuarios WHERE id = %s", (usuario_id,))
        row = cur.fetchone()
        if row:
            personal_name = f"Personal - {row[0]}"
            cur.execute(
                "SELECT id FROM grupos WHERE nombre = %s",
                (personal_name,)
            )
            g = cur.fetchone()
            if not g:
                cur.execute(
                    "INSERT INTO grupos (nombre, creado_por) VALUES (%s, %s) RETURNING id",
                    (personal_name, usuario_id)
                )
                personal_id = cur.fetchone()[0]
            else:
                personal_id = g[0]

            cur.execute(
                """
                IF NOT EXISTS (
                    SELECT 1
                    FROM usuariosempresas
                    WHERE usuarioid = %s AND empresa = %s
                )
                BEGIN
                    INSERT INTO usuariosempresas (usuarioid, empresa, eliminar, editar)
                    VALUES (%s, %s, %s, %s)
                END
                """,
                (usuario_id, personal_id, usuario_id, personal_id, True, True)
            )
            _sincronizar_usuario_registrado(cur, usuario_id, personal_id)

    conn.commit()
    cur.close()
    conn.close()


def eliminar_grupo_personal(usuario_id, target_group_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT usuario FROM usuarios WHERE id = %s", (usuario_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return

    personal_name = f"Personal - {row[0]}"
    cur.execute(
        "SELECT id FROM grupos WHERE nombre = %s",
        (personal_name,)
    )
    group_row = cur.fetchone()
    if not group_row:
        cur.close()
        conn.close()
        return

    personal_id = group_row[0]
    if personal_id == target_group_id:
        cur.close()
        conn.close()
        return

    cur.execute(
        "SELECT COUNT(*) FROM usuariosempresas WHERE empresa = %s",
        (personal_id,)
    )
    count = cur.fetchone()[0]

    if count == 1:
        # Asegurar caja pendiente en el grupo destino
        cur.execute(
            "SELECT id FROM cajas WHERE grupo_id = %s AND is_pendiente = TRUE",
            (target_group_id,)
        )
        row = cur.fetchone()
        if row:
            pendiente_id = row[0]
        else:
            cur.execute(
                """
                INSERT INTO cajas (rango_min, rango_max, creado_por, grupo_id, is_pendiente)
                VALUES (%s, %s, %s, %s, 1)
                RETURNING id
                """,
                (-1, -1, None, target_group_id)
            )
            pendiente_id = cur.fetchone()[0]

        # Mover archivos al grupo destino (por rango o pendiente)
        cur.execute(
            "SELECT id, numero FROM archivos WHERE grupo_id = %s",
            (personal_id,)
        )
        archivos = cur.fetchall()
        for archivo_id, numero in archivos:
            cur.execute(
                """
                SELECT TOP 1 id
                FROM cajas
                WHERE grupo_id = %s
                  AND is_pendiente = 0
                  AND %s BETWEEN rango_min AND rango_max
                ORDER BY rango_min, id
                """,
                (target_group_id, numero)
            )
            dest = cur.fetchone()
            dest_id = dest[0] if dest else pendiente_id
            cur.execute(
                """
                UPDATE archivos
                SET grupo_id = %s,
                    caja_id = %s,
                    grupo_origen_id = COALESCE(grupo_origen_id, %s)
                WHERE id = %s
                """,
                (target_group_id, dest_id, personal_id, archivo_id)
            )

        # Mover logs y movimientos al grupo destino
        cur.execute(
            "UPDATE logs SET grupo_id = %s WHERE grupo_id = %s",
            (target_group_id, personal_id)
        )
        cur.execute(
            "UPDATE movimientos SET grupo_id = %s WHERE grupo_id = %s",
            (target_group_id, personal_id)
        )

        # Borrar cajas del grupo personal y archivar el grupo
        cur.execute("DELETE FROM cajas WHERE grupo_id = %s", (personal_id,))
        cur.execute(
            "UPDATE grupos SET archivado = 1, archivado_en = SYSDATETIME() WHERE id = %s",
            (personal_id,)
        )
        conn.commit()

    cur.close()
    conn.close()


def archivar_grupo(grupo_id, admin_user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM grupos WHERE id = %s", (grupo_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return False

    cur.execute("SELECT id FROM grupos WHERE nombre = %s", ("Archivador",))
    arch_row = cur.fetchone()
    if arch_row:
        arch_id = arch_row[0]
    else:
        cur.execute(
            "INSERT INTO grupos (nombre, creado_por) VALUES (%s, %s) RETURNING id",
            ("Archivador", admin_user_id)
        )
        arch_id = cur.fetchone()[0]

    cur.execute(
        "SELECT id FROM cajas WHERE grupo_id = %s AND is_pendiente = 1",
        (arch_id,)
    )
    row = cur.fetchone()
    if row:
        pendiente_id = row[0]
    else:
        cur.execute(
            """
            INSERT INTO cajas (rango_min, rango_max, creado_por, grupo_id, is_pendiente)
            VALUES (%s, %s, %s, %s, 1)
            RETURNING id
            """,
            (-1, -1, admin_user_id, arch_id)
        )
        pendiente_id = cur.fetchone()[0]

    # Mover cajas al Archivador (mantiene rangos y caja_id)
    cur.execute(
        """
        UPDATE cajas
        SET grupo_id = %s,
            grupo_origen_id = %s
        WHERE grupo_id = %s
        """,
        (arch_id, grupo_id, grupo_id)
    )

    # Mover archivos al Archivador
    cur.execute(
        """
        UPDATE archivos
        SET grupo_id = %s,
            grupo_origen_id = %s
        WHERE grupo_id = %s
        """,
        (arch_id, grupo_id, grupo_id)
    )

    # Reasignar archivos huérfanos a caja pendiente del Archivador
    cur.execute(
        """
        UPDATE archivos
        SET caja_id = %s
        WHERE grupo_id = %s AND caja_id NOT IN (
            SELECT id FROM cajas WHERE grupo_id = %s
        )
        """,
        (pendiente_id, arch_id, arch_id)
    )

    # Mover logs y movimientos al Archivador
    cur.execute(
        "UPDATE logs SET grupo_id = %s WHERE grupo_id = %s",
        (arch_id, grupo_id)
    )
    cur.execute(
        "UPDATE movimientos SET grupo_id = %s WHERE grupo_id = %s",
        (arch_id, grupo_id)
    )

    # Quitar membresías y archivar el grupo
    cur.execute("DELETE FROM usuariosempresas WHERE empresa = %s", (grupo_id,))
    cur.execute("DELETE FROM usuariosregistrados WHERE empresa = %s", (grupo_id,))
    cur.execute(
        "UPDATE grupos SET archivado = 1, archivado_en = SYSDATETIME() WHERE id = %s",
        (grupo_id,)
    )

    conn.commit()
    cur.close()
    conn.close()
    return True
