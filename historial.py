import json
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
    item = f"{entidad}:{entidad_id}" if entidad_id is not None else entidad
    antes_texto = json.dumps(datos_antes, ensure_ascii=False) if datos_antes is not None else ""
    despues_texto = json.dumps(datos_despues, ensure_ascii=False) if datos_despues is not None else ""

    cur.execute(
        """
        INSERT INTO movimientos (
            usuarioid,
            empresa,
            accion,
            antes,
            despues,
            item
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            usuario_id,
            grupo_id,
            accion,
            antes_texto,
            despues_texto if despues_texto else (json.dumps(meta, ensure_ascii=False) if meta is not None else ""),
            item,
        )
    )

    conn.commit()
    cur.close()
    conn.close()
