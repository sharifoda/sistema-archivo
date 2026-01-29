from db import get_db
from historial import registrar_movimiento


def _buscar_caja_para_numero(cur, numero, grupo_id):
    cur.execute(
        """
        SELECT id
        FROM cajas
        WHERE grupo_id = %s
          AND is_pendiente = FALSE
          AND %s BETWEEN rango_min AND rango_max
        LIMIT 1
        """,
        (grupo_id, numero)
    )
    fila = cur.fetchone()
    return fila[0] if fila else None


def agregar_archivo(numero, nombre, grupo_id, creado_por=None, tipo_doc="CC"):
    conn = get_db()
    cur = conn.cursor()

    caja_id = _buscar_caja_para_numero(cur, numero, grupo_id)
    if caja_id is None:
        cur.close()
        conn.close()
        raise ValueError("No existe una caja cuyo rango contenga ese numero de archivo.")

    cur.execute(
        """
        INSERT INTO archivos (numero, nombre, caja_id, creado_por, grupo_id, tipo_doc)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (numero, nombre, caja_id, creado_por, grupo_id, tipo_doc)
    )
    archivo_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    registrar_movimiento(
        creado_por,
        grupo_id,
        entidad="archivo",
        entidad_id=archivo_id,
        accion="CREAR_ARCHIVO",
        datos_despues={"id": archivo_id, "numero": numero, "nombre": nombre, "caja_id": caja_id, "tipo_doc": tipo_doc},
    )


def modificar_archivo(numero, nombre, grupo_id, usuario_id=None, tipo_doc=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, nombre, tipo_doc FROM archivos WHERE numero = %s AND grupo_id = %s",
        (numero, grupo_id)
    )
    antes = cur.fetchone()

    if tipo_doc:
        cur.execute(
            "UPDATE archivos SET nombre = %s, tipo_doc = %s WHERE numero = %s AND grupo_id = %s",
            (nombre, tipo_doc, numero, grupo_id)
        )
    else:
        cur.execute(
            "UPDATE archivos SET nombre = %s WHERE numero = %s AND grupo_id = %s",
            (nombre, numero, grupo_id)
        )

    conn.commit()
    cur.close()
    conn.close()

    if antes:
        registrar_movimiento(
            usuario_id,
            grupo_id,
            entidad="archivo",
            entidad_id=antes[0],
            accion="MODIFICAR_ARCHIVO",
            datos_antes={"nombre": antes[1], "tipo_doc": antes[2]},
            datos_despues={"nombre": nombre, "tipo_doc": tipo_doc or antes[2]},
        )


def eliminar_archivo(numero, grupo_id, usuario_id=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, numero, nombre, caja_id, pdf_path, tipo_doc FROM archivos WHERE numero = %s AND grupo_id = %s",
        (numero, grupo_id)
    )
    antes = cur.fetchone()

    cur.execute(
        "DELETE FROM archivos WHERE numero = %s AND grupo_id = %s",
        (numero, grupo_id)
    )

    conn.commit()
    cur.close()
    conn.close()

    if antes:
        registrar_movimiento(
            usuario_id,
            grupo_id,
            entidad="archivo",
            entidad_id=antes[0],
            accion="ELIMINAR_ARCHIVO",
            datos_antes={
                "id": antes[0],
                "numero": antes[1],
                "nombre": antes[2],
                "caja_id": antes[3],
                "pdf_path": antes[4],
                "tipo_doc": antes[5],
            },
        )
