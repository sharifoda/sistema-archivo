/* =========================
   Datos enviados desde Flask
   ========================= */
const el = document.getElementById("server-data");
const data = JSON.parse(el.dataset.json);

const URL_CAJA_BASE = data.urlCajaBase;
const URL_PDF_BASE  = data.urlPdfBase;
const resultado     = data.resultado;
const csrfToken     = data.csrfToken || "";

/* =========================
   Estado global de búsqueda
   ========================= */
const BUSQ = {
  cajaId: null,
  cajaNum: null,
  tipoDoc: null,
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

function escapeAttr(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/* =========================
   Modal editar desde búsqueda
   ========================= */
function abrirModalEditarDesdeBusqueda(doc, nombre, cajaNum, cajaId, tipoDoc) {
  if (doc === null || doc === undefined) return;

  BUSQ.doc = doc;
  BUSQ.nombre = nombre;
  BUSQ.cajaNum = cajaNum;
  BUSQ.cajaId = cajaId;
  BUSQ.tipoDoc = tipoDoc || "";

  document.getElementById("numero_old").value = BUSQ.doc;
  document.getElementById("numero_new").value = BUSQ.doc;
  document.getElementById("nombre_new").value = BUSQ.nombre || "";
  document.getElementById("tipo_doc_new").value = BUSQ.tipoDoc || "";

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

document.addEventListener("click", function (e) {
  const btn = e.target.closest(".btn-modificar-busq");
  if (!btn) return;

  const doc = Number(btn.dataset.doc);
  const nombre = btn.dataset.nombre || "";
  const cajaNum = Number(btn.dataset.cajaNum);
  const cajaId = Number(btn.dataset.cajaId);
  const tipoDoc = btn.dataset.tipoDoc || "";

  abrirModalEditarDesdeBusqueda(doc, nombre, cajaNum, cajaId, tipoDoc);
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
    if (Array.isArray(resultado[0])) {
      const rows = resultado;
      const body = rows
        .map(row => {
          const cajaId = row[0];
          const cajaNum = row[1];
          const tipoDoc = row[2];
          const doc = row[3];
          const nombre = row[4];
          const pdf = row.length > 5 ? row[5] : null;
          const nombreAttr = escapeAttr(nombre || "");

          const cajaTxt =
            cajaNum === 0 ? "<strong>0</strong> (Pendiente)" : cajaNum;
          const irCajaUrl = buildCajaUrl(cajaId, doc);
          const pdfLink = pdf
            ? `<button type="button" class="btn-small"
                 data-numero="${doc}" data-nombre="${nombreAttr}"
                 onclick="abrirPdfModal(this)">Ver PDF</button>`
            : `<button type="button" class="btn-small btn-disabled"
                 onclick="alert('Este documento no tiene PDF.');">
                 Ver PDF
               </button>`;

          return `
            <tr>
              <td>${cajaTxt}</td>
              <td>${tipoDoc || ""}</td>
              <td>${formatMiles(doc)}</td>
              <td>${String(nombre || "").toUpperCase()}</td>
              <td>${pdf ? "Si" : "No"}</td>
              <td>
                <div class="acciones-cell">
                  <button type="button" class="btn-small btn-modificar-busq"
                          data-doc="${doc}"
                          data-nombre="${nombreAttr}"
                          data-tipo-doc="${tipoDoc || ""}"
                          data-caja-num="${cajaNum}"
                          data-caja-id="${cajaId}">
                    Modificar
                  </button>

                  <form method="post" style="margin:0;">
                    <input type="hidden" name="_csrf_token" value="${csrfToken}">
                    <input type="hidden" name="accion" value="eliminar_archivo_modal">
                    <input type="hidden" name="numero" value="${doc}">
                    <button type="submit" class="btn-small btn-danger"
                            onclick="return confirm('Seguro que deseas eliminar el documento ' + ${doc} + '?');">
                      Eliminar
                    </button>
                  </form>

                  ${pdfLink}

                  <a class="btn-small" href="${irCajaUrl}"
                     style="text-decoration:none; color:#000;">
                    Ir a
                  </a>
                </div>
              </td>
            </tr>
          `;
        })
        .join("");

      cont.innerHTML = `
        <table>
          <tr>
            <th>Caja</th>
            <th>Tipo</th>
            <th>Documento</th>
            <th>Nombre</th>
            <th>PDF</th>
            <th>Accion</th>
          </tr>
          ${body}
        </table>
      `;
    } else {
    // resultado = [caja_id, caja_num, tipo_doc, documento, nombre, pdf_path]
    BUSQ.cajaId = resultado[0];
    BUSQ.cajaNum = resultado[1];
    BUSQ.tipoDoc = resultado[2];
    BUSQ.doc = resultado[3];
    BUSQ.nombre = resultado[4];
    BUSQ.pdf = resultado.length > 5 ? resultado[5] : null;

    const cajaTxt =
      BUSQ.cajaNum === 0
        ? "<strong>0</strong> (Pendiente)"
        : BUSQ.cajaNum;

    const irCajaUrl = buildCajaUrl(BUSQ.cajaId, BUSQ.doc);

    const pdfLink = BUSQ.pdf
      ? `<button type="button" class="btn-small" data-numero="${BUSQ.doc}" data-nombre="${escapeAttr(BUSQ.nombre || "")}" onclick="abrirPdfModal(this)">📄 Ver PDF</button>`
      : `<button type="button" class="btn-small btn-disabled"
           onclick="alert('Este documento no tiene PDF.');">
           📄 Ver PDF
         </button>`;

    cont.innerHTML = `
      <table>
        <tr>
          <th>Caja</th>
          <th>Tipo</th>
          <th>Documento</th>
          <th>Nombre</th>
          <th>PDF</th>
          <th>Acción</th>
        </tr>
        <tr>
          <td>${cajaTxt}</td>
          <td>${BUSQ.tipoDoc || ""}</td>
          <td>${formatMiles(BUSQ.doc)}</td>
          <td>${String(BUSQ.nombre || "").toUpperCase()}</td>
          <td>${BUSQ.pdf ? "Sí" : "No"}</td>
          <td>
            <div class="acciones-cell">
              <button type="button" class="btn-small"
                      onclick="abrirModalEditarDesdeBusqueda(BUSQ.doc, BUSQ.nombre, BUSQ.cajaNum, BUSQ.cajaId, BUSQ.tipoDoc)">
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
    const btnMod = cont.querySelector(".acciones-cell > button");
    if (btnMod) {
      btnMod.classList.add("btn-modificar-busq");
      btnMod.removeAttribute("onclick");
      btnMod.dataset.doc = BUSQ.doc;
      btnMod.dataset.nombre = BUSQ.nombre || "";
      btnMod.dataset.tipoDoc = BUSQ.tipoDoc || "";
      btnMod.dataset.cajaNum = BUSQ.cajaNum;
      btnMod.dataset.cajaId = BUSQ.cajaId;
    }
    const formDel = cont.querySelector(".acciones-cell form");
    if (formDel && csrfToken) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "_csrf_token";
      input.value = csrfToken;
      formDel.insertBefore(input, formDel.firstChild);
    }
    }
  }

  abrirModal("Buscar");
}


