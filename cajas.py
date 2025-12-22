from db import get_db

def crear_caja(rango_min, rango_max, creado_por=None):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO cajas (rango_min, rango_max, creado_por) VALUES (%s, %s, %s)",
        (rango_min, rango_max, creado_por)
    )

    conn.commit()
    cur.close()
    conn.close()
