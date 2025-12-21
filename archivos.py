import sqlite3

def obtener_caja(numero):
    conn = sqlite3.connect("archivo.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM cajas
        WHERE ? BETWEEN rango_min AND rango_max
    """, (numero,))

    caja = cursor.fetchone()
    conn.close()

    return caja[0] if caja else None


def agregar_archivo(numero, nombre):
    caja_id = obtener_caja(numero)
    if not caja_id:
        return

    conn = sqlite3.connect("archivo.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO archivos (numero, nombre, caja_id) VALUES (?, ?, ?)",
        (numero, nombre, caja_id)
    )

    conn.commit()
    conn.close()


def modificar_archivo(numero, nombre):
    conn = sqlite3.connect("archivo.db")
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE archivos SET nombre = ? WHERE numero = ?",
        (nombre, numero)
    )

    conn.commit()
    conn.close()


def eliminar_archivo(numero):
    conn = sqlite3.connect("archivo.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM archivos WHERE numero = ?",
        (numero,)
    )

    conn.commit()
    conn.close()