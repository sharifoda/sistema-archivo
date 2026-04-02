/* =========================
   Datos enviados desde Flask
   ========================= */
const el = document.getElementById("server-data");
const data = JSON.parse(el.dataset.json);

const URL_CAJA_BASE = data.urlCajaBase;
const URL_PDF_BASE  = data.urlPdfBase;
const resultado     = data.resultado;
const csrfToken     = data.csrfToken || "";
const PDF_BULK_DATA = Array.isArray(data.pdfBulkData) ? data.pdfBulkData : [];

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

const BULK_PDF = {
  boxes: PDF_BULK_DATA,
  activeBoxId: PDF_BULK_DATA.length ? PDF_BULK_DATA[0].id : null,
  selectedDocs: new Set()
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
  document.body.classList.add("dashboard-modal-open");
  show("overlay" + tipo);
  show("modal" + tipo);
}

function cerrarModal(tipo, limpiarBuscar = false) {
  hide("overlay" + tipo);
  hide("modal" + tipo);

  const modalAbierto = ["Caja", "Doc", "Buscar", "Editar", "PdfDownload"].some((name) => {
    const modal = document.getElementById("modal" + name);
    return modal && modal.style.display === "block";
  });
  if (!modalAbierto) {
    document.body.classList.remove("dashboard-modal-open");
  }

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
  const pdfOptions = document.getElementById("editarPdfOptions");
  const appendInput = document.getElementById("editar_append_pdf");
  const removeInput = document.getElementById("editar_remove_pdf");
  const hasPdf = !!BUSQ.pdf;

  if (pdfOptions) {
    pdfOptions.style.display = hasPdf ? "block" : "none";
  }
  if (appendInput) {
    appendInput.checked = false;
  }
  if (removeInput) {
    removeInput.checked = false;
  }

  document.getElementById("editarInfo").innerText =
    "Editando documento: " +
    BUSQ.doc +
    " (Caja " +
    (BUSQ.cajaNum === 0 ? "0 - Pendiente" : BUSQ.cajaNum) +
    ")";

  abrirModal("Editar");
}

const editarAppendInput = document.getElementById("editar_append_pdf");
const editarRemoveInput = document.getElementById("editar_remove_pdf");
if (editarAppendInput && editarRemoveInput) {
  editarAppendInput.addEventListener("change", function () {
    if (editarAppendInput.checked) editarRemoveInput.checked = false;
  });
  editarRemoveInput.addEventListener("change", function () {
    if (editarRemoveInput.checked) editarAppendInput.checked = false;
  });
}

["overlayPdfDownload", "modalPdfDownload"].forEach((id) => {
  const el = document.getElementById(id);
  if (el && el.parentElement !== document.body) {
    document.body.appendChild(el);
  }
});

/* =========================
   Eventos globales
   ========================= */

// Cerrar modal al hacer click en overlay
document.addEventListener("click", function (e) {
  ["Caja", "Doc", "Buscar", "Editar", "PdfDownload"].forEach(tipo => {
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
  cerrarModal("PdfDownload");
});

function getBulkBox(boxId) {
  return BULK_PDF.boxes.find((box) => box.id === boxId) || null;
}

function updateBulkSummary() {
  const total = BULK_PDF.selectedDocs.size;
  const el = document.getElementById("bulkDocsSummary");
  if (!el) return;
  el.textContent =
    total > 0
      ? `${total} PDF${total === 1 ? "" : "s"} marcado${total === 1 ? "" : "s"} para descargar.`
      : "Solo se descargarán los PDFs marcados.";
}

function renderBulkPdfBoxes() {
  const list = document.getElementById("bulkBoxesList");
  if (!list) return;

  if (!BULK_PDF.boxes.length) {
    list.innerHTML = `<div class="bulk-empty">No hay cajas con PDFs disponibles.</div>`;
    const docsList = document.getElementById("bulkDocsList");
    if (docsList) docsList.innerHTML = `<div class="bulk-empty">No hay PDFs para descargar.</div>`;
    const title = document.getElementById("bulkDocsTitle");
    if (title) title.textContent = "Sin PDFs";
    updateBulkSummary();
    return;
  }

  if (!getBulkBox(BULK_PDF.activeBoxId)) {
    BULK_PDF.activeBoxId = BULK_PDF.boxes[0].id;
  }

  list.innerHTML = BULK_PDF.boxes
    .map((box) => {
      const selectedInBox = box.docs.filter((doc) => BULK_PDF.selectedDocs.has(String(doc.numero))).length;
      return `
        <label class="bulk-box-item ${box.id === BULK_PDF.activeBoxId ? "active" : ""}" onclick="setActiveBulkBox(${box.id})">
          <div class="bulk-box-copy">
            <strong>Caja ${box.numero}</strong>
            <span>${box.docs.length} PDF${box.docs.length === 1 ? "" : "s"} disponibles${selectedInBox ? " · " + selectedInBox + " marcado" + (selectedInBox === 1 ? "" : "s") : ""}</span>
          </div>
        </label>
      `;
    })
    .join("");

  renderBulkPdfDocs();
}

function setActiveBulkBox(boxId) {
  BULK_PDF.activeBoxId = boxId;
  renderBulkPdfBoxes();
}

function renderBulkPdfDocs() {
  const box = getBulkBox(BULK_PDF.activeBoxId);
  const title = document.getElementById("bulkDocsTitle");
  const list = document.getElementById("bulkDocsList");
  if (!title || !list) return;

  if (!box) {
    title.textContent = "Selecciona una caja";
    list.innerHTML = `<div class="bulk-empty">Selecciona una caja para ver sus PDFs.</div>`;
    updateBulkSummary();
    return;
  }

  title.textContent = `Caja ${box.numero}`;
  list.innerHTML = box.docs
    .map((doc) => {
      const checked = BULK_PDF.selectedDocs.has(String(doc.numero)) ? "checked" : "";
      return `
        <label class="bulk-doc-item">
          <div class="bulk-doc-copy">
            <strong>${formatMiles(doc.numero)}${doc.tipo_doc ? " · " + doc.tipo_doc : ""}</strong>
            <span>${String(doc.nombre || "").toUpperCase()}</span>
          </div>
          <input type="checkbox" ${checked} onchange="toggleBulkDoc('${doc.numero}', this.checked)">
        </label>
      `;
    })
    .join("");

  updateBulkSummary();
}

function toggleBulkDoc(numero, checked) {
  if (checked) {
    BULK_PDF.selectedDocs.add(String(numero));
  } else {
    BULK_PDF.selectedDocs.delete(String(numero));
  }
  renderBulkPdfBoxes();
}

function toggleBulkBox(boxId, checked) {
  BULK_PDF.activeBoxId = boxId;
  renderBulkPdfBoxes();
}

function seleccionarTodosCajaActiva() {
  const box = getBulkBox(BULK_PDF.activeBoxId);
  if (!box) return;
  box.docs.forEach((doc) => BULK_PDF.selectedDocs.add(String(doc.numero)));
  renderBulkPdfBoxes();
}

function limpiarCajaActiva() {
  const box = getBulkBox(BULK_PDF.activeBoxId);
  if (!box) return;
  box.docs.forEach((doc) => BULK_PDF.selectedDocs.delete(String(doc.numero)));
  renderBulkPdfBoxes();
}

function descargarPdfSeleccionados() {
  if (!BULK_PDF.selectedDocs.size) {
    alert("Debes seleccionar al menos un PDF.");
    return;
  }
  const input = document.getElementById("bulkSelectedDocs");
  const form = document.getElementById("bulkPdfDownloadForm");
  if (!input || !form) return;
  input.value = Array.from(BULK_PDF.selectedDocs).join(",");
  form.submit();
}

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


