from psycopg2.extras import Json
from db import get_db


def registrar_movimiento(
    usuario_id,
    grupo_id,
    entidad,
    entidad_id,
    accion,
    datos_antes=None,
    datos_despues=None,
    meta=None
):
    if not usuario_id or not grupo_id:
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO movimientos (
            usuario_id,
            grupo_id,
            entidad,
            entidad_id,
            accion,
            datos_antes,
            datos_despues,
            meta
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            usuario_id,
            grupo_id,
            entidad,
            entidad_id,
            accion,
            Json(datos_antes) if datos_antes is not None else None,
            Json(datos_despues) if datos_despues is not None else None,
            Json(meta) if meta is not None else None,
        )
    )

    conn.commit()
    cur.close()
    conn.close()
