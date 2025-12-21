import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB = "archivo.db"

def crear_usuario(usuario, password):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    hash_pw = generate_password_hash(password)

    cursor.execute(
        "INSERT INTO usuarios (usuario, password) VALUES (?, ?)",
        (usuario, hash_pw)
    )

    conn.commit()
    conn.close()


def verificar_usuario(usuario, password):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT password FROM usuarios WHERE usuario = ?",
        (usuario,)
    )

    dato = cursor.fetchone()
    conn.close()

    if dato and check_password_hash(dato[0], password):
        return True
    return False
