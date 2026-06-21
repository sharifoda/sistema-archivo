from db import get_db
from historial import registrar_movimiento


def _rowcount_or_zero(cur):
    return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0


def _get_caja_pendiente_id(cur, grupo_id):
    cur.execute(
        "SELECT id FROM cajas WHERE grupo_id = %s AND is_pendiente = 1",
        (grupo_id,)
    )
    row = cur.fetchone()
    return row[0] if row else None


def crear_caja(rango_min, rango_max, grupo_id, creado_por=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO cajas (rango_min, rango_max, creado_por, grupo_id, is_pendiente)
        VALUES (%s, %s, %s, %s, 0)
        RETURNING id
        """,
        (rango_min, rango_max, creado_por, grupo_id)
    )

    caja_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    registrar_movimiento(
        creado_por,
        grupo_id,
        entidad="caja",
        entidad_id=caja_id,
        accion="CREAR_CAJA",
        datos_despues={"id": caja_id, "rango_min": rango_min, "rango_max": rango_max}
    )

    return caja_id


def asegurar_caja_sin_asignar(grupo_id):
    """
    Crea la caja pendiente si no existe.
    Usamos rango_min=-1 y rango_max=-1 para cumplir NOT NULL.
    """
    conn = get_db()
    cur = conn.cursor()

    pendiente_id = _get_caja_pendiente_id(cur, grupo_id)

    if pendiente_id is None:
        cur.execute(
            """
            INSERT INTO cajas (rango_min, rango_max, creado_por, grupo_id, is_pendiente)
            VALUES (%s, %s, %s, %s, 1)
            RETURNING id
            """,
            (-1, -1, None, grupo_id)
        )
        pendiente_id = cur.fetchone()[0]
        conn.commit()

    cur.close()
    conn.close()
    return pendiente_id


def reparar_archivos_huerfanos(grupo_id):
    """
    Reasigna a la caja pendiente los archivos cuya caja no existe
    o pertenece a otra empresa/grupo.
    """
    conn = get_db()
    cur = conn.cursor()

    pendiente_id = _get_caja_pendiente_id(cur, grupo_id)
    if pendiente_id is None:
        cur.execute(
            """
            INSERT INTO cajas (rango_min, rango_max, creado_por, grupo_id, is_pendiente)
            VALUES (%s, %s, %s, %s, 1)
            RETURNING id
            """,
            (-1, -1, None, grupo_id)
        )
        pendiente_id = cur.fetchone()[0]

    cur.execute(
        """
        UPDATE archivos
        SET caja_id = %s
        WHERE grupo_id = %s
          AND NOT EXISTS (
              SELECT 1
              FROM cajas c
              WHERE c.id = archivos.caja_id
                AND c.grupo_id = %s
          )
        """,
        (pendiente_id, grupo_id, grupo_id)
    )

    afectados = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    conn.commit()
    cur.close()
    conn.close()
    return afectados


def reubicar_archivos_pendientes_por_nueva_caja(caja_id, grupo_id, usuario_id=None):
    """
    Mueve archivos de la caja pendiente que encajen en el rango de esta caja.
    Retorna cuantos movio.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT rango_min, rango_max FROM cajas WHERE id = %s AND grupo_id = %s",
        (caja_id, grupo_id)
    )
    rango = cur.fetchone()
    if not rango:
        cur.close()
        conn.close()
        return 0

    rmin, rmax = rango
    pendiente_id = _get_caja_pendiente_id(cur, grupo_id)
    if pendiente_id is None:
        cur.close()
        conn.close()
        return 0

    cur.execute(
        """
        UPDATE archivos
        SET caja_id = %s
        WHERE caja_id = %s
          AND grupo_id = %s
          AND numero BETWEEN %s AND %s
        """,
        (caja_id, pendiente_id, grupo_id, rmin, rmax)
    )

    contador = _rowcount_or_zero(cur)

    conn.commit()
    cur.close()
    conn.close()

    return contador


def modificar_caja(caja_id, nuevo_min, nuevo_max, grupo_id, usuario_id=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT rango_min, rango_max FROM cajas WHERE id = %s AND grupo_id = %s",
        (caja_id, grupo_id)
    )
    antes = cur.fetchone()

    cur.execute(
        """
        UPDATE cajas
        SET rango_min = %s, rango_max = %s
        WHERE id = %s AND grupo_id = %s
        """,
        (nuevo_min, nuevo_max, caja_id, grupo_id)
    )

    conn.commit()
    cur.close()
    conn.close()

    if not antes:
        return None

    return {
        "rango_min": antes[0],
        "rango_max": antes[1],
        "nuevo_min": nuevo_min,
        "nuevo_max": nuevo_max,
    }


def reubicar_archivos_de_caja(caja_id, grupo_id, usuario_id=None):
    """
    Despues de modificar rangos, saca de esta caja los archivos que ya no caben.
    Los mueve a otra caja si existe, o a la caja pendiente si no existe.
    Retorna cuantos movio.
    """
    pendiente_id = asegurar_caja_sin_asignar(grupo_id)
    if caja_id == pendiente_id:
        return 0

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT rango_min, rango_max FROM cajas WHERE id = %s AND grupo_id = %s",
        (caja_id, grupo_id)
    )
    rango = cur.fetchone()
    if not rango:
        cur.close()
        conn.close()
        return 0

    rmin, rmax = rango

    cur.execute(
        """
        UPDATE a
        SET caja_id = COALESCE(dest.id, %s)
        FROM archivos a
        OUTER APPLY (
            SELECT TOP 1 c.id
            FROM cajas c
            WHERE c.id <> %s
              AND c.grupo_id = %s
              AND c.is_pendiente = 0
              AND a.numero BETWEEN c.rango_min AND c.rango_max
            ORDER BY c.rango_min, c.id
        ) dest
        WHERE a.caja_id = %s
          AND a.grupo_id = %s
          AND NOT (%s <= a.numero AND a.numero <= %s)
        """,
        (pendiente_id, caja_id, grupo_id, caja_id, grupo_id, rmin, rmax)
    )

    contador = _rowcount_or_zero(cur)

    conn.commit()
    cur.close()
    conn.close()

    return contador


def eliminar_caja(caja_id, grupo_id, usuario_id=None):
    """
    Elimina una caja sin borrar archivos:
    - mueve sus archivos a otra caja por rango si existe
    - si no, a la caja pendiente
    - luego borra la caja
    """
    pendiente_id = asegurar_caja_sin_asignar(grupo_id)
    if caja_id == pendiente_id:
        return None

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT rango_min, rango_max FROM cajas WHERE id = %s AND grupo_id = %s",
        (caja_id, grupo_id)
    )
    antes = cur.fetchone()

    cur.execute(
        """
        UPDATE a
        SET caja_id = COALESCE(dest.id, %s)
        FROM archivos a
        OUTER APPLY (
            SELECT TOP 1 c.id
            FROM cajas c
            WHERE c.id <> %s
              AND c.grupo_id = %s
              AND c.is_pendiente = 0
              AND a.numero BETWEEN c.rango_min AND c.rango_max
            ORDER BY c.rango_min, c.id
        ) dest
        WHERE a.caja_id = %s
          AND a.grupo_id = %s
        """,
        (pendiente_id, caja_id, grupo_id, caja_id, grupo_id)
    )
    reasignados = _rowcount_or_zero(cur)

    cur.execute("DELETE FROM cajas WHERE id = %s AND grupo_id = %s", (caja_id, grupo_id))

    conn.commit()
    cur.close()
    conn.close()

    if not antes:
        return None

    return {
        "rango_min": antes[0],
        "rango_max": antes[1],
        "reasignados": reasignados,
    }
