from db import get_db


def registrar_log(usuario_id, accion, ip=None, grupo_id=None):
    """
    Guarda un log en la tabla logs.
    usuario_id: int (id del usuario en la tabla usuarios)
    accion: str (ej: 'LOGIN', 'CREAR_CAJA', etc.)
    ip: str (opcional)
    """
    if not usuario_id:
        return  # si por alguna razón no hay usuario_id, no registramos

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO auditoria (usuarioid, accion, direccionip, empresa)
        VALUES (%s, %s, %s, %s)
        """,
        (usuario_id, accion, ip, grupo_id)
    )

    conn.commit()
    cur.close()
    conn.close()
