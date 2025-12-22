from db import get_db

def _buscar_caja_para_numero(cur, numero):
    cur.execute(
        "SELECT id FROM cajas WHERE %s BETWEEN rango_min AND rango_max LIMIT 1",
        (numero,)
    )
    fila = cur.fetchone()
    return fila[0] if fila else None


def agregar_archivo(numero, nombre, creado_por=None):
    conn = get_db()
    cur = conn.cursor()

    caja_id = _buscar_caja_para_numero(cur, numero)
    if caja_id is None:
        cur.close()
        conn.close()
        raise ValueError("No existe una caja cuyo rango contenga ese número de archivo.")

    cur.execute(
        "INSERT INTO archivos (numero, nombre, caja_id, creado_por) VALUES (%s, %s, %s, %s)",
        (numero, nombre, caja_id, creado_por)
    )

    conn.commit()
    cur.close()
    conn.close()


def modificar_archivo(numero, nombre):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE archivos SET nombre = %s WHERE numero = %s",
        (nombre, numero)
    )

    conn.commit()
    cur.close()
    conn.close()


def eliminar_archivo(numero):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM archivos WHERE numero = %s",
        (numero,)
    )

    conn.commit()
    cur.close()
    conn.close()
