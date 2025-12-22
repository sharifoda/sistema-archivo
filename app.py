print(">>> APP.PY CORRECTO CARGADO <<<")

from flask import Flask, render_template, request, redirect, url_for, session, send_file
from cajas import crear_caja
from archivos import agregar_archivo, modificar_archivo, eliminar_archivo
from auth import crear_usuario, verificar_usuario, obtener_usuario_y_rol
from logs import registrar_log
from db import get_db
from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font

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

    if request.method == "POST":
        rmin = int(request.form["rango_min"])
        rmax = int(request.form["rango_max"])

        crear_caja(rmin, rmax, creado_por=session.get("usuario_id"))

        # LOG: CREAR_CAJA
        registrar_log(
            session.get("usuario_id"),
            f"CREAR_CAJA rango={rmin}-{rmax}",
            request.remote_addr
        )

        return redirect(url_for("cajas"))

    return render_template("cajas.html")


# ---------------- ARCHIVOS ----------------
@app.route("/archivos", methods=["GET", "POST"])
def archivos():
    if not login_requerido():
        return redirect(url_for("login"))

    if request.method == "POST":
        accion = request.form["accion"]
        numero = int(request.form["numero"])
        nombre = request.form.get("nombre")

        if accion == "agregar":
            agregar_archivo(numero, nombre, creado_por=session.get("usuario_id"))
            registrar_log(session.get("usuario_id"), f"AGREGAR_ARCHIVO numero={numero}", request.remote_addr)

        elif accion == "modificar":
            modificar_archivo(numero, nombre)
            registrar_log(session.get("usuario_id"), f"MODIFICAR_ARCHIVO numero={numero}", request.remote_addr)

        elif accion == "eliminar":
            eliminar_archivo(numero)
            registrar_log(session.get("usuario_id"), f"ELIMINAR_ARCHIVO numero={numero}", request.remote_addr)

        return redirect(url_for("archivos"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT a.numero, a.nombre, c.rango_min, c.rango_max
        FROM archivos a
        JOIN cajas c ON a.caja_id = c.id
        ORDER BY a.numero
    """)

    datos = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("archivos.html", archivos=datos)


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
