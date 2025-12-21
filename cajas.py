import sqlite3

def crear_caja(rango_min, rango_max):
    conn = sqlite3.connect("archivo.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO cajas (rango_min, rango_max) VALUES (?, ?)",
        (rango_min, rango_max)
    )

    conn.commit()
    conn.close()
