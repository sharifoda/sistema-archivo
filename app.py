print(">>> APP.PY CORRECTO CARGADO <<<")

from flask import Flask, render_template, request, redirect, url_for, session, send_file
from cajas import (
    crear_caja,
    eliminar_caja,
    modificar_caja,
    asegurar_caja_sin_asignar,
    reubicar_archivos_de_caja,
    reubicar_archivos_pendientes_por_nueva_caja
)
from archivos import agregar_archivo, modificar_archivo, eliminar_archivo
from auth import crear_usuario, verificar_usuario, obtener_usuario_y_rol
from logs import registrar_log
from db import get_db
from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font
from flask import flash

app = Flask(__name__)
app.secret_key = "clave_super_secreta"


def login_requerido():
    return "usuario" in session


def admin_requerido():
    return session.get("rol") == "admin"


# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        info = verificar_usuario(usuario, password)  # (id, rol) o None
        if info:
            session["usuario"] = usuario
            session["usuario_id"] = info[0]
            session["rol"] = info[1]

            # LOG: LOGIN
            registrar_log(session.get("usuario_id"), "LOGIN", request.remote_addr)

            return redirect(url_for("inicio"))

    return render_template("login.html")


# ---------------- REGISTRO ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        # Intento de crear usuario (debe devolver True/False si usas el auth.py mejorado)
        ok = crear_usuario(usuario, password, rol="cliente")

        # Si tu crear_usuario no devuelve nada (None), lo tratamos como éxito
        if ok is False:
            return render_template("register.html", error="El usuario ya existe")

        return redirect(url_for("login"))

    # GET
    return render_template("register.html")



# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    # LOG: LOGOUT (antes de borrar sesión)
    registrar_log(session.get("usuario_id"), "LOGOUT", request.remote_addr)

    session.clear()
    return redirect(url_for("login"))


# ---------------- INICIO (BIENVENIDA) ----------------
@app.route("/inicio")
def inicio():
    if not login_requerido():
        return redirect(url_for("login"))

    return render_template("inicio.html")


# ---------------- CAJAS ----------------
@app.route("/cajas", methods=["GET", "POST"])
def cajas():
    if not login_requerido():
        return redirect(url_for("login"))

    # Asegurar que siempre exista la Caja 0
    asegurar_caja_sin_asignar()

    if request.method == "POST":
        accion = request.form.get("accion")

        # ======================
        # ELIMINAR CAJA
        # ======================
        if accion == "eliminar":
            caja_id = int(request.form["caja_id"])

            eliminar_caja(caja_id)

            registrar_log(
                session.get("usuario_id"),
                f"ELIMINAR_CAJA caja_id={caja_id}",
                request.remote_addr
            )

            return redirect(url_for("cajas"))

        # ======================
        # MODIFICAR CAJA
        # ======================
        if accion == "modificar":
            caja_id = int(request.form["caja_id"])
            nuevo_min = int(request.form["rango_min"])
            nuevo_max = int(request.form["rango_max"])

            modificar_caja(caja_id, nuevo_min, nuevo_max)

            # 1) Sacar archivos que ya no caben
            movidos_fuera = reubicar_archivos_de_caja(caja_id)

            # 2) Meter archivos pendientes que ahora sí caben
            movidos_dentro = reubicar_archivos_pendientes_por_nueva_caja(caja_id)

            total_movidos = movidos_fuera + movidos_dentro

            if total_movidos > 0:
                flash(
                    f"Se reasignaron automáticamente {total_movidos} archivo(s) según el nuevo rango.",
                    "success"
                )
            else:
                flash(
                    "El rango se actualizó. No fue necesario reasignar archivos.",
                    "info"
                )

            registrar_log(
                session.get("usuario_id"),
                f"MODIFICAR_CAJA caja_id={caja_id} rango={nuevo_min}-{nuevo_max} reasignados={total_movidos}",
                request.remote_addr
            )

            return redirect(url_for("cajas"))



        # ======================
        # CREAR CAJA
        # ======================
        rmin = int(request.form["rango_min"])
        rmax = int(request.form["rango_max"])

        nueva_caja_id = crear_caja(
            rmin,
            rmax,
            creado_por=session.get("usuario_id")
        )

        # Reubicar archivos pendientes (Caja 0) si encajan en la nueva caja
        reubicar_archivos_pendientes_por_nueva_caja(nueva_caja_id)

        registrar_log(
            session.get("usuario_id"),
            f"CREAR_CAJA rango={rmin}-{rmax}",
            request.remote_addr
        )

        return redirect(url_for("cajas"))

    # ======================
    # LISTADO DE CAJAS
    # ======================
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        WITH ranked AS (
            SELECT
                id,
                rango_min,
                rango_max,
                ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE id <> 0
        )
        SELECT
            c.id AS caja_id,
            COUNT(a.id) AS total_archivos,
            c.rango_min,
            c.rango_max,
            CASE
                WHEN c.id = 0 THEN 0
                ELSE r.caja_visible
            END AS caja_visible
        FROM cajas c
        LEFT JOIN archivos a ON a.caja_id = c.id
        LEFT JOIN ranked r ON r.id = c.id
        GROUP BY c.id, c.rango_min, c.rango_max, r.caja_visible
        ORDER BY
            CASE WHEN c.id = 0 THEN 1 ELSE 0 END,
            caja_visible
    """)

    cajas_data = cur.fetchall()
    cur.close()
    conn.close()

    # Ocultar Caja 0 si está vacía
    cajas_filtradas = []
    for c in cajas_data:
        if c[0] == 0 and c[1] == 0:
            continue
        cajas_filtradas.append(c)

    return render_template("cajas.html", cajas=cajas_filtradas)



# ---------------- ARCHIVOS ----------------
@app.route("/archivos", methods=["GET", "POST"])
def archivos():
    if not login_requerido():
        return redirect(url_for("login"))

    # =========================
    # POST: agregar / modificar fila / eliminar fila
    # =========================
    if request.method == "POST":
        accion = request.form["accion"]

        # ✅ AGREGAR (formulario de arriba)
        if accion == "agregar":
            numero = int(request.form["numero"])
            nombre = request.form.get("nombre", "").strip()

            agregar_archivo(numero, nombre, creado_por=session.get("usuario_id"))

            # Log con info real
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT caja_id, nombre FROM archivos WHERE numero = %s", (numero,))
            info = cur.fetchone()
            caja_id = info[0] if info else 0
            nombre_final = info[1] if info else nombre
            cur.close()
            conn.close()

            registrar_log(
                session.get("usuario_id"),
                f"AGREGAR_ARCHIVO | caja_id={caja_id} | numero={numero} | nombre={nombre_final}",
                request.remote_addr
            )

            return redirect(url_for("archivos"))

       # ✅ MODIFICAR DESDE FILA (popup)
        if accion == "modificar_fila":
            numero_old = int(request.form["numero_old"])
            numero_new = int(request.form["numero_new"])
            nombre_new = request.form.get("nombre_new", "").strip()

            conn = get_db()
            cur = conn.cursor()

            cur.execute("SELECT caja_id FROM archivos WHERE numero = %s", (numero_old,))
            antes = cur.fetchone()
            caja_id = antes[0] if antes else 0

            cur.execute("""
                UPDATE archivos
                SET numero = %s, nombre = %s
                WHERE numero = %s
            """, (numero_new, nombre_new, numero_old))

            conn.commit()
            cur.close()
            conn.close()

            registrar_log(
                session.get("usuario_id"),
                f"MODIFICAR_ARCHIVO | caja_id={caja_id} | numero={numero_new} | nombre={nombre_new}",
                request.remote_addr
            )

            return redirect(url_for("archivos"))


        # ✅ ELIMINAR DESDE FILA
        if accion == "eliminar_fila":
            numero = int(request.form["numero"])

            conn = get_db()
            cur = conn.cursor()

            # guardar info antes de borrar
            cur.execute("SELECT caja_id, nombre FROM archivos WHERE numero = %s", (numero,))
            antes = cur.fetchone()
            caja_id = antes[0] if antes else 0
            nombre_final = antes[1] if antes else ""

            cur.close()
            conn.close()

            eliminar_archivo(numero)

            registrar_log(
                session.get("usuario_id"),
                f"ELIMINAR_ARCHIVO | caja_id={caja_id} | numero={numero} | nombre={nombre_final}",
                request.remote_addr
            )

            return redirect(url_for("archivos"))

        # Si llega una acción desconocida:
        return redirect(url_for("archivos"))

    # =========================
    # GET: listado + búsqueda + últimos movimientos + modo edición
    # =========================
    conn = get_db()
    cur = conn.cursor()

    # Listado normal (caja visible 1..N y caja 0)
    cur.execute("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE id <> 0
        )
        SELECT
            CASE WHEN c.id = 0 THEN 0 ELSE r.caja_visible END AS caja,
            a.numero AS documento,
            a.nombre AS nombre
        FROM archivos a
        JOIN cajas c ON a.caja_id = c.id
        LEFT JOIN ranked r ON r.id = c.id
        ORDER BY caja, a.numero
    """)
    datos = cur.fetchall()

    # Buscador
    resultado = None
    buscar = request.args.get("buscar", "").strip()
    if buscar:
        try:
            doc = int(buscar)
            cur.execute("""
                WITH ranked AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
                    FROM cajas
                    WHERE id <> 0
                )
                SELECT
                    CASE WHEN c.id = 0 THEN 0 ELSE r.caja_visible END AS caja,
                    a.numero AS documento,
                    a.nombre AS nombre
                FROM archivos a
                JOIN cajas c ON a.caja_id = c.id
                LEFT JOIN ranked r ON r.id = c.id
                WHERE a.numero = %s
                LIMIT 1
            """, (doc,))
            resultado = cur.fetchone()
        except ValueError:
            resultado = ("error", buscar, None)

    # Modo edición (qué documento está en edición)
    edit_num = request.args.get("edit", "").strip()
    edit_num = int(edit_num) if edit_num.isdigit() else None

    # Últimos movimientos (10)
    cur.execute("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE id <> 0
        ),
        base AS (
            SELECT
                l.fecha,
                l.accion,
                NULLIF(substring(l.accion from 'caja_id=([0-9]+)') , '')::int AS caja_id,
                NULLIF(substring(l.accion from 'numero=([0-9]+)') , '')::bigint AS documento,
                substring(l.accion from 'nombre=([^|]+)') AS nombre,
                CASE
                    WHEN l.accion LIKE 'AGREGAR_ARCHIVO%' THEN 'Registro'
                    WHEN l.accion LIKE 'MODIFICAR_ARCHIVO%' THEN 'Modificación'
                    WHEN l.accion LIKE 'ELIMINAR_ARCHIVO%' THEN 'Eliminación'
                    ELSE 'Otro'
                END AS tipo
            FROM logs l
            WHERE l.accion LIKE 'AGREGAR_ARCHIVO%'
               OR l.accion LIKE 'MODIFICAR_ARCHIVO%'
               OR l.accion LIKE 'ELIMINAR_ARCHIVO%'
            ORDER BY l.fecha DESC
            LIMIT 10
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY b.fecha DESC) AS movimiento,
            CASE
                WHEN COALESCE(b.caja_id, a.caja_id, 0) = 0 THEN 0
                ELSE r.caja_visible
            END AS caja,
            COALESCE(b.documento, a.numero) AS documento,
            COALESCE(b.nombre, a.nombre, '') AS nombre,
            b.tipo
        FROM base b
        LEFT JOIN archivos a ON a.numero = b.documento
        LEFT JOIN ranked r ON r.id = COALESCE(b.caja_id, a.caja_id)
        ORDER BY movimiento
    """)
    movimientos = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "archivos.html",
        archivos=datos,
        resultado=resultado,
        movimientos=movimientos,
        edit_num=edit_num
    )




# ---------------- ADMIN: LOGS ----------------
@app.route("/admin/logs")
def admin_logs():
    if not login_requerido():
        return redirect(url_for("login"))

    if not admin_requerido():
        return "Acceso denegado", 403

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.usuario, l.accion, l.fecha, l.ip
        FROM logs l
        JOIN usuarios u ON u.id = l.usuario_id
        ORDER BY l.fecha DESC
        LIMIT 200
    """)

    registros = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin_logs.html", registros=registros)

@app.route("/export/excel")
def export_excel():
    if not login_requerido():
        return redirect(url_for("login"))

    # 1) Consultas a la DB
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, rango_min, rango_max, fecha FROM cajas ORDER BY rango_min")
    cajas_data = cur.fetchall()

    cur.execute("""
        SELECT a.numero, a.nombre, c.rango_min, c.rango_max, a.fecha
        FROM archivos a
        JOIN cajas c ON a.caja_id = c.id
        ORDER BY a.numero
    """)
    archivos_data = cur.fetchall()

    cur.close()
    conn.close()

    # 2) Crear Excel
    wb = Workbook()

    # Hoja 1: Cajas
    ws_cajas = wb.active
    ws_cajas.title = "Cajas"
    headers_cajas = ["ID", "Rango mínimo", "Rango máximo", "Fecha"]
    ws_cajas.append(headers_cajas)
    for cell in ws_cajas[1]:
        cell.font = Font(bold=True)

    for row in cajas_data:
        ws_cajas.append(list(row))

    # Hoja 2: Archivos
    ws_archivos = wb.create_sheet(title="Archivos")
    headers_archivos = ["Número", "Nombre", "Rango min caja", "Rango max caja", "Fecha"]
    ws_archivos.append(headers_archivos)
    for cell in ws_archivos[1]:
        cell.font = Font(bold=True)

    for row in archivos_data:
        ws_archivos.append(list(row))

    # Ajuste simple de ancho de columnas (opcional)
    for ws in [ws_cajas, ws_archivos]:
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    max_len = max(max_len, len(str(cell.value)) if cell.value is not None else 0)
                except:
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + 2, 45)

    # 3) Enviar como descarga
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    fecha = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"reporte_cajas_archivos_{fecha}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(debug=True)
