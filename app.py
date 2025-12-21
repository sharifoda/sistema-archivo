print(">>> APP.PY CORRECTO CARGADO <<<")

from flask import Flask, render_template, request, redirect, url_for, session
from database import crear_base_datos
from cajas import crear_caja
from archivos import agregar_archivo, modificar_archivo, eliminar_archivo
from auth import crear_usuario, verificar_usuario
import sqlite3

app = Flask(__name__)
app.secret_key = "clave_super_secreta"

crear_base_datos()


def login_requerido():
    return "usuario" in session


# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        if verificar_usuario(usuario, password):
            session["usuario"] = usuario
            return redirect(url_for("inicio"))

    return render_template("login.html")


# ---------------- REGISTRO ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        crear_usuario(
            request.form["usuario"],
            request.form["password"]
        )
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
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
        crear_caja(
            int(request.form["rango_min"]),
            int(request.form["rango_max"])
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
            agregar_archivo(numero, nombre)
        elif accion == "modificar":
            modificar_archivo(numero, nombre)
        elif accion == "eliminar":
            eliminar_archivo(numero)

        return redirect(url_for("archivos"))

    conn = sqlite3.connect("archivo.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.numero, a.nombre, c.rango_min, c.rango_max
        FROM archivos a
        JOIN cajas c ON a.caja_id = c.id
        ORDER BY a.numero
    """)

    datos = cursor.fetchall()
    conn.close()

    return render_template("archivos.html", archivos=datos)


if __name__ == "__main__":
    app.run(debug=True)
