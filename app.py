print(">>> APP.PY CORRECTO CARGADO <<<")

from flask import Flask, render_template, request, redirect, url_for, session
from cajas import crear_caja
from archivos import agregar_archivo, modificar_archivo, eliminar_archivo
from auth import crear_usuario, verificar_usuario, obtener_usuario_y_rol
from logs import registrar_log
from db import get_db

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


if __name__ == "__main__":
    app.run(debug=True)
