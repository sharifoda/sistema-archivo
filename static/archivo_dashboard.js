/* =========================
   Datos enviados desde Flask
   ========================= */
const el = document.getElementById("server-data");
const data = JSON.parse(el.dataset.json);

const URL_CAJA_BASE = data.urlCajaBase;
const URL_PDF_BASE  = data.urlPdfBase;
const resultado     = data.resultado;

/* =========================
   Estado global de búsqueda
   ========================= */
const BUSQ = {
  cajaId: null,
  cajaNum: null,
  doc: null,
  nombre: null,
  pdf: null
};

/* =========================
   Helpers UI
   ========================= */
function show(id) {
  document.getElementById(id).style.display = "block";
}

function hide(id) {
  document.getElementById(id).style.display = "none";
}

function abrirModal(tipo) {
  show("overlay" + tipo);
  show("modal" + tipo);
}

function cerrarModal(tipo, limpiarBuscar = false) {
  hide("overlay" + tipo);
  hide("modal" + tipo);

  if (limpiarBuscar) {
    const url = new URL(window.location);
    url.searchParams.delete("buscar");
    window.history.replaceState({}, "", url);
  }
}

/* =========================
   URLs dinámicas
   ========================= */
function buildCajaUrl(cajaId, highlightDoc) {
  const base = URL_CAJA_BASE.replace("/0", "/" + String(cajaId));
  if (!highlightDoc) return base;
  return base + "?highlight=" + encodeURIComponent(String(highlightDoc));
}

function buildPdfUrl(doc) {
  return URL_PDF_BASE.replace("/0", "/" + String(doc));
}

function formatMiles(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return value;
  return num.toLocaleString("es-CO");
}

/* =========================
   Modal editar desde búsqueda
   ========================= */
function abrirModalEditarDesdeBusqueda() {
  if (BUSQ.doc === null) return;

  document.getElementById("numero_old").value = BUSQ.doc;
  document.getElementById("numero_new").value = BUSQ.doc;
  document.getElementById("nombre_new").value = BUSQ.nombre || "";

  document.getElementById("editarInfo").innerText =
    "Editando documento: " +
    BUSQ.doc +
    " (Caja " +
    (BUSQ.cajaNum === 0 ? "0 - Pendiente" : BUSQ.cajaNum) +
    ")";

  abrirModal("Editar");
}

/* =========================
   Eventos globales
   ========================= */

// Cerrar modal al hacer click en overlay
document.addEventListener("click", function (e) {
  ["Caja", "Doc", "Buscar", "Editar"].forEach(tipo => {
    const ov = document.getElementById("overlay" + tipo);
    if (e.target === ov) {
      cerrarModal(tipo, tipo === "Buscar");
    }
  });
});

// Cerrar con ESC
document.addEventListener("keydown", function (e) {
  if (e.key !== "Escape") return;

  cerrarModal("Caja");
  cerrarModal("Doc");
  cerrarModal("Buscar", true);
  cerrarModal("Editar");
});

/* =========================
   Procesar resultado búsqueda
   ========================= */
if (resultado) {
  const cont = document.getElementById("buscarContenido");

  // Error de input
  if (resultado[0] === "error") {
    cont.innerHTML =
      `<p style="color:#b00020;">⚠️ Debes ingresar un número válido.</p>`;

  // No encontrado
  } else if (resultado[0] === "no") {
    cont.innerHTML =
      `<p style="color:#b00020;">❌ No se encontró ningún archivo con ese documento.</p>`;

  // Resultado OK
  } else {
    // resultado = [caja_id, caja_num, documento, nombre, pdf_path]
    BUSQ.cajaId = resultado[0];
    BUSQ.cajaNum = resultado[1];
    BUSQ.doc = resultado[2];
    BUSQ.nombre = resultado[3];
    BUSQ.pdf = resultado.length > 4 ? resultado[4] : null;

    const cajaTxt =
      BUSQ.cajaNum === 0
        ? "<strong>0</strong> (Pendiente)"
        : BUSQ.cajaNum;

    const irCajaUrl = buildCajaUrl(BUSQ.cajaId, BUSQ.doc);

    const pdfLink = BUSQ.pdf
      ? `<a class="btn-small" href="${buildPdfUrl(BUSQ.doc)}" target="_blank" rel="noopener">📄 Ver PDF</a>`
      : `<button type="button" class="btn-small btn-disabled"
           onclick="alert('Este documento no tiene PDF.');">
           📄 Ver PDF
         </button>`;

    cont.innerHTML = `
      <table>
        <tr>
          <th>Caja</th>
          <th>Documento</th>
          <th>Nombre</th>
          <th>PDF</th>
          <th>Acción</th>
        </tr>
        <tr>
          <td>${cajaTxt}</td>
          <td>${formatMiles(BUSQ.doc)}</td>
          <td>${BUSQ.nombre}</td>
          <td>${BUSQ.pdf ? "Sí" : "No"}</td>
          <td>
            <div class="acciones-cell">
              <button type="button" class="btn-small"
                      onclick="abrirModalEditarDesdeBusqueda()">
                ✏️ Modificar
              </button>

              <form method="post" style="margin:0;">
                <input type="hidden" name="accion" value="eliminar_archivo_modal">
                <input type="hidden" name="numero" value="${BUSQ.doc}">
                <button type="submit" class="btn-small btn-danger"
                        onclick="return confirm('¿Seguro que deseas eliminar el documento ' + BUSQ.doc + '?');">
                  🗑️ Eliminar
                </button>
              </form>

              ${pdfLink}

              <a class="btn-small" href="${irCajaUrl}"
                 style="text-decoration:none; color:#000;">
                📦 Ir a
              </a>
            </div>
          </td>
        </tr>
      </table>
    `;
  }

  abrirModal("Buscar");
}
