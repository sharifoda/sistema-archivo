print(">>> APP.PY CORRECTO CARGADO <<<")
import os
from werkzeug.utils import secure_filename
from flask import send_file, send_from_directory
from openpyxl import Workbook, load_workbook
from io import BytesIO
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
from auth import crear_usuario, verificar_usuario, obtener_usuario_y_rol, usuario_existe
from grupos import (
    crear_grupo,
    agregar_usuario_a_grupo,
    obtener_grupos_usuario,
    obtener_todos_grupos,
    obtener_miembros_grupo,
    buscar_usuario_por_nombre,
    usuario_puede_eliminar,
    quitar_usuario_de_grupo,
    eliminar_grupo_personal,
    archivar_grupo
)
from logs import registrar_log
from historial import registrar_movimiento
from werkzeug.security import generate_password_hash
from db import get_db
from io import BytesIO
from datetime import datetime
from collections import defaultdict
from openpyxl.styles import Font
from flask import flash

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "pdfs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB

app.secret_key = "clave_super_secreta"

def es_pdf(file):
    if not file:
        return False
    filename = (file.filename or "").lower()
    return filename.endswith(".pdf")

def guardar_pdf(file, numero_documento, grupo_id):
    """
    Guarda el pdf y retorna el path relativo (para guardar en DB).
    """
    filename = secure_filename(file.filename)
    # Guardar con nombre controlado (evita duplicados raros)
    final_name = f"doc_{grupo_id}_{numero_documento}.pdf"
    abs_path = os.path.join(app.config["UPLOAD_FOLDER"], final_name)
    file.save(abs_path)
    # Guardamos en DB un path relativo simple
    return final_name


def login_requerido():
    return "usuario" in session


def admin_requerido():
    return session.get("rol") == "admin"


def obtener_grupo_id():
    return session.get("grupo_id")


def supervisor_requerido():
    return session.get("rol") in ("admin", "supervisor")


def usuario_requerido():
    return session.get("rol") not in ("admin", "supervisor")


def es_archivador_grupo(grupo_id):
    if not grupo_id:
        return False
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nombre FROM grupos WHERE id = %s", (grupo_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row and row[0] == "Archivador"


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

            grupos = obtener_grupos_usuario(session["usuario_id"])
            if grupos:
                session["grupo_id"] = grupos[0][0]
            else:
                grupo_id = crear_grupo(f"Personal - {usuario}", creado_por=session["usuario_id"])
                agregar_usuario_a_grupo(
                    session["usuario_id"],
                    grupo_id,
                    puede_eliminar=True,
                    puede_editar=True
                )
                session["grupo_id"] = grupo_id

            # LOG: LOGIN
            registrar_log(
                session.get("usuario_id"),
                "LOGIN",
                request.remote_addr,
                session.get("grupo_id")
            )

            return redirect(url_for("inicio"))
        if usuario_existe(usuario):
            flash("Contrasena incorrecta.", "error")
        else:
            flash("Usuario no registrado.", "error")

    return render_template("login.html")


# ---------------- REGISTRO ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if not login_requerido() or not admin_requerido():
        return "Acceso denegado", 403

    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        # Intento de crear usuario (debe devolver True/False si usas el auth.py mejorado)
        user_id = crear_usuario(usuario, password, rol="cliente")

        # Si tu crear_usuario no devuelve nada (None), lo tratamos como éxito
        if user_id is False:
            return render_template("register.html", error="El usuario ya existe")

        grupo_id = crear_grupo(f"Personal - {usuario}", creado_por=user_id)
        agregar_usuario_a_grupo(user_id, grupo_id, puede_eliminar=True, puede_editar=True)

        return redirect(url_for("login"))

    # GET
    return render_template("register.html")



# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    # LOG: LOGOUT (antes de borrar sesión)
    registrar_log(
        session.get("usuario_id"),
        "LOGOUT",
        request.remote_addr,
        session.get("grupo_id")
    )

    session.clear()
    return redirect(url_for("login"))


# ---------------- INICIO (BIENVENIDA) ----------------
@app.route("/inicio")
def inicio():
    if not login_requerido():
        return redirect(url_for("login"))

    grupo_id = obtener_grupo_id()
    if not grupo_id:
        return redirect(url_for("grupos"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM archivos WHERE grupo_id = %s",
        (grupo_id,)
    )
    total_archivos = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM cajas WHERE grupo_id = %s AND is_pendiente = FALSE",
        (grupo_id,)
    )
    total_cajas = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        "inicio.html",
        total_archivos=total_archivos,
        total_cajas=total_cajas
    )


# ---------------- GRUPOS ----------------
@app.route("/grupos", methods=["GET", "POST"])
def grupos():
    if not login_requerido():
        return redirect(url_for("login"))

    if admin_requerido():
        if request.method == "POST":
            accion = request.form.get("accion")

            if accion == "crear_grupo":
                nombre = request.form.get("nombre", "").strip()
                if nombre:
                    crear_grupo(nombre, creado_por=session.get("usuario_id"))
                    flash("Grupo creado correctamente.", "success")
                else:
                    flash("Debes ingresar un nombre de grupo.", "error")

            if accion == "agregar_usuario":
                grupo_id = int(request.form.get("grupo_id"))
                usuario = request.form.get("usuario", "").strip()
                puede_eliminar = request.form.get("puede_eliminar") == "1"
                puede_editar = request.form.get("puede_editar") == "1"

                user_row = buscar_usuario_por_nombre(usuario)
                if not user_row:
                    flash("El usuario no existe.", "error")
                else:
                    agregar_usuario_a_grupo(user_row[0], grupo_id, puede_eliminar, puede_editar)
                    eliminar_grupo_personal(user_row[0], grupo_id)
                    flash("Usuario agregado al grupo.", "success")

            if accion == "actualizar_permiso":
                grupo_id = int(request.form.get("grupo_id"))
                usuario_id = int(request.form.get("usuario_id"))
                puede_eliminar = request.form.get("puede_eliminar") == "1"
                puede_editar = request.form.get("puede_editar") == "1"

                agregar_usuario_a_grupo(usuario_id, grupo_id, puede_eliminar, puede_editar)
                flash("Permisos actualizados.", "success")

            if accion == "quitar_usuario":
                grupo_id = int(request.form.get("grupo_id"))
                usuario_id = int(request.form.get("usuario_id"))
                quitar_usuario_de_grupo(usuario_id, grupo_id)
                flash("Usuario removido del grupo.", "success")

            if accion == "eliminar_grupo":
                grupo_id = int(request.form.get("grupo_id"))
                ok = archivar_grupo(grupo_id, session.get("usuario_id"))
                if ok:
                    flash("Grupo archivado y eliminado correctamente.", "success")
                else:
                    flash("El grupo no existe.", "error")

            if accion == "crear_usuario":
                usuario = request.form.get("usuario", "").strip()
                password = request.form.get("password", "").strip()
                rol = request.form.get("rol", "cliente").strip()
                if not usuario or not password:
                    flash("Usuario y contrasena son obligatorios.", "error")
                else:
                    user_id = crear_usuario(usuario, password, rol=rol)
                    if user_id is False:
                        flash("El usuario ya existe.", "error")
                    else:
                        grupo_id = crear_grupo(f"Personal - {usuario}", creado_por=user_id)
                        agregar_usuario_a_grupo(user_id, grupo_id, puede_eliminar=True, puede_editar=True)
                        flash("Usuario creado correctamente.", "success")

            if accion == "actualizar_usuario":
                usuario_id = int(request.form.get("usuario_id"))
                nuevo_usuario = request.form.get("usuario", "").strip()
                nuevo_rol = request.form.get("rol", "").strip()
                nueva_password = request.form.get("password", "").strip()
                nuevo_grupo_id = int(request.form.get("grupo_id"))
                return_to = request.form.get("return_to", "")

                conn = get_db()
                cur = conn.cursor()

                try:
                    if nuevo_usuario:
                        cur.execute(
                            "UPDATE usuarios SET usuario = %s WHERE id = %s",
                            (nuevo_usuario, usuario_id)
                        )

                    if nuevo_rol:
                        cur.execute(
                            "UPDATE usuarios SET rol = %s WHERE id = %s",
                            (nuevo_rol, usuario_id)
                        )

                        cur.execute(
                            """
                            UPDATE usuarios_grupos
                            SET puede_eliminar = %s
                            WHERE usuario_id = %s
                            """,
                            ((nuevo_rol in ("admin", "supervisor")), usuario_id)
                        )

                    if nueva_password:
                        hash_pw = generate_password_hash(nueva_password)
                        cur.execute(
                            "UPDATE usuarios SET password = %s WHERE id = %s",
                            (hash_pw, usuario_id)
                        )

                    cur.execute(
                        "SELECT grupo_id FROM usuarios_grupos WHERE usuario_id = %s LIMIT 1",
                        (usuario_id,)
                    )
                    current = cur.fetchone()
                    current_group_id = current[0] if current else None

                    if nuevo_grupo_id == 0:
                        cur.execute(
                            "DELETE FROM usuarios_grupos WHERE usuario_id = %s",
                            (usuario_id,)
                        )
                    elif current_group_id != nuevo_grupo_id:
                        cur.execute(
                            "DELETE FROM usuarios_grupos WHERE usuario_id = %s",
                            (usuario_id,)
                        )
                        agregar_usuario_a_grupo(
                            usuario_id,
                            nuevo_grupo_id,
                            puede_eliminar=(nuevo_rol in ("admin", "supervisor")),
                            puede_editar=True
                        )
                        eliminar_grupo_personal(usuario_id, nuevo_grupo_id)

                    conn.commit()
                    flash("Usuario actualizado correctamente.", "success")
                except Exception as e:
                    conn.rollback()
                    flash(f"Error al actualizar usuario: {e}", "error")
                finally:
                    cur.close()
                    conn.close()
                if return_to == "admin_logs_usuarios":
                    return redirect(url_for("admin_logs", tab="usuarios"))

            if accion == "eliminar_usuario":
                usuario_id = int(request.form.get("usuario_id"))
                return_to = request.form.get("return_to", "")
                if usuario_id == session.get("usuario_id"):
                    flash("No puedes eliminar tu propio usuario.", "error")
                    return redirect(url_for("grupos"))

                conn = get_db()
                cur = conn.cursor()
                try:
                    cur.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    flash(f"Error al eliminar usuario: {e}", "error")
                    cur.close()
                    conn.close()
                    return redirect(url_for("grupos"))
                cur.close()
                conn.close()
                flash("Usuario eliminado correctamente.", "success")
                if return_to == "admin_logs_usuarios":
                    return redirect(url_for("admin_logs", tab="usuarios"))

            return redirect(url_for("grupos"))

        grupos_data = obtener_todos_grupos()
        grupos_info = []
        for g in grupos_data:
            miembros = obtener_miembros_grupo(g[0])
            grupos_info.append((g[0], g[1], miembros))

        return render_template("grupos.html", grupos=grupos_info, es_admin=True)

    if usuario_requerido():
        return redirect(url_for("archivo"))

    grupos_data = obtener_grupos_usuario(session.get("usuario_id"))
    grupos_info = []
    conn = get_db()
    cur = conn.cursor()
    for g in grupos_data:
        cur.execute(
            """
            SELECT
                u.id,
                u.usuario,
                ug.puede_eliminar,
                ug.puede_editar,
                MAX(l.fecha) AS ultima_conexion
            FROM usuarios_grupos ug
            JOIN usuarios u ON u.id = ug.usuario_id
            LEFT JOIN logs l ON l.usuario_id = u.id AND l.accion = 'LOGIN'
            WHERE ug.grupo_id = %s
            GROUP BY u.id, u.usuario, ug.puede_eliminar, ug.puede_editar
            ORDER BY u.usuario
            """,
            (g[0],)
        )
        miembros = cur.fetchall()
        grupos_info.append((g[0], g[1], g[2], g[3], miembros))
    cur.close()
    conn.close()
    empresa_nombre = grupos_info[0][1] if grupos_info else "Empresa"
    return render_template(
        "grupos.html",
        grupos=grupos_info,
        es_admin=False,
        empresa_nombre=empresa_nombre
    )


@app.context_processor
def inject_grupo_actual():
    nombre = None
    grupo_id = session.get("grupo_id")
    if grupo_id:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT nombre FROM grupos WHERE id = %s", (grupo_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        nombre = row[0] if row else None
    return {"grupo_actual": nombre}


@app.route("/grupos/seleccionar/<int:grupo_id>")
def seleccionar_grupo(grupo_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if not admin_requerido():
        grupos_usuario = {g[0] for g in obtener_grupos_usuario(session.get("usuario_id"))}
        if grupo_id not in grupos_usuario:
            return "Acceso denegado", 403

    session["grupo_id"] = grupo_id
    return redirect(url_for("archivo"))


# ---------------- CAJAS ----------------
@app.route("/cajas", methods=["GET", "POST"])
def cajas():
    if not login_requerido():
        return redirect(url_for("login"))

    grupo_id = obtener_grupo_id()
    if not grupo_id:
        return redirect(url_for("grupos"))

    # Asegurar que siempre exista la caja pendiente
    asegurar_caja_sin_asignar(grupo_id)

    if request.method == "POST":
        accion = request.form.get("accion")

        # ======================
        # ELIMINAR CAJA
        # ======================
        if accion == "eliminar":
            caja_id = int(request.form["caja_id"])

            if not admin_requerido():
                flash("Solo el admin puede eliminar cajas.", "error")
                return redirect(url_for("cajas"))

            if not admin_requerido() and not usuario_puede_eliminar(session.get("usuario_id"), grupo_id):
                flash("No tienes permiso para eliminar cajas en este grupo.", "error")
                return redirect(url_for("cajas"))

            eliminar_caja(caja_id, grupo_id, session.get("usuario_id"))

            registrar_log(
                session.get("usuario_id"),
                f"ELIMINAR_CAJA caja_id={caja_id}",
                request.remote_addr,
                grupo_id
            )

            flash("Caja eliminada correctamente.", "success")
            return redirect(url_for("cajas"))

        # ======================
        # MODIFICAR CAJA (modal)
        # ======================
        if accion == "modificar":
            caja_id = int(request.form["caja_id"])
            nuevo_min = int(request.form["rango_min"])
            nuevo_max = int(request.form["rango_max"])

            if not admin_requerido():
                flash("Solo el admin puede modificar cajas.", "error")
                return redirect(url_for("cajas"))

            modificar_caja(caja_id, nuevo_min, nuevo_max, grupo_id, session.get("usuario_id"))

            movidos_fuera = reubicar_archivos_de_caja(caja_id, grupo_id, session.get("usuario_id"))
            movidos_dentro = reubicar_archivos_pendientes_por_nueva_caja(
                caja_id,
                grupo_id,
                session.get("usuario_id")
            )

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
                request.remote_addr,
                grupo_id
            )

            return redirect(url_for("cajas"))

        # ======================
        # CREAR CAJA
        # ======================
        if accion == "crear":
            rmin = int(request.form["rango_min"])
            rmax = int(request.form["rango_max"])

            if not admin_requerido():
                flash("Solo el admin puede crear cajas.", "error")
                return redirect(url_for("cajas"))

            nueva_caja_id = crear_caja(
                rmin,
                rmax,
                grupo_id,
                creado_por=session.get("usuario_id")
            )

            # Reubicar archivos pendientes (Caja 0) si encajan en la nueva caja
            movidos = reubicar_archivos_pendientes_por_nueva_caja(
                nueva_caja_id,
                grupo_id,
                session.get("usuario_id")
            )

            registrar_log(
                session.get("usuario_id"),
                f"CREAR_CAJA caja_id={nueva_caja_id} rango={rmin}-{rmax} movidos_desde_caja0={movidos}",
                request.remote_addr,
                grupo_id
            )

            if movidos > 0:
                flash(f"Caja creada. Se movieron {movidos} archivo(s) desde Caja 0.", "success")
            else:
                flash("Caja creada correctamente.", "success")

            return redirect(url_for("cajas"))

        # Si llega algo raro:
        flash("Acción no válida.", "error")
        return redirect(url_for("cajas"))

    # ======================
    # LISTADO DE CAJAS
    # ======================
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                rango_min,
                rango_max,
                ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE grupo_id = %s AND is_pendiente = FALSE
        )
        SELECT
            c.id AS caja_id,
            COUNT(a.id) AS total_archivos,
            c.rango_min,
            c.rango_max,
            CASE
                WHEN c.is_pendiente THEN 0
                ELSE r.caja_visible
            END AS caja_visible,
            c.is_pendiente
        FROM cajas c
        LEFT JOIN archivos a ON a.caja_id = c.id AND a.grupo_id = %s
        LEFT JOIN ranked r ON r.id = c.id
        WHERE c.grupo_id = %s
        GROUP BY c.id, c.rango_min, c.rango_max, c.is_pendiente, r.caja_visible
        ORDER BY
            CASE WHEN c.is_pendiente THEN 1 ELSE 0 END,
            caja_visible
        """,
        (grupo_id, grupo_id, grupo_id)
    )

    cajas_data = cur.fetchall()
    cur.close()
    conn.close()

    # Ocultar Caja 0 si está vacía
    cajas_filtradas = []
    for c in cajas_data:
        if c[5] and c[1] == 0:
            continue
        cajas_filtradas.append(c)

    return render_template("cajas.html", cajas=cajas_filtradas)



# ---------------- ARCHIVOS ----------------
@app.route("/archivos", methods=["GET", "POST"])
def archivos():
    if not login_requerido():
        return redirect(url_for("login"))

    grupo_id = obtener_grupo_id()
    if not grupo_id:
        return redirect(url_for("grupos"))

    # =========================
    # POST: agregar / modificar fila / eliminar fila
    # =========================
    if request.method == "POST":
        accion = request.form["accion"]


        # ✅ AGREGAR (formulario de arriba)
        if accion == "agregar":
            numero = int(request.form["numero"])
            nombre = request.form.get("nombre", "").strip()
            if not nombre:
                nombre = f"Documento {numero}"

            agregar_archivo(numero, nombre, grupo_id, creado_por=session.get("usuario_id"))

            # Log con info real
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT caja_id, nombre FROM archivos WHERE numero = %s AND grupo_id = %s",
                (numero, grupo_id)
            )
            info = cur.fetchone()
            caja_id = info[0] if info else 0
            nombre_final = info[1] if info else nombre
            cur.close()
            conn.close()

            registrar_log(
                session.get("usuario_id"),
                f"ARCHIVO|tipo=REGISTRO|numero_new={numero}|nombre_new={nombre_final}|caja={caja_id}",
                request.remote_addr,
                grupo_id
            )


            return redirect(url_for("archivos"))

       # ✅ MODIFICAR DESDE FILA (popup)
        if accion == "modificar_fila":
            numero_old = int(request.form["numero_old"])
            numero_new = int(request.form["numero_new"])
            nombre_new = request.form.get("nombre_new", "").strip()

            conn = get_db()
            cur = conn.cursor()

            # Antes:
            cur.execute(
                "SELECT id, caja_id, numero, nombre, pdf_path FROM archivos WHERE numero = %s AND grupo_id = %s",
                (numero_old, grupo_id)
            )
            antes = cur.fetchone()
            archivo_id = antes[0] if antes else None
            caja_id = antes[1] if antes else 0
            numero_viejo = antes[2] if antes else numero_old
            nombre_viejo = antes[3] if antes else ""
            pdf_old = antes[4] if antes else None

            # ... haces el UPDATE ...

            registrar_log(
                session.get("usuario_id"),
                f"ARCHIVO|tipo=MODIFICACION|numero_old={numero_viejo}|numero_new={numero_new}|nombre_old={nombre_viejo}|nombre_new={nombre_new}|caja={caja_id}",
                request.remote_addr,
                grupo_id
            )

            cur.execute("""
                UPDATE archivos
                SET numero = %s, nombre = %s
                WHERE numero = %s AND grupo_id = %s
            """, (numero_new, nombre_new, numero_old, grupo_id))

            conn.commit()
            cur.close()
            conn.close()

            registrar_log(
                session.get("usuario_id"),
                f"MODIFICAR_ARCHIVO | caja_id={caja_id} | numero={numero_new} | nombre={nombre_new}",
                request.remote_addr,
                grupo_id
            )

            if archivo_id:
                registrar_movimiento(
                    session.get("usuario_id"),
                    grupo_id,
                    entidad="archivo",
                    entidad_id=archivo_id,
                    accion="MODIFICAR_ARCHIVO",
                    datos_antes={
                        "numero": numero_viejo,
                        "nombre": nombre_viejo,
                        "caja_id": caja_id,
                        "pdf_path": pdf_old,
                    },
                    datos_despues={
                        "numero": numero_new,
                        "nombre": nombre_new,
                        "caja_id": caja_id,
                        "pdf_path": pdf_old,
                    },
                )

            return redirect(url_for("archivos"))


        # ✅ ELIMINAR DESDE FILA
        if accion == "eliminar_fila":
            numero = int(request.form["numero"])

            if not supervisor_requerido() and not usuario_puede_eliminar(session.get("usuario_id"), grupo_id):
                flash("No tienes permiso para eliminar archivos en este grupo.", "error")
                return redirect(url_for("archivos"))

            conn = get_db()
            cur = conn.cursor()

            # guardar info antes de borrar
            cur.execute(
                "SELECT caja_id, nombre FROM archivos WHERE numero = %s AND grupo_id = %s",
                (numero, grupo_id)
            )
            antes = cur.fetchone()
            caja_id = antes[0] if antes else 0
            nombre_final = antes[1] if antes else ""

            cur.close()
            conn.close()

            eliminar_archivo(numero, grupo_id, session.get("usuario_id"))

            registrar_log(
                session.get("usuario_id"),
                f"ARCHIVO|tipo=ELIMINACION|numero_old={numero}|nombre_old={nombre_final}|caja={caja_id}",
                request.remote_addr,
                grupo_id
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
    cur.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE grupo_id = %s AND is_pendiente = FALSE
        )
        SELECT
            CASE WHEN c.is_pendiente THEN 0 ELSE r.caja_visible END AS caja,
            a.numero AS documento,
            a.nombre AS nombre
        FROM archivos a
        JOIN cajas c ON a.caja_id = c.id
        LEFT JOIN ranked r ON r.id = c.id
        WHERE a.grupo_id = %s
        ORDER BY caja, a.numero
        """,
        (grupo_id, grupo_id)
    )

    datos = cur.fetchall()

    # Buscador
    resultado = None
    buscar = request.args.get("buscar", "").strip()
    if buscar:
        try:
            doc = int(buscar)
            cur.execute("""
                WITH ranked AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
                FROM cajas
                WHERE grupo_id = %s AND is_pendiente = FALSE
                )
                SELECT
                c.id AS caja_id,
                CASE WHEN c.is_pendiente THEN 0 ELSE r.caja_visible END AS caja_num,
                a.numero AS documento,
                a.nombre AS nombre,
                a.pdf_path
                FROM archivos a
                JOIN cajas c ON c.id = a.caja_id
                LEFT JOIN ranked r ON r.id = c.id
                WHERE a.numero = %s AND a.grupo_id = %s
                LIMIT 1;
            """, (grupo_id, doc, grupo_id))

            resultado = cur.fetchone()
        except ValueError:
            cur.execute("""
                WITH ranked AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
                FROM cajas
                WHERE grupo_id = %s AND is_pendiente = FALSE
                )
                SELECT
                c.id AS caja_id,
                CASE WHEN c.is_pendiente THEN 0 ELSE r.caja_visible END AS caja_num,
                a.numero AS documento,
                a.nombre AS nombre,
                a.pdf_path
                FROM archivos a
                JOIN cajas c ON c.id = a.caja_id
                LEFT JOIN ranked r ON r.id = c.id
                WHERE a.nombre ILIKE %s AND a.grupo_id = %s
                ORDER BY a.numero
                LIMIT 1;
            """, (grupo_id, f"%{buscar}%", grupo_id))
            resultado = cur.fetchone()
            if not resultado:
                resultado = ("no",)

    # Modo edición (qué documento está en edición)
    edit_num = request.args.get("edit", "").strip()
    edit_num = int(edit_num) if edit_num.isdigit() else None

    # Últimos movimientos (10)
    cur.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE grupo_id = %s AND is_pendiente = FALSE
        ),
        base AS (
            SELECT
                l.fecha,
                l.accion,
                NULLIF(substring(l.accion from 'caja=([0-9]+)'), '')::int AS caja_id,
                NULLIF(substring(l.accion from 'numero_old=([0-9]+)'), '')::bigint AS numero_old,
                NULLIF(substring(l.accion from 'numero_new=([0-9]+)'), '')::bigint AS numero_new,
                substring(l.accion from 'nombre_old=([^|]+)') AS nombre_old,
                substring(l.accion from 'nombre_new=([^|]+)') AS nombre_new,
                substring(l.accion from 'tipo=([^|]+)') AS tipo_raw
            FROM logs l
            WHERE l.accion LIKE 'ARCHIVO|tipo=%'
              AND l.grupo_id = %s
            ORDER BY l.fecha DESC
            LIMIT 10
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY b.fecha DESC) AS movimiento,

            CASE
                WHEN c.is_pendiente THEN 0
                ELSE r.caja_visible
            END AS caja,

            COALESCE(b.numero_new, b.numero_old, a.numero) AS documento,
            COALESCE(b.nombre_new, b.nombre_old, a.nombre, '') AS nombre,

            CASE
                WHEN b.tipo_raw = 'REGISTRO' THEN 'Registro'
                WHEN b.tipo_raw = 'MODIFICACION' THEN 'Modificación'
                WHEN b.tipo_raw = 'ELIMINACION' THEN 'Eliminación'
                ELSE 'Otro'
            END AS tipo,

            CASE
                WHEN b.tipo_raw = 'REGISTRO' THEN
                    'Se registró el documento y el nombre.'
                WHEN b.tipo_raw = 'ELIMINACION' THEN
                    'Se eliminó el documento y su nombre.'
                WHEN b.tipo_raw = 'MODIFICACION' THEN
                    TRIM(
                        BOTH ', ' FROM
                        (CASE
                            WHEN b.numero_old IS NOT NULL AND b.numero_new IS NOT NULL AND b.numero_old <> b.numero_new
                            THEN 'Documento: ' || b.numero_old || ' → ' || b.numero_new || ', '
                            ELSE ''
                        END)
                        ||
                        (CASE
                            WHEN COALESCE(b.nombre_old,'') <> COALESCE(b.nombre_new,'')
                            THEN 'Nombre: ' || COALESCE(b.nombre_old,'') || ' → ' || COALESCE(b.nombre_new,'')
                            ELSE ''
                        END)
                    )
                ELSE
                    'Sin detalle'
            END AS detalle
        FROM base b
        LEFT JOIN archivos a ON a.numero = COALESCE(b.numero_new, b.numero_old)
                           AND a.grupo_id = %s
        LEFT JOIN cajas c ON c.id = COALESCE(b.caja_id, a.caja_id)
                         AND c.grupo_id = %s
        LEFT JOIN ranked r ON r.id = c.id
        ORDER BY movimiento
    """, (grupo_id, grupo_id, grupo_id))
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

# ---------------- ARCHIVO ----------------

@app.route("/archivo", methods=["GET", "POST"])
def archivo():
    if not login_requerido():
        return redirect(url_for("login"))

    grupo_id = obtener_grupo_id()
    if not grupo_id:
        return redirect(url_for("grupos"))

    asegurar_caja_sin_asignar(grupo_id)

    archivador_mode = admin_requerido() and es_archivador_grupo(grupo_id)
    view_mode = request.args.get("view", "").strip()

    if request.method == "GET" and archivador_mode and view_mode == "especial":
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, rango_min, rango_max, is_pendiente, grupo_origen_id
            FROM cajas
            WHERE grupo_id = %s
            ORDER BY is_pendiente, rango_min, id
            """,
            (grupo_id,)
        )
        cajas_rows = cur.fetchall()

        cur.execute(
            """
            SELECT id, numero, nombre, caja_id, pdf_path, grupo_origen_id
            FROM archivos
            WHERE grupo_id = %s
            ORDER BY caja_id, numero
            """,
            (grupo_id,)
        )
        archivos_rows = cur.fetchall()

        cur.execute(
            """
            SELECT id, nombre
            FROM grupos
            WHERE archivado = FALSE AND nombre <> 'Archivador'
            ORDER BY nombre
            """
        )
        grupos_destino = cur.fetchall()

        cur.execute("SELECT id, nombre FROM grupos")
        grupos_nombres = {r[0]: r[1] for r in cur.fetchall()}

        cur.close()
        conn.close()

        cajas_map = {}
        for c in cajas_rows:
            cajas_map[c[0]] = {
                "id": c[0],
                "rango_min": c[1],
                "rango_max": c[2],
                "is_pendiente": c[3],
                "grupo_origen_id": c[4],
                "grupo_origen_nombre": grupos_nombres.get(c[4]),
                "archivos": []
            }

        for a in archivos_rows:
            caja_id = a[3]
            if caja_id not in cajas_map:
                cajas_map[caja_id] = {
                    "id": caja_id,
                    "rango_min": None,
                    "rango_max": None,
                    "is_pendiente": False,
                    "grupo_origen_id": None,
                    "archivos": []
                }
            cajas_map[caja_id]["archivos"].append({
                "id": a[0],
                "numero": a[1],
                "nombre": a[2],
                "pdf_path": a[4],
                "grupo_origen_id": a[5],
                "grupo_origen_nombre": grupos_nombres.get(a[5]),
            })

        cajas_list = []
        for c in cajas_map.values():
            if c["is_pendiente"] and not c["archivos"]:
                continue
            cajas_list.append(c)

        return render_template(
            "archivo_archivador.html",
            cajas=cajas_list,
            grupos_destino=grupos_destino
        )

    # =========================================================
    # POST: acciones del dashboard
    # =========================================================
    accion = request.form.get("accion") if request.method == "POST" else None

    if request.method == "POST":
        # ---------- Importar Excel ----------
        if accion == "importar_excel":
            if not admin_requerido():
                flash("Solo el admin puede importar Excel.", "error")
                return redirect(url_for("archivo"))

            excel_file = request.files.get("excel")
            if not excel_file or not excel_file.filename:
                flash("Debes seleccionar un archivo Excel.", "error")
                return redirect(url_for("archivo"))

            try:
                wb = load_workbook(excel_file, data_only=True)
            except Exception as e:
                flash(f"Archivo Excel invalido: {e}", "error")
                return redirect(url_for("archivo"))

            ws = wb.active
            max_row = ws.max_row or 1
            max_col = ws.max_column or 1

            columnas = []
            for col in range(1, max_col + 1):
                header = ws.cell(row=1, column=col).value
                if header is None or str(header).strip() == "":
                    continue
                numeros = []
                for row in range(2, max_row + 1):
                    cell_val = ws.cell(row=row, column=col).value
                    if cell_val is None:
                        continue
                    if isinstance(cell_val, (int, float)):
                        try:
                            num = int(cell_val)
                        except Exception:
                            continue
                    else:
                        s = str(cell_val).strip()
                        if not s.isdigit():
                            continue
                        num = int(s)
                    numeros.append(num)
                columnas.append((col, str(header).strip(), numeros))

            if not columnas:
                flash("No se encontraron cajas en la primera fila del Excel.", "error")
                return redirect(url_for("archivo"))

            total_cajas = 0
            total_docs = 0
            insertados = 0
            duplicados = 0
            vacias = 0

            conn = get_db()
            cur = conn.cursor()
            try:
                for _, _, nums in columnas:
                    nums = sorted(set(nums))
                    if not nums:
                        vacias += 1
                        continue
                    rmin = min(nums)
                    rmax = max(nums)
                    caja_id = crear_caja(rmin, rmax, grupo_id, creado_por=session.get("usuario_id"))
                    total_cajas += 1
                    total_docs += len(nums)

                    for numero in nums:
                        nombre = f"Documento {numero}"
                        cur.execute(
                            """
                            INSERT INTO archivos (numero, nombre, caja_id, creado_por, grupo_id)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (grupo_id, numero) DO NOTHING
                            RETURNING id
                            """,
                            (numero, nombre, caja_id, session.get("usuario_id"), grupo_id)
                        )
                        row = cur.fetchone()
                        if row:
                            insertados += 1
                            registrar_movimiento(
                                session.get("usuario_id"),
                                grupo_id,
                                entidad="archivo",
                                entidad_id=row[0],
                                accion="CREAR_ARCHIVO",
                                datos_despues={
                                    "id": row[0],
                                    "numero": numero,
                                    "nombre": nombre,
                                    "caja_id": caja_id
                                },
                            )
                        else:
                            duplicados += 1

                conn.commit()
            except Exception as e:
                conn.rollback()
                cur.close()
                conn.close()
                flash(f"Error al importar Excel: {e}", "error")
                return redirect(url_for("archivo"))

            cur.close()
            conn.close()

            msg = f"Importacion lista. Cajas: {total_cajas}, Documentos: {insertados}"
            if duplicados:
                msg += f", Duplicados: {duplicados}"
            if vacias:
                msg += f", Cajas vacias: {vacias}"
            flash(msg + ".", "success")
            return redirect(url_for("archivo"))

        # ---------- Crear Caja ----------
        if accion == "crear_caja":
            rmin = int(request.form["rango_min"])
            rmax = int(request.form["rango_max"])

            if not admin_requerido():
                flash("Solo el admin puede crear cajas.", "error")
                return redirect(url_for("archivo"))

            nueva_caja_id = crear_caja(rmin, rmax, grupo_id, creado_por=session.get("usuario_id"))
            movidos = reubicar_archivos_pendientes_por_nueva_caja(
                nueva_caja_id,
                grupo_id,
                session.get("usuario_id")
            )

            registrar_log(
                session.get("usuario_id"),
                f"CREAR_CAJA caja_id={nueva_caja_id} rango={rmin}-{rmax} movidos_desde_caja0={movidos}",
                request.remote_addr,
                grupo_id
            )

            flash("Caja creada correctamente.", "success")
            return redirect(url_for("archivo"))

        # ---------- Agregar Documento ----------
        elif accion == "agregar_documento":
            numero = int(request.form["numero"])
            nombre = request.form.get("nombre", "").strip()

            conn = get_db()
            cur = conn.cursor()

            # 1) Determinar caja destino por rangos
            cur.execute("""
                SELECT id
                FROM cajas
                WHERE grupo_id = %s
                  AND is_pendiente = FALSE
                  AND %s BETWEEN rango_min AND rango_max
                ORDER BY rango_min, id
                LIMIT 1
            """, (grupo_id, numero))
            caja_dest = cur.fetchone()
            caja_id = caja_dest[0] if caja_dest else asegurar_caja_sin_asignar(grupo_id)  # ✅ si no cae en ninguna caja → 0

            # 2) Insertar archivo YA con caja_id
            # (si tu tabla tiene otras columnas obligatorias, aquí se ajusta, pero esto es lo normal)
            cur.execute("""
                INSERT INTO archivos (caja_id, numero, nombre, pdf_path, grupo_id, creado_por)
                VALUES (%s, %s, %s, NULL, %s, %s)
                RETURNING id
            """, (caja_id, numero, nombre, grupo_id, session.get("usuario_id")))
            archivo_id = cur.fetchone()[0]

            # 3) PDF opcional: guardar y actualizar pdf_path
            pdf_name = None
            file = request.files.get("pdf")
            if file and file.filename:
                if not es_pdf(file):
                    cur.close()
                    conn.close()
                    flash("El archivo debe ser PDF.", "error")
                    return redirect(url_for("archivo"))

                pdf_name = guardar_pdf(file, numero, grupo_id)
                cur.execute(
                    "UPDATE archivos SET pdf_path = %s WHERE numero = %s AND grupo_id = %s",
                    (pdf_name, numero, grupo_id)
                )

            conn.commit()
            cur.close()
            conn.close()

            registrar_log(
                session.get("usuario_id"),
                f"ARCHIVO|tipo=CREACION|numero={numero}|nombre={nombre}|caja={caja_id}",
                request.remote_addr,
                grupo_id
            )

            registrar_movimiento(
                session.get("usuario_id"),
                grupo_id,
                entidad="archivo",
                entidad_id=archivo_id,
                accion="CREAR_ARCHIVO",
                datos_despues={
                    "id": archivo_id,
                    "numero": numero,
                    "nombre": nombre,
                    "caja_id": caja_id,
                    "pdf_path": pdf_name,
                },
            )

            flash("Documento agregado correctamente.", "success")
            return redirect(url_for("archivo"))

        # ---------- Eliminar Archivo (desde modal de búsqueda) ----------
        elif accion == "eliminar_archivo_modal":
            numero = int(request.form["numero"])

            if not supervisor_requerido() and not usuario_puede_eliminar(session.get("usuario_id"), grupo_id):
                flash("No tienes permiso para eliminar archivos en este grupo.", "error")
                return redirect(url_for("archivo"))

            conn = get_db()
            cur = conn.cursor()

            # datos antes de borrar para log + pdf_path para borrar del disco
            cur.execute(
                "SELECT id, caja_id, numero, nombre, pdf_path FROM archivos WHERE numero = %s AND grupo_id = %s",
                (numero, grupo_id)
            )
            antes = cur.fetchone()

            if antes:
                archivo_id, caja_old, numero_old, nombre_old, pdf_old = antes
                registrar_movimiento(
                    session.get("usuario_id"),
                    grupo_id,
                    entidad="archivo",
                    entidad_id=archivo_id,
                    accion="ELIMINAR_ARCHIVO",
                    datos_antes={
                        "id": archivo_id,
                        "numero": numero_old,
                        "nombre": nombre_old,
                        "caja_id": caja_old,
                        "pdf_path": pdf_old,
                    },
                )

            cur.execute("DELETE FROM archivos WHERE numero = %s AND grupo_id = %s", (numero, grupo_id))
            conn.commit()
            cur.close()
            conn.close()

            # borrar PDF del disco si existía
            if antes:

                if pdf_old:
                    try:
                        path = pdf_old
                        if not os.path.isabs(path):
                            path = os.path.join(app.root_path, path)
                        if os.path.exists(path):
                            os.remove(path)
                    except Exception as e:
                        print("Error eliminando PDF:", e)

                registrar_log(
                    session.get("usuario_id"),
                    f"ARCHIVO|tipo=ELIMINACION|numero_old={numero_old}|nombre_old={nombre_old}|caja={caja_old}",
                    request.remote_addr,
                    grupo_id
                )

            flash("Archivo eliminado correctamente.", "success")
            return redirect(url_for("archivo"))

        # ---------- Modificar Archivo (desde modal de búsqueda) ----------
        elif accion == "modificar_archivo_modal":
            numero_old = int(request.form["numero_old"])
            numero_new = int(request.form["numero_new"])
            nombre_new = request.form.get("nombre_new", "").strip()

            # checkbox para eliminar PDF actual
            remove_pdf = request.form.get("remove_pdf") == "1"

            conn = get_db()
            cur = conn.cursor()

            cur.execute(
                "SELECT id, caja_id, numero, nombre, pdf_path FROM archivos WHERE numero = %s AND grupo_id = %s",
                (numero_old, grupo_id)
            )
            antes = cur.fetchone()

            if not antes:
                cur.close()
                conn.close()
                flash("No se encontró el archivo a modificar.", "error")
                return redirect(url_for("archivo"))

            archivo_id, caja_old, numero_viejo, nombre_viejo, pdf_old = antes

            # Caja destino según rangos del numero_new
            cur.execute("""
                SELECT id
                FROM cajas
                WHERE grupo_id = %s
                  AND is_pendiente = FALSE
                  AND %s BETWEEN rango_min AND rango_max
                ORDER BY rango_min, id
                LIMIT 1
            """, (grupo_id, numero_new))
            caja_dest = cur.fetchone()
            caja_dest_id = caja_dest[0] if caja_dest else asegurar_caja_sin_asignar(grupo_id)

            pdf_name = pdf_old

            # 1) eliminar PDF actual si se pidió
            if remove_pdf and pdf_old:
                try:
                    path = pdf_old
                    if not os.path.isabs(path):
                        path = os.path.join(app.root_path, path)
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    print("Error eliminando PDF:", e)

                pdf_name = None  # queda NULL en DB

            # 2) subir PDF nuevo (reemplazo)
            file = request.files.get("pdf")
            if file and file.filename:
                if not es_pdf(file):
                    cur.close()
                    conn.close()
                    flash("El archivo debe ser PDF.", "error")
                    return redirect(url_for("archivo"))

                # si había anterior y no se eliminó arriba, lo borramos
                if pdf_old and not remove_pdf:
                    try:
                        old_path = pdf_old
                        if not os.path.isabs(old_path):
                            old_path = os.path.join(app.root_path, old_path)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception as e:
                        print("Error eliminando PDF anterior:", e)

                pdf_name = guardar_pdf(file, numero_new, grupo_id)

            # 3) update final
            cur.execute("""
                UPDATE archivos
                SET numero = %s, nombre = %s, caja_id = %s, pdf_path = %s
                WHERE numero = %s AND grupo_id = %s
            """, (numero_new, nombre_new, caja_dest_id, pdf_name, numero_old, grupo_id))

            conn.commit()
            cur.close()
            conn.close()

            registrar_log(
                session.get("usuario_id"),
                f"ARCHIVO|tipo=MODIFICACION|numero_old={numero_viejo}|numero_new={numero_new}|"
                f"nombre_old={nombre_viejo}|nombre_new={nombre_new}|caja={caja_dest_id}|"
                f"pdf_eliminado={1 if (remove_pdf and pdf_old) else 0}|pdf_nuevo={1 if (file and file.filename) else 0}",
                request.remote_addr,
                grupo_id
            )

            registrar_movimiento(
                session.get("usuario_id"),
                grupo_id,
                entidad="archivo",
                entidad_id=archivo_id,
                accion="MODIFICAR_ARCHIVO",
                datos_antes={
                    "numero": numero_viejo,
                    "nombre": nombre_viejo,
                    "caja_id": caja_old,
                    "pdf_path": pdf_old,
                },
                datos_despues={
                    "numero": numero_new,
                    "nombre": nombre_new,
                    "caja_id": caja_dest_id,
                    "pdf_path": pdf_name,
                },
            )

            flash("Archivo modificado correctamente.", "success")
            return redirect(url_for("archivo"))

        # Acción desconocida
        else:
            flash("Acción no reconocida.", "error")
            return redirect(url_for("archivo"))

    # =========================================================
    # GET: buscador + listado de cajas
    # =========================================================
    resultado = None
    buscar_raw = request.args.get("buscar", "").strip()

    if buscar_raw:
        conn = get_db()
        cur = conn.cursor()
        try:
            doc = int(buscar_raw)

            cur.execute("""
                WITH ranked AS (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
                    FROM cajas
                    WHERE grupo_id = %s AND is_pendiente = FALSE
                )
                SELECT
                    c.id AS caja_id,
                    CASE WHEN c.is_pendiente THEN 0 ELSE r.caja_visible END AS caja_num,
                    a.numero AS documento,
                    a.nombre AS nombre,
                    a.pdf_path
                FROM archivos a
                JOIN cajas c ON c.id = a.caja_id
                LEFT JOIN ranked r ON r.id = c.id
                WHERE a.numero = %s AND a.grupo_id = %s
                LIMIT 1
            """, (grupo_id, doc, grupo_id))

            row = cur.fetchone()
            if row:
                resultado = row
            else:
                resultado = ("no",)

        except ValueError:
            cur.execute("""
                WITH ranked AS (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
                    FROM cajas
                    WHERE grupo_id = %s AND is_pendiente = FALSE
                )
                SELECT
                    c.id AS caja_id,
                    CASE WHEN c.is_pendiente THEN 0 ELSE r.caja_visible END AS caja_num,
                    a.numero AS documento,
                    a.nombre AS nombre,
                    a.pdf_path
                FROM archivos a
                JOIN cajas c ON c.id = a.caja_id
                LEFT JOIN ranked r ON r.id = c.id
                WHERE a.nombre ILIKE %s AND a.grupo_id = %s
                ORDER BY a.numero
                LIMIT 1
            """, (grupo_id, f"%{buscar_raw}%", grupo_id))
            row = cur.fetchone()
            if row:
                resultado = row
            else:
                resultado = ("no",)
        finally:
            cur.close()
            conn.close()

    # listado de cajas (como ya lo tienes)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE grupo_id = %s AND is_pendiente = FALSE
        ),
        conteo AS (
            SELECT caja_id, COUNT(*) AS total_archivos
            FROM archivos
            WHERE grupo_id = %s
            GROUP BY caja_id
        )
        SELECT
            c.id,
            CASE
            WHEN c.is_pendiente THEN 0
            ELSE r.caja_visible
            END AS caja_num,
            c.rango_min,
            c.rango_max,
            COALESCE(ct.total_archivos, 0) AS total_archivos,
            c.is_pendiente
        FROM cajas c
        LEFT JOIN conteo ct ON ct.caja_id = c.id
        LEFT JOIN ranked r ON r.id = c.id
        WHERE c.grupo_id = %s AND (c.is_pendiente = FALSE OR COALESCE(ct.total_archivos, 0) > 0)
        ORDER BY CASE WHEN c.is_pendiente THEN 1 ELSE 0 END, c.rango_min, c.id
    """, (grupo_id, grupo_id, grupo_id))

    cajas = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        "archivo_dashboard.html",
        cajas=cajas,
        resultado=resultado,
        archivador_mode=archivador_mode
    )

# ---------------- archivo_caja ----------------

@app.route("/archivo/caja/<int:caja_id>", methods=["GET", "POST"])
def archivo_caja(caja_id):
    if not login_requerido():
        return redirect(url_for("login"))

    grupo_id = obtener_grupo_id()
    if not grupo_id:
        return redirect(url_for("grupos"))

    asegurar_caja_sin_asignar(grupo_id)

    # ======================
    # POST: Acciones en esta caja
    # ======================
    if request.method == "POST":
        accion = request.form.get("accion")

        # ---------- MODIFICAR CAJA ----------
        if accion == "modificar_caja":
            nuevo_min = int(request.form["rango_min"])
            nuevo_max = int(request.form["rango_max"])

            if not admin_requerido():
                flash("Solo el admin puede modificar cajas.", "error")
                return redirect(url_for("archivo_caja", caja_id=caja_id))

            modificar_caja(caja_id, nuevo_min, nuevo_max, grupo_id, session.get("usuario_id"))

            # Reubicar archivos según nuevo rango
            movidos_fuera = reubicar_archivos_de_caja(caja_id, grupo_id, session.get("usuario_id"))
            movidos_dentro = reubicar_archivos_pendientes_por_nueva_caja(
                caja_id,
                grupo_id,
                session.get("usuario_id")
            )
            total = movidos_fuera + movidos_dentro

            registrar_log(
                session.get("usuario_id"),
                f"MODIFICAR_CAJA caja_id={caja_id} rango={nuevo_min}-{nuevo_max} reasignados={total}",
                request.remote_addr,
                grupo_id
            )

            if total > 0:
                flash(f"Se reasignaron automáticamente {total} archivo(s) según el nuevo rango.", "success")
            else:
                flash("El rango se actualizó. No fue necesario reasignar archivos.", "info")

            return redirect(url_for("archivo_caja", caja_id=caja_id))

        # ---------- ELIMINAR CAJA ----------
        if accion == "eliminar_caja":
            if not admin_requerido():
                flash("Solo el admin puede eliminar cajas.", "error")
                return redirect(url_for("archivo_caja", caja_id=caja_id))

            if not admin_requerido() and not usuario_puede_eliminar(session.get("usuario_id"), grupo_id):
                flash("No tienes permiso para eliminar cajas en este grupo.", "error")
                return redirect(url_for("archivo_caja", caja_id=caja_id))

            eliminar_caja(caja_id, grupo_id, session.get("usuario_id"))

            registrar_log(
                session.get("usuario_id"),
                f"ELIMINAR_CAJA caja_id={caja_id}",
                request.remote_addr,
                grupo_id
            )

            flash("Caja eliminada correctamente.", "success")
            return redirect(url_for("archivo"))

        # ---------- ELIMINAR ARCHIVO ----------
        if accion == "eliminar_archivo_fila":
            numero = int(request.form["numero"])

            if not supervisor_requerido() and not usuario_puede_eliminar(session.get("usuario_id"), grupo_id):
                flash("No tienes permiso para eliminar archivos en este grupo.", "error")
                return redirect(url_for("archivo_caja", caja_id=caja_id))

            conn = get_db()
            cur = conn.cursor()

            # obtener datos antes de borrar (para log)
            cur.execute(
                "SELECT id, caja_id, numero, nombre, pdf_path FROM archivos WHERE numero = %s AND grupo_id = %s",
                (numero, grupo_id)
            )
            antes = cur.fetchone()

            if antes:
                archivo_id, caja_old, numero_old, nombre_old, pdf_old = antes
                registrar_movimiento(
                    session.get("usuario_id"),
                    grupo_id,
                    entidad="archivo",
                    entidad_id=archivo_id,
                    accion="ELIMINAR_ARCHIVO",
                    datos_antes={
                        "id": archivo_id,
                        "numero": numero_old,
                        "nombre": nombre_old,
                        "caja_id": caja_old,
                        "pdf_path": pdf_old,
                    },
                )

            cur.execute("DELETE FROM archivos WHERE numero = %s AND grupo_id = %s", (numero, grupo_id))
            conn.commit()

            cur.close()
            conn.close()

            if antes:
                registrar_log(
                    session.get("usuario_id"),
                    f"ARCHIVO|tipo=ELIMINACION|numero_old={numero_old}|nombre_old={nombre_old}|caja={caja_old}",
                    request.remote_addr,
                    grupo_id
                )

            flash("Archivo eliminado correctamente.", "success")
            return redirect(url_for("archivo_caja", caja_id=caja_id))

        # ---------- MODIFICAR ARCHIVO (numero y/o nombre) ----------
        if accion == "modificar_archivo_fila":
            import os

            numero_old = int(request.form["numero_old"])
            numero_new = int(request.form["numero_new"])
            nombre_new = request.form.get("nombre_new", "").strip()

            remove_pdf = request.form.get("remove_pdf") == "1"
            file = request.files.get("pdf")

            conn = get_db()
            cur = conn.cursor()

            # Traer estado actual
            cur.execute(
                "SELECT id, caja_id, numero, nombre, pdf_path FROM archivos WHERE numero = %s AND grupo_id = %s",
                (numero_old, grupo_id)
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                flash("No se encontro el archivo a modificar.", "error")
                return redirect(url_for("archivo_caja", caja_id=caja_id))

            archivo_id, caja_old, numero_viejo, nombre_viejo, pdf_old = row

            pdf_name = pdf_old

            # 🗑️ Eliminar PDF actual
            if remove_pdf and pdf_old:
                try:
                    path = pdf_old
                    if not os.path.isabs(path):
                        path = os.path.join(app.root_path, path)
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    print("Error eliminando PDF:", e)

                pdf_name = None

            # 📄 Reemplazar / subir PDF nuevo
            if file and file.filename:
                if not es_pdf(file):
                    cur.close()
                    conn.close()
                    flash("El archivo debe ser PDF.", "error")
                    return redirect(url_for("archivo_caja", caja_id=caja_id))

                # borrar anterior si existía
                if pdf_old and not remove_pdf:
                    try:
                        old_path = pdf_old
                        if not os.path.isabs(old_path):
                            old_path = os.path.join(app.root_path, old_path)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception as e:
                        print("Error eliminando PDF anterior:", e)

                pdf_name = guardar_pdf(file, numero_new, grupo_id)

            # Update final
            cur.execute("""
                UPDATE archivos
                SET numero = %s,
                    nombre = %s,
                    pdf_path = %s
                WHERE numero = %s AND grupo_id = %s
            """, (numero_new, nombre_new, pdf_name, numero_old, grupo_id))

            conn.commit()
            cur.close()
            conn.close()
            
            registrar_movimiento(
                session.get("usuario_id"),
                grupo_id,
                entidad="archivo",
                entidad_id=archivo_id,
                accion="MODIFICAR_ARCHIVO",
                datos_antes={
                    "numero": numero_viejo,
                    "nombre": nombre_viejo,
                    "caja_id": caja_old,
                    "pdf_path": pdf_old,
                },
                datos_despues={
                    "numero": numero_new,
                    "nombre": nombre_new,
                    "caja_id": caja_old,
                    "pdf_path": pdf_name,
                },
            )

            flash("Archivo modificado correctamente.", "success")
            return redirect(url_for("archivo_caja", caja_id=caja_id))

    # ======================
    # GET: Render de la caja + archivos
    # ======================
    highlight_raw = request.args.get("highlight", "").strip()
    highlight_num = int(highlight_raw) if highlight_raw.isdigit() else None

    conn = get_db()
    cur = conn.cursor()

    # info de caja + numero visible
    cur.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE grupo_id = %s AND is_pendiente = FALSE
        )
        SELECT
            c.id,
            CASE WHEN c.is_pendiente THEN 0 ELSE r.caja_visible END AS caja_num,
            c.rango_min,
            c.rango_max
        FROM cajas c
        LEFT JOIN ranked r ON r.id = c.id
        WHERE c.id = %s AND c.grupo_id = %s
    """, (grupo_id, caja_id, grupo_id))
    caja_info = cur.fetchone()

    if not caja_info:
        cur.close()
        conn.close()
        flash("La caja no existe.", "error")
        return redirect(url_for("archivo"))

    # archivos de la caja (incluye pdf_path para habilitar Ver PDF)
    cur.execute("""
        SELECT a.numero, a.nombre, a.pdf_path
        FROM archivos a
        WHERE a.caja_id = %s AND a.grupo_id = %s
        ORDER BY a.numero
    """, (caja_id, grupo_id))
    archivos = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "archivo_caja.html",
        caja=caja_info,
        archivos=archivos,
        highlight_num=highlight_num
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
        SELECT COALESCE(u.usuario, '[eliminado]') AS usuario,
               l.accion, l.fecha, l.ip, g.nombre, l.grupo_id
        FROM logs l
        LEFT JOIN usuarios u ON u.id = l.usuario_id
        LEFT JOIN grupos g ON g.id = l.grupo_id
        ORDER BY l.fecha DESC
        LIMIT 200
    """)

    registros = cur.fetchall()

    logs_por_grupo = defaultdict(list)
    for r in registros:
        grupo_nombre = r[4] or "Sin empresa"
        logs_por_grupo[grupo_nombre].append(r)

    cur.execute("""
        SELECT
            m.id,
            m.fecha,
            COALESCE(u.usuario, '[eliminado]') AS usuario,
            g.nombre,
            m.entidad,
            m.accion,
            m.datos_antes,
            m.datos_despues,
            m.grupo_id,
            m.entidad_id
        FROM movimientos m
        LEFT JOIN usuarios u ON u.id = m.usuario_id
        LEFT JOIN grupos g ON g.id = m.grupo_id
        ORDER BY m.fecha DESC
        LIMIT 200
    """)
    movimientos = cur.fetchall()

    movimientos_por_grupo = defaultdict(list)
    for m in movimientos:
        grupo_nombre = m[3] or "Sin empresa"
        movimientos_por_grupo[grupo_nombre].append(m)

    cur.execute("""
        SELECT
            u.id,
            u.usuario,
            u.rol,
            u.creado_en,
            COALESCE(string_agg(g.nombre, ', ' ORDER BY g.nombre), 'Sin grupo') AS grupos,
            COALESCE(array_agg(g.id ORDER BY g.id), ARRAY[]::integer[]) AS grupo_ids
        FROM usuarios u
        LEFT JOIN usuarios_grupos ug ON ug.usuario_id = u.id
        LEFT JOIN grupos g ON g.id = ug.grupo_id AND g.archivado = FALSE
        GROUP BY u.id, u.usuario, u.rol, u.creado_en
        ORDER BY u.creado_en DESC
    """)
    usuarios = cur.fetchall()

    cur.execute("""
        SELECT id, nombre
        FROM grupos
        WHERE archivado = FALSE
        ORDER BY nombre
    """)
    grupos_todos = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin_logs.html",
        registros=registros,
        movimientos=movimientos,
        logs_por_grupo=logs_por_grupo,
        movimientos_por_grupo=movimientos_por_grupo,
        usuarios=usuarios,
        grupos_todos=grupos_todos
    )


# ---------------- ADMIN: GRUPOS ----------------
@app.route("/admin/grupos", methods=["GET", "POST"])
def admin_grupos():
    return redirect(url_for("grupos"))


@app.route("/admin/grupos/abrir/<int:grupo_id>")
def admin_abrir_grupo(grupo_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if not admin_requerido():
        return "Acceso denegado", 403

    session["grupo_id"] = grupo_id
    return redirect(url_for("archivo"))


# ---------------- ADMIN: MOVIMIENTOS ----------------
@app.route("/admin/movimientos")
def admin_movimientos():
    if not login_requerido():
        return redirect(url_for("login"))

    if not admin_requerido():
        return "Acceso denegado", 403

    return redirect(url_for("admin_logs"))


@app.route("/admin/movimientos/<int:mov_id>/deshacer", methods=["POST"])
def deshacer_movimiento(mov_id):
    if not login_requerido():
        return redirect(url_for("login"))

    if not admin_requerido():
        return "Acceso denegado", 403

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT entidad, accion, datos_antes, datos_despues, grupo_id, entidad_id
        FROM movimientos
        WHERE id = %s
    """, (mov_id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        flash("Movimiento no encontrado.", "error")
        return redirect(url_for("admin_movimientos"))

    entidad, accion, datos_antes, datos_despues, grupo_id, entidad_id = row

    try:
        if entidad == "archivo":
            if accion == "CREAR_ARCHIVO":
                cur.execute(
                    "DELETE FROM archivos WHERE id = %s AND grupo_id = %s",
                    (entidad_id, grupo_id)
                )
            elif accion == "ELIMINAR_ARCHIVO" and datos_antes:
                cur.execute(
                    """
                    INSERT INTO archivos (id, numero, nombre, caja_id, pdf_path, grupo_id, creado_por)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        datos_antes.get("id"),
                        datos_antes.get("numero"),
                        datos_antes.get("nombre"),
                        datos_antes.get("caja_id"),
                        datos_antes.get("pdf_path"),
                        grupo_id,
                        None,
                    )
                )
            elif accion == "ARCHIVO_MOVER" and datos_antes:
                cur.execute(
                    "UPDATE archivos SET caja_id = %s WHERE id = %s AND grupo_id = %s",
                    (datos_antes.get("caja_id"), entidad_id, grupo_id)
                )
            elif accion == "MODIFICAR_ARCHIVO" and datos_antes:
                cur.execute(
                    """
                    UPDATE archivos
                    SET numero = %s, nombre = %s, caja_id = %s, pdf_path = %s
                    WHERE id = %s AND grupo_id = %s
                    """,
                    (
                        datos_antes.get("numero"),
                        datos_antes.get("nombre"),
                        datos_antes.get("caja_id"),
                        datos_antes.get("pdf_path"),
                        entidad_id,
                        grupo_id,
                    )
                )

        if entidad == "caja":
            if accion == "CREAR_CAJA":
                cur.execute(
                    "DELETE FROM cajas WHERE id = %s AND grupo_id = %s",
                    (entidad_id, grupo_id)
                )
            elif accion == "ELIMINAR_CAJA" and datos_antes:
                cur.execute(
                    """
                    INSERT INTO cajas (id, rango_min, rango_max, grupo_id, is_pendiente)
                    VALUES (%s, %s, %s, %s, FALSE)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        entidad_id,
                        datos_antes.get("rango_min"),
                        datos_antes.get("rango_max"),
                        grupo_id,
                    )
                )
            elif accion == "MODIFICAR_CAJA" and datos_antes:
                cur.execute(
                    """
                    UPDATE cajas
                    SET rango_min = %s, rango_max = %s
                    WHERE id = %s AND grupo_id = %s
                    """,
                    (
                        datos_antes.get("rango_min"),
                        datos_antes.get("rango_max"),
                        entidad_id,
                        grupo_id,
                    )
                )

        conn.commit()
        flash("Movimiento deshecho.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al deshacer: {e}", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("admin_movimientos"))


# ---------------- ARCHIVADOR: TRANSFERIR ----------------
@app.route("/archivador/transferir", methods=["POST"])
def archivador_transferir():
    if not login_requerido():
        return redirect(url_for("login"))

    grupo_id = obtener_grupo_id()
    if not admin_requerido() or not es_archivador_grupo(grupo_id):
        return "Acceso denegado", 403

    cajas_ids_raw = request.form.get("cajas_ids", "")
    archivos_ids_raw = request.form.get("archivos_ids", "")
    grupo_destino = int(request.form.get("grupo_destino"))

    if es_archivador_grupo(grupo_destino):
        flash("No puedes mover elementos al Archivador.", "error")
        return redirect(url_for("archivo") + "?view=especial")

    cajas_ids = [int(x) for x in cajas_ids_raw.split(",") if x.strip().isdigit()]
    archivos_ids = [int(x) for x in archivos_ids_raw.split(",") if x.strip().isdigit()]

    if not cajas_ids and not archivos_ids:
        flash("No hay elementos seleccionados.", "error")
        return redirect(url_for("archivo") + "?view=especial")

    conn = get_db()
    cur = conn.cursor()

    pendientes_id = asegurar_caja_sin_asignar(grupo_destino)
    warnings = []
    moved_file_ids = set()

    # Mover cajas completas
    for caja_id in cajas_ids:
        cur.execute(
            """
            SELECT rango_min, rango_max, is_pendiente
            FROM cajas
            WHERE id = %s AND grupo_id = %s
            """,
            (caja_id, grupo_id)
        )
        row = cur.fetchone()
        if not row:
            continue

        rmin, rmax, is_pendiente = row
        if is_pendiente:
            warnings.append(f"Caja {caja_id} es pendiente y no se movio.")
            continue

        # Aviso de solapamiento de rangos en destino
        cur.execute(
            """
            SELECT id, rango_min, rango_max
            FROM cajas
            WHERE grupo_id = %s
              AND is_pendiente = FALSE
              AND NOT (rango_max < %s OR rango_min > %s)
            """,
            (grupo_destino, rmin, rmax)
        )
        overlaps = cur.fetchall()
        if overlaps:
            warnings.append(
                f"Caja {caja_id} tiene solapamiento de rango en grupo destino."
            )

        cur.execute(
            """
            UPDATE cajas
            SET grupo_id = %s,
                grupo_origen_id = COALESCE(grupo_origen_id, %s)
            WHERE id = %s
            """,
            (grupo_destino, grupo_id, caja_id)
        )

        cur.execute(
            """
            UPDATE archivos
            SET grupo_id = %s,
                grupo_origen_id = COALESCE(grupo_origen_id, %s)
            WHERE caja_id = %s
            """,
            (grupo_destino, grupo_id, caja_id)
        )

        cur.execute("SELECT id FROM archivos WHERE caja_id = %s", (caja_id,))
        moved_file_ids.update([r[0] for r in cur.fetchall()])

    # Mover archivos sueltos
    for archivo_id in archivos_ids:
        if archivo_id in moved_file_ids:
            continue

        cur.execute(
            "SELECT numero FROM archivos WHERE id = %s AND grupo_id = %s",
            (archivo_id, grupo_id)
        )
        row = cur.fetchone()
        if not row:
            continue

        numero = row[0]
        cur.execute(
            """
            SELECT id
            FROM cajas
            WHERE grupo_id = %s
              AND is_pendiente = FALSE
              AND %s BETWEEN rango_min AND rango_max
            ORDER BY rango_min, id
            LIMIT 1
            """,
            (grupo_destino, numero)
        )
        dest = cur.fetchone()
        dest_caja = dest[0] if dest else pendientes_id

        cur.execute(
            """
            UPDATE archivos
            SET grupo_id = %s,
                caja_id = %s,
                grupo_origen_id = COALESCE(grupo_origen_id, %s)
            WHERE id = %s
            """,
            (grupo_destino, dest_caja, grupo_id, archivo_id)
        )

    conn.commit()
    cur.close()
    conn.close()

    if warnings:
        flash("Aviso: " + " | ".join(warnings), "info")
    else:
        flash("Elementos movidos correctamente.", "success")

    return redirect(url_for("archivo") + "?view=especial")


# ---------------- ARCHIVADOR: ELIMINAR ----------------
@app.route("/archivador/eliminar", methods=["POST"])
def archivador_eliminar():
    if not login_requerido():
        return redirect(url_for("login"))

    grupo_id = obtener_grupo_id()
    if not admin_requerido() or not es_archivador_grupo(grupo_id):
        return "Acceso denegado", 403

    cajas_ids_raw = request.form.get("cajas_ids", "")
    archivos_ids_raw = request.form.get("archivos_ids", "")

    cajas_ids = [int(x) for x in cajas_ids_raw.split(",") if x.strip().isdigit()]
    archivos_ids = [int(x) for x in archivos_ids_raw.split(",") if x.strip().isdigit()]

    if not cajas_ids and not archivos_ids:
        flash("No hay elementos seleccionados.", "error")
        return redirect(url_for("archivo") + "?view=especial")

    conn = get_db()
    cur = conn.cursor()

    # Eliminar archivos sueltos (que no esten en cajas seleccionadas)
    if archivos_ids:
        cur.execute(
            "DELETE FROM archivos WHERE id = ANY(%s) AND grupo_id = %s",
            (archivos_ids, grupo_id)
        )

    # Eliminar cajas y sus archivos
    for caja_id in cajas_ids:
        cur.execute(
            "DELETE FROM archivos WHERE caja_id = %s AND grupo_id = %s",
            (caja_id, grupo_id)
        )
        cur.execute(
            "DELETE FROM cajas WHERE id = %s AND grupo_id = %s",
            (caja_id, grupo_id)
        )

    conn.commit()
    cur.close()
    conn.close()

    flash("Elementos eliminados permanentemente.", "success")
    return redirect(url_for("archivo") + "?view=especial")

@app.route("/export/excel")
def export_excel():
    if not login_requerido():
        return redirect(url_for("login"))

    grupo_id = obtener_grupo_id()
    if not grupo_id:
        return redirect(url_for("grupos"))

    conn = get_db()
    cur = conn.cursor()

    # ===== 1) HOJA CAJAS (sin ID real, usando caja_visible) =====
    cur.execute("""
        WITH ranked AS (
            SELECT id, rango_min, rango_max,
                   ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE grupo_id = %s AND is_pendiente = FALSE
        )
        SELECT
            r.caja_visible AS caja_num,
            r.rango_min,
            r.rango_max,
            COALESCE(COUNT(a.id),0) AS total_archivos
        FROM ranked r
        LEFT JOIN archivos a ON a.caja_id = r.id AND a.grupo_id = %s
        GROUP BY r.caja_visible, r.rango_min, r.rango_max
        ORDER BY r.caja_visible
    """, (grupo_id, grupo_id))
    cajas = cur.fetchall()

    # Caja pendiente (solo si tiene archivos)
    pendiente_id = asegurar_caja_sin_asignar(grupo_id)
    cur.execute(
        "SELECT COUNT(*) FROM archivos WHERE caja_id = %s AND grupo_id = %s",
        (pendiente_id, grupo_id)
    )
    total_caja0 = cur.fetchone()[0]

    # ===== 2) HOJA ARCHIVOS (caja_visible, documento, nombre, pdf si/no) =====
    cur.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE grupo_id = %s AND is_pendiente = FALSE
        )
        SELECT
            CASE WHEN c.is_pendiente THEN 0 ELSE r.caja_visible END AS caja_num,
            a.numero,
            a.nombre,
            CASE WHEN a.pdf_path IS NULL OR a.pdf_path = '' THEN 'No' ELSE 'Si' END AS pdf
        FROM archivos a
        JOIN cajas c ON c.id = a.caja_id
        LEFT JOIN ranked r ON r.id = c.id
        WHERE a.grupo_id = %s
        ORDER BY caja_num, a.numero
    """, (grupo_id, grupo_id))
    archivos = cur.fetchall()

    cur.close()
    conn.close()

    # ===== Crear Excel =====
    wb = Workbook()

    # ---- Hoja 1: Cajas ----
    ws1 = wb.active
    ws1.title = "Cajas"
    ws1.append(["Caja", "Rango", "Total de archivos"])

    for (caja_num, rmin, rmax, total) in cajas:
        ws1.append([caja_num, f"{rmin}-{rmax}", total])

    if total_caja0 and total_caja0 > 0:
        # Caja 0 al final, sin rango
        ws1.append([0, "", total_caja0])

    # ---- Hoja 2: Archivos ----
    ws2 = wb.create_sheet("Archivos")
    ws2.append(["Caja", "Número", "Nombre", "PDF"])

    # Insertar filas en blanco al cambiar de caja (como tu imagen)
    last_caja = None
    for (caja_num, numero, nombre, pdf) in archivos:
        if last_caja is not None and caja_num != last_caja:
            ws2.append([])  # fila en blanco entre cajas
        ws2.append([caja_num, numero, nombre, pdf])
        last_caja = caja_num

    # Auto-width básico (opcional)
    for ws in [ws1, ws2]:
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

    # Guardar a memoria y enviar
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="reporte_archivo.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# PDF

@app.route("/pdf/<int:numero>")
def ver_pdf(numero):
    if not login_requerido():
        return redirect(url_for("login"))

    grupo_id = obtener_grupo_id()
    if not grupo_id:
        return redirect(url_for("grupos"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT pdf_path FROM archivos WHERE numero = %s AND grupo_id = %s",
        (numero, grupo_id)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not row[0]:
        # Si no hay PDF
        return "No hay PDF para este documento.", 404

    filename = row[0]
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)

if __name__ == "__main__":
    app.run(debug=True)
