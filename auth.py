from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db


def crear_usuario(usuario, password, rol="cliente"):
    """
    Crea un usuario nuevo con contraseña hasheada.
    rol: 'admin' o 'cliente'
    """
    conn = get_db()
    cur = conn.cursor()

    hash_pw = generate_password_hash(password)

    try:
        cur.execute("SELECT 1 FROM usuarios WHERE usuario = %s", (usuario,))
        if cur.fetchone():
            conn.rollback()
            return False
        cur.execute(
            "INSERT INTO usuarios (usuario, [contraseña], rol) VALUES (%s, %s, %s) RETURNING id",
            (usuario, hash_pw, rol)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def verificar_usuario(usuario, password):
    """
    Verifica credenciales. Devuelve:
      - (id, rol) si son válidas
      - None si son inválidas
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, [contraseña], rol FROM usuarios WHERE usuario = %s AND activo = 1",
        (usuario,)
    )

    dato = cur.fetchone()

    cur.close()
    conn.close()

    if not dato:
        return None

    user_id, hash_pw, rol = dato

    if check_password_hash(hash_pw, password):
        return (user_id, rol)

    return None


def obtener_usuario_y_rol(usuario):
    """
    (Opcional) Si lo sigues usando en otras partes.
    Devuelve (id, rol) o None.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, rol FROM usuarios WHERE usuario = %s AND activo = 1",
        (usuario,)
    )

    dato = cur.fetchone()

    cur.close()
    conn.close()

    return dato


def usuario_existe(usuario):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM usuarios WHERE usuario = %s AND activo = 1",
        (usuario,)
    )
    row = cur.fetchone()

    cur.close()
    conn.close()

    return row is not None
