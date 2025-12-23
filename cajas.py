from db import get_db


def crear_caja(rango_min, rango_max, creado_por=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO cajas (rango_min, rango_max, creado_por)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (rango_min, rango_max, creado_por)
    )

    caja_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return caja_id


def asegurar_caja_sin_asignar():
    """
    Crea la Caja 0 si no existe.
    Usamos rango_min=-1 y rango_max=-1 para cumplir NOT NULL.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM cajas WHERE id = 0")
    existe = cur.fetchone()

    if not existe:
        cur.execute(
            "INSERT INTO cajas (id, rango_min, rango_max, creado_por) VALUES (%s, %s, %s, %s)",
            (0, -1, -1, None)
        )
        conn.commit()

    cur.close()
    conn.close()


def reubicar_archivos_pendientes_por_nueva_caja(caja_id):
    """
    Mueve archivos de Caja 0 que encajen en el rango de esta caja.
    Retorna cuántos movió.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT rango_min, rango_max FROM cajas WHERE id = %s", (caja_id,))
    rango = cur.fetchone()
    if not rango:
        cur.close()
        conn.close()
        return 0

    rmin, rmax = rango

    cur.execute("""
        SELECT id
        FROM archivos
        WHERE caja_id = 0
          AND numero BETWEEN %s AND %s
    """, (rmin, rmax))

    archivos = cur.fetchall()
    contador = 0

    for (archivo_id,) in archivos:
        cur.execute(
            "UPDATE archivos SET caja_id = %s WHERE id = %s",
            (caja_id, archivo_id)
        )
        contador += 1

    conn.commit()
    cur.close()
    conn.close()

    return contador


def modificar_caja(caja_id, nuevo_min, nuevo_max):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE cajas
        SET rango_min = %s, rango_max = %s
        WHERE id = %s
    """, (nuevo_min, nuevo_max, caja_id))

    conn.commit()
    cur.close()
    conn.close()


def reubicar_archivos_de_caja(caja_id):
    """
    Después de modificar rangos, saca de esta caja los archivos que ya no caben.
    Los mueve a otra caja si existe, o a Caja 0 si no existe.
    Retorna cuántos movió.
    """
    if caja_id == 0:
        return 0

    asegurar_caja_sin_asignar()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT rango_min, rango_max FROM cajas WHERE id = %s", (caja_id,))
    rango = cur.fetchone()
    if not rango:
        cur.close()
        conn.close()
        return 0

    rmin, rmax = rango

    cur.execute("""
        SELECT id, numero
        FROM archivos
        WHERE caja_id = %s
          AND NOT (%s <= numero AND numero <= %s)
    """, (caja_id, rmin, rmax))

    fuera = cur.fetchall()
    contador = 0

    for archivo_id, numero in fuera:
        cur.execute("""
            SELECT id
            FROM cajas
            WHERE id <> %s
              AND id <> 0
              AND %s BETWEEN rango_min AND rango_max
            ORDER BY rango_min, id
            LIMIT 1
        """, (caja_id, numero))

        destino = cur.fetchone()
        destino_id = destino[0] if destino else 0

        cur.execute(
            "UPDATE archivos SET caja_id = %s WHERE id = %s",
            (destino_id, archivo_id)
        )
        contador += 1

    conn.commit()
    cur.close()
    conn.close()

    return contador


def eliminar_caja(caja_id):
    """
    Elimina una caja sin borrar archivos:
    - mueve sus archivos a otra caja por rango si existe
    - si no, a Caja 0
    - luego borra la caja
    """
    if caja_id == 0:
        return

    asegurar_caja_sin_asignar()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, numero FROM archivos WHERE caja_id = %s", (caja_id,))
    archivos = cur.fetchall()

    for archivo_id, numero in archivos:
        cur.execute("""
            SELECT id
            FROM cajas
            WHERE id <> %s
              AND id <> 0
              AND %s BETWEEN rango_min AND rango_max
            ORDER BY rango_min, id
            LIMIT 1
        """, (caja_id, numero))

        destino = cur.fetchone()
        destino_id = destino[0] if destino else 0

        cur.execute(
            "UPDATE archivos SET caja_id = %s WHERE id = %s",
            (destino_id, archivo_id)
        )

    cur.execute("DELETE FROM cajas WHERE id = %s", (caja_id,))

    conn.commit()
    cur.close()
    conn.close()
