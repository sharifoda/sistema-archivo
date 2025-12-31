print(">>> APP.PY CORRECTO CARGADO <<<")
import os
from werkzeug.utils import secure_filename
from flask import send_file, send_from_directory
from openpyxl import Workbook
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
from auth import crear_usuario, verificar_usuario, obtener_usuario_y_rol
from logs import registrar_log
from db import get_db
from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
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

def guardar_pdf(file, numero_documento):
    """
    Guarda el pdf y retorna el path relativo (para guardar en DB).
    """
    filename = secure_filename(file.filename)
    # Guardar con nombre controlado (evita duplicados raros)
    final_name = f"doc_{numero_documento}.pdf"
    abs_path = os.path.join(app.config["UPLOAD_FOLDER"], final_name)
    file.save(abs_path)
    # Guardamos en DB un path relativo simple
    return final_name


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

            flash("Caja eliminada correctamente.", "success")
            return redirect(url_for("cajas"))

        # ======================
        # MODIFICAR CAJA (modal)
        # ======================
        if accion == "modificar":
            caja_id = int(request.form["caja_id"])
            nuevo_min = int(request.form["rango_min"])
            nuevo_max = int(request.form["rango_max"])

            modificar_caja(caja_id, nuevo_min, nuevo_max)

            movidos_fuera = reubicar_archivos_de_caja(caja_id)
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
        if accion == "crear":
            rmin = int(request.form["rango_min"])
            rmax = int(request.form["rango_max"])

            nueva_caja_id = crear_caja(
                rmin,
                rmax,
                creado_por=session.get("usuario_id")
            )

            # Reubicar archivos pendientes (Caja 0) si encajan en la nueva caja
            movidos = reubicar_archivos_pendientes_por_nueva_caja(nueva_caja_id)

            registrar_log(
                session.get("usuario_id"),
                f"CREAR_CAJA caja_id={nueva_caja_id} rango={rmin}-{rmax} movidos_desde_caja0={movidos}",
                request.remote_addr
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
                f"ARCHIVO|tipo=REGISTRO|numero_new={numero}|nombre_new={nombre_final}|caja={caja_id}",
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

            # Antes:
            cur.execute("SELECT caja_id, numero, nombre FROM archivos WHERE numero = %s", (numero_old,))
            antes = cur.fetchone()
            caja_id = antes[0] if antes else 0
            numero_viejo = antes[1] if antes else numero_old
            nombre_viejo = antes[2] if antes else ""

            # ... haces el UPDATE ...

            registrar_log(
                session.get("usuario_id"),
                f"ARCHIVO|tipo=MODIFICACION|numero_old={numero_viejo}|numero_new={numero_new}|nombre_old={nombre_viejo}|nombre_new={nombre_new}|caja={caja_id}",
                request.remote_addr
            )

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
                f"ARCHIVO|tipo=ELIMINACION|numero_old={numero}|nombre_old={nombre_final}|caja={caja_id}",
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
                SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
                FROM cajas
                WHERE id <> 0
                )
                SELECT
                c.id AS caja_id,
                CASE WHEN c.id = 0 THEN 0 ELSE r.caja_visible END AS caja_num,
                a.numero AS documento,
                a.nombre AS nombre,
                a.pdf_path
                FROM archivos a
                JOIN cajas c ON c.id = a.caja_id
                LEFT JOIN ranked r ON r.id = c.id
                WHERE a.numero = %s
                LIMIT 1;
            """, (numero_buscar,))

            resultado = cur.fetchone()
        except ValueError:
            resultado = ("error", buscar, None)

    # Modo edición (qué documento está en edición)
    edit_num = request.args.get("edit", "").strip()
    edit_num = int(edit_num) if edit_num.isdigit() else None

    # Últimos movimientos (10)
    cur.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE id <> 0
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
            ORDER BY l.fecha DESC
            LIMIT 10
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY b.fecha DESC) AS movimiento,

            CASE
                WHEN COALESCE(b.caja_id, a.caja_id, 0) = 0 THEN 0
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

# ---------------- ARCHIVO ----------------

@app.route("/archivo", methods=["GET", "POST"])
def archivo():
    if not login_requerido():
        return redirect(url_for("login"))

    asegurar_caja_sin_asignar()

    # ===== POST: acciones del dashboard =====
    if request.method == "POST":
        accion = request.form.get("accion")

        # ---------- Crear Caja ----------
        if accion == "crear_caja":
            rmin = int(request.form["rango_min"])
            rmax = int(request.form["rango_max"])

            nueva_caja_id = crear_caja(rmin, rmax, creado_por=session.get("usuario_id"))
            movidos = reubicar_archivos_pendientes_por_nueva_caja(nueva_caja_id)

            registrar_log(
                session.get("usuario_id"),
                f"CREAR_CAJA caja_id={nueva_caja_id} rango={rmin}-{rmax} movidos_desde_caja0={movidos}",
                request.remote_addr
            )

            flash("Caja creada correctamente.", "success")
            return redirect(url_for("archivo"))

        # ---------- Agregar Documento ----------
        if accion == "agregar_documento":
            numero = int(request.form["numero"])
            nombre = request.form.get("nombre", "").strip()

            # 1) crear archivo normal
            agregar_archivo(numero, nombre, creado_por=session.get("usuario_id"))

            # 2) si viene pdf, guardarlo y actualizar DB
            file = request.files.get("pdf")
            if file and file.filename:
                if not es_pdf(file):
                    flash("El archivo debe ser PDF.", "error")
                    return redirect(url_for("archivo"))

                pdf_name = guardar_pdf(file, numero)

                conn = get_db()
                cur = conn.cursor()
                cur.execute("UPDATE archivos SET pdf_path = %s WHERE numero = %s", (pdf_name, numero))
                conn.commit()
                cur.close()
                conn.close()

            registrar_log(session.get("usuario_id"), f"AGREGAR_ARCHIVO numero={numero}", request.remote_addr)
            flash("Documento agregado correctamente.", "success")
            return redirect(url_for("archivo"))


        # ---------- Eliminar Archivo (desde modal de búsqueda) ----------
        if accion == "eliminar_archivo_modal":
            numero = int(request.form["numero"])

            conn = get_db()
            cur = conn.cursor()

            # datos antes de borrar para log
            cur.execute("SELECT caja_id, numero, nombre FROM archivos WHERE numero = %s", (numero,))
            antes = cur.fetchone()

            cur.execute("DELETE FROM archivos WHERE numero = %s", (numero,))
            conn.commit()

            cur.close()
            conn.close()

            if antes:
                caja_old, numero_old, nombre_old = antes
                registrar_log(
                    session.get("usuario_id"),
                    f"ARCHIVO|tipo=ELIMINACION|numero_old={numero_old}|nombre_old={nombre_old}|caja={caja_old}",
                    request.remote_addr
                )

            flash("Archivo eliminado correctamente.", "success")
            return redirect(url_for("archivo"))

        # ---------- Modificar Archivo (desde modal de búsqueda) ----------

    if request.method == "POST" and accion == "modificar_archivo_modal":
        numero_old = int(request.form["numero_old"])
        numero_new = int(request.form["numero_new"])
        nombre_new = request.form.get("nombre_new", "").strip()

        # NUEVO: checkbox para eliminar PDF actual
        remove_pdf = request.form.get("remove_pdf") == "1"

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT caja_id, numero, nombre, pdf_path FROM archivos WHERE numero = %s", (numero_old,))
        antes = cur.fetchone()

        if not antes:
            cur.close()
            conn.close()
            flash("No se encontró el archivo a modificar.", "error")
            return redirect(url_for("archivo"))

        caja_old, numero_viejo, nombre_viejo, pdf_old = antes

        # Caja destino según rangos del numero_new
        cur.execute("""
            SELECT id
            FROM cajas
            WHERE id <> 0 AND %s BETWEEN rango_min AND rango_max
            ORDER BY rango_min, id
            LIMIT 1
        """, (numero_new,))
        caja_dest = cur.fetchone()
        caja_dest_id = caja_dest[0] if caja_dest else 0

        # =========================
        # NUEVO: eliminar PDF actual
        # =========================
        pdf_name = pdf_old

        if remove_pdf and pdf_old:
            try:
                # Si pdf_old es relativo (ej: "static/pdfs/123.pdf"), lo volvemos absoluto
                path = pdf_old
                if not os.path.isabs(path):
                    path = os.path.join(app.root_path, path)
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print("Error eliminando PDF:", e)

            pdf_name = None  # en DB quedará NULL

        # =========================
        # PDF (opcional) - reemplazo
        # =========================
        file = request.files.get("pdf")
        if file and file.filename:
            if not es_pdf(file):
                cur.close()
                conn.close()
                flash("El archivo debe ser PDF.", "error")
                return redirect(url_for("archivo"))

            # Si había PDF anterior y no fue eliminado arriba, lo borramos (para evitar basura)
            if pdf_old and not remove_pdf:
                try:
                    old_path = pdf_old
                    if not os.path.isabs(old_path):
                        old_path = os.path.join(app.root_path, old_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                except Exception as e:
                    print("Error eliminando PDF anterior:", e)

            # Guardar nuevo PDF (tu función)
            pdf_name = guardar_pdf(file, numero_new)

        # Update
        cur.execute("""
            UPDATE archivos
            SET numero = %s, nombre = %s, caja_id = %s, pdf_path = %s
            WHERE numero = %s
        """, (numero_new, nombre_new, caja_dest_id, pdf_name, numero_old))

        conn.commit()
        cur.close()
        conn.close()

        registrar_log(
            session.get("usuario_id"),
            f"ARCHIVO|tipo=MODIFICACION|numero_old={numero_viejo}|numero_new={numero_new}|"
            f"nombre_old={nombre_viejo}|nombre_new={nombre_new}|caja={caja_dest_id}|"
            f"pdf_eliminado={1 if (remove_pdf and pdf_old) else 0}|pdf_nuevo={1 if (file and file.filename) else 0}",
            request.remote_addr
        )

        flash("Archivo modificado correctamente.", "success")
        return redirect(url_for("archivo"))



    # ===== GET: listado de cajas =====
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE id <> 0
        )
        SELECT
            c.id AS caja_id,
            CASE WHEN c.id = 0 THEN 0 ELSE r.caja_visible END AS caja_num,
            c.rango_min,
            c.rango_max,
            COUNT(a.id) AS total_archivos
        FROM cajas c
        LEFT JOIN archivos a ON a.caja_id = c.id
        LEFT JOIN ranked r ON r.id = c.id
        GROUP BY c.id, r.caja_visible, c.rango_min, c.rango_max
        ORDER BY
            CASE WHEN c.id = 0 THEN 1 ELSE 0 END,
            caja_num
    """)

    cajas_data = cur.fetchall()

    cajas_filtradas = [c for c in cajas_data if not (c[0] == 0 and c[4] == 0)]

    # ===== Buscador para modal =====
        # Buscador
        # ===== Buscador para modal =====
    resultado = None
    buscar_raw = request.args.get("buscar", "").strip()

    if buscar_raw:
        try:
            doc = int(buscar_raw)

            cur.execute("""
                WITH ranked AS (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
                    FROM cajas
                    WHERE id <> 0
                )
                SELECT
                    c.id AS caja_id,
                    CASE WHEN c.id = 0 THEN 0 ELSE r.caja_visible END AS caja_num,
                    a.numero AS documento,
                    a.nombre AS nombre,
                    a.pdf_path
                FROM archivos a
                JOIN cajas c ON c.id = a.caja_id
                LEFT JOIN ranked r ON r.id = c.id
                WHERE a.numero = %s
                LIMIT 1
            """, (doc,))

            row = cur.fetchone()
            if row:
                resultado = row
            else:
                resultado = ("no",)

        except ValueError:
            resultado = ("error", buscar_raw)


    cur.close()
    conn.close()

    return render_template(
        "archivo_dashboard.html",
        cajas=cajas_filtradas,
        resultado=resultado
    )

# ---------------- archivo_caja ----------------

@app.route("/archivo/caja/<int:caja_id>", methods=["GET", "POST"])
def archivo_caja(caja_id):
    if not login_requerido():
        return redirect(url_for("login"))

    asegurar_caja_sin_asignar()

    # ======================
    # POST: Acciones en esta caja
    # ======================
    if request.method == "POST":
        accion = request.form.get("accion")

        # ---------- MODIFICAR CAJA ----------
        if accion == "modificar_caja":
            nuevo_min = int(request.form["rango_min"])
            nuevo_max = int(request.form["rango_max"])

            modificar_caja(caja_id, nuevo_min, nuevo_max)

            # Reubicar archivos según nuevo rango
            movidos_fuera = reubicar_archivos_de_caja(caja_id)
            movidos_dentro = reubicar_archivos_pendientes_por_nueva_caja(caja_id)
            total = movidos_fuera + movidos_dentro

            registrar_log(
                session.get("usuario_id"),
                f"MODIFICAR_CAJA caja_id={caja_id} rango={nuevo_min}-{nuevo_max} reasignados={total}",
                request.remote_addr
            )

            if total > 0:
                flash(f"Se reasignaron automáticamente {total} archivo(s) según el nuevo rango.", "success")
            else:
                flash("El rango se actualizó. No fue necesario reasignar archivos.", "info")

            return redirect(url_for("archivo_caja", caja_id=caja_id))

        # ---------- ELIMINAR ARCHIVO ----------
        if accion == "eliminar_archivo_fila":
            numero = int(request.form["numero"])

            conn = get_db()
            cur = conn.cursor()

            # obtener datos antes de borrar (para log)
            cur.execute("SELECT caja_id, numero, nombre FROM archivos WHERE numero = %s", (numero,))
            antes = cur.fetchone()

            cur.execute("DELETE FROM archivos WHERE numero = %s", (numero,))
            conn.commit()

            cur.close()
            conn.close()

            if antes:
                caja_old, numero_old, nombre_old = antes
                registrar_log(
                    session.get("usuario_id"),
                    f"ARCHIVO|tipo=ELIMINACION|numero_old={numero_old}|nombre_old={nombre_old}|caja={caja_old}",
                    request.remote_addr
                )

            flash("Archivo eliminado correctamente.", "success")
            return redirect(url_for("archivo_caja", caja_id=caja_id))

        # ---------- MODIFICAR ARCHIVO (numero y/o nombre) ----------
        if accion == "modificar_archivo_fila":
            numero_old = int(request.form["numero_old"])
            numero_new = int(request.form["numero_new"])
            nombre_new = request.form.get("nombre_new", "").strip()

            conn = get_db()
            cur = conn.cursor()

            # datos anteriores
            cur.execute("SELECT caja_id, numero, nombre FROM archivos WHERE numero = %s", (numero_old,))
            antes = cur.fetchone()

            if not antes:
                cur.close()
                conn.close()
                flash("No se encontró el archivo a modificar.", "error")
                return redirect(url_for("archivo_caja", caja_id=caja_id))

            caja_old, numero_viejo, nombre_viejo = antes

            # decidir caja destino según rangos actuales
            cur.execute("""
                SELECT id
                FROM cajas
                WHERE id <> 0 AND %s BETWEEN rango_min AND rango_max
                ORDER BY rango_min, id
                LIMIT 1
            """, (numero_new,))
            caja_dest = cur.fetchone()
            caja_dest_id = caja_dest[0] if caja_dest else 0

            # actualizar
            cur.execute("""
                UPDATE archivos
                SET numero = %s, nombre = %s, caja_id = %s
                WHERE numero = %s
            """, (numero_new, nombre_new, caja_dest_id, numero_old))

            conn.commit()
            cur.close()
            conn.close()

            registrar_log(
                session.get("usuario_id"),
                f"ARCHIVO|tipo=MODIFICACION|numero_old={numero_viejo}|numero_new={numero_new}|nombre_old={nombre_viejo}|nombre_new={nombre_new}|caja={caja_dest_id}",
                request.remote_addr
            )

            flash("Archivo modificado correctamente.", "success")

            # si el archivo cambió de caja, llévalo a la nueva caja
            if caja_dest_id != caja_id:
                return redirect(url_for("archivo_caja", caja_id=caja_dest_id))
            return redirect(url_for("archivo_caja", caja_id=caja_id))

        flash("Acción no válida.", "error")
        return redirect(url_for("archivo_caja", caja_id=caja_id))

    # ======================
    # GET: Render de la caja + archivos
    # ======================
    conn = get_db()
    cur = conn.cursor()

    # info de caja + numero visible
    cur.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE id <> 0
        )
        SELECT
            c.id,
            CASE WHEN c.id = 0 THEN 0 ELSE r.caja_visible END AS caja_num,
            c.rango_min,
            c.rango_max
        FROM cajas c
        LEFT JOIN ranked r ON r.id = c.id
        WHERE c.id = %s
    """, (caja_id,))
    caja_info = cur.fetchone()

    if not caja_info:
        cur.close()
        conn.close()
        flash("La caja no existe.", "error")
        return redirect(url_for("archivo"))

    # archivos de la caja
    cur.execute("""
        SELECT a.numero, a.nombre
        FROM archivos a
        WHERE a.caja_id = %s
        ORDER BY a.numero
    """, (caja_id,))
    archivos = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("archivo_caja.html", caja=caja_info, archivos=archivos)


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

    conn = get_db()
    cur = conn.cursor()

    # ===== 1) HOJA CAJAS (sin ID real, usando caja_visible) =====
    cur.execute("""
        WITH ranked AS (
            SELECT id, rango_min, rango_max,
                   ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE id <> 0
        )
        SELECT
            r.caja_visible AS caja_num,
            r.rango_min,
            r.rango_max,
            COALESCE(COUNT(a.id),0) AS total_archivos
        FROM ranked r
        LEFT JOIN archivos a ON a.caja_id = r.id
        GROUP BY r.caja_visible, r.rango_min, r.rango_max
        ORDER BY r.caja_visible
    """)
    cajas = cur.fetchall()

    # Caja 0 (solo si tiene archivos)
    cur.execute("""
        SELECT COUNT(*) FROM archivos WHERE caja_id = 0
    """)
    total_caja0 = cur.fetchone()[0]

    # ===== 2) HOJA ARCHIVOS (caja_visible, documento, nombre, pdf si/no) =====
    cur.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY rango_min, id) AS caja_visible
            FROM cajas
            WHERE id <> 0
        )
        SELECT
            CASE WHEN c.id = 0 THEN 0 ELSE r.caja_visible END AS caja_num,
            a.numero,
            a.nombre,
            CASE WHEN a.pdf_path IS NULL OR a.pdf_path = '' THEN 'No' ELSE 'Sí' END AS pdf
        FROM archivos a
        JOIN cajas c ON c.id = a.caja_id
        LEFT JOIN ranked r ON r.id = c.id
        ORDER BY caja_num, a.numero
    """)
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

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT pdf_path FROM archivos WHERE numero = %s", (numero,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not row[0]:
        # Si no hay PDF
        return "No hay PDF para este documento.", 404

    filename = row[0]
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
