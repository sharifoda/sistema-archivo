/* =========================
   Datos enviados desde Flask
   ========================= */
const el = document.getElementById("server-data");
const data = JSON.parse(el.dataset.json);

const URL_CAJA_BASE = data.urlCajaBase;
const URL_PDF_BASE  = data.urlPdfBase;
const IMPORT_STATUS_URL = data.importStatusUrl || "";
const IMPORT_REPORT_URL_BASE = data.importReportUrlBase || "";
const IMPORT_CLOSE_URL = data.importCloseUrl || "";
const IMPORT_JOB = data.importJob || null;
const resultado     = data.resultado;
const csrfToken     = data.csrfToken || "";
const PDF_BULK_DATA = Array.isArray(data.pdfBulkData) ? data.pdfBulkData : [];
let importStatusTimer = null;
let importLastInserted = IMPORT_JOB && Number.isFinite(Number(IMPORT_JOB.inserted)) ? Number(IMPORT_JOB.inserted) : 0;
let importCurrentJob = IMPORT_JOB || null;
let importJustStarted = false;
let importTypePending = IMPORT_JOB?.import_type || "excel";

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

  const modalAbierto = ["Caja", "CajaMasiva", "Doc", "Buscar", "Editar", "PdfDownload"].some((name) => {
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

function formatDateTime(value) {
  if (!value) return "N/D";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("es-CO", { timeZone: "America/Bogota" });
}

function buildImportReportUrl(jobId) {
  return IMPORT_REPORT_URL_BASE ? IMPORT_REPORT_URL_BASE.replace("__JOB__", String(jobId || "")) : "";
}

function getImportLabels(job) {
  const importType = String(job?.import_type || importTypePending || "excel").toLowerCase();
  if (importType === "pdf") {
    return {
      importType,
      headingProgress: "Carga de PDF en progreso",
      headingDone: "Carga de PDF finalizada",
      defaultMessage: "Carga de PDF en proceso.",
      pendingDetail: "Subiendo archivos y preparando la carga masiva de PDF...",
      processed: "Procesados",
      inserted: "Nuevos",
      merged: "Unidos",
      ignored: "No encontrados",
      invalid: "Invalidos"
    };
  }
  return {
    importType,
    headingProgress: "Carga de Excel en progreso",
    headingDone: "Carga de Excel finalizada",
    defaultMessage: "Importacion en proceso.",
    pendingDetail: "Subiendo archivo y preparando el analisis del Excel...",
    processed: "Procesados",
    inserted: "Exitosos",
    merged: "Unidos",
    ignored: "Repetidos",
    invalid: "Invalidos"
  };
}

function syncImportJobUrl(jobId, done = false) {
  if (!jobId) return;
  const url = new URL(window.location.href);
  url.searchParams.set("import_job", String(jobId));
  if (done) {
    url.searchParams.set("import_done", "1");
  } else {
    url.searchParams.delete("import_done");
  }
  window.history.replaceState({}, "", url.toString());
}

function clearImportJobUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("import_job");
  url.searchParams.delete("import_done");
  window.history.replaceState({}, "", url.toString());
}

function renderImportStatus(job) {
  importCurrentJob = job || null;
  if (job?.import_type) {
    importTypePending = job.import_type;
  }
  const banner = document.getElementById("importStatusBanner");
  const title = document.getElementById("importStatusTitle");
  const meta = document.getElementById("importStatusMeta");
  const note = document.getElementById("importStatusNote");
  if (!banner || !title || !meta || !note) return;

  if (!job) {
    banner.className = "import-status";
    title.textContent = "";
    meta.innerHTML = "";
    note.textContent = "";
    return;
  }

  banner.className = `import-status visible ${job.status || "processing"}`;
  title.textContent = job.message || "Importacion en proceso.";
  const labels = getImportLabels(job);
  meta.innerHTML = [
    `Total: ${formatMiles(job.total_rows || 0)}`,
    `${labels.processed}: ${formatMiles(job.processed_rows || 0)}`,
    `${labels.inserted}: ${formatMiles(job.inserted || 0)}`,
    `${labels.merged}: ${formatMiles(job.merged || 0)}`,
    `${labels.ignored}: ${formatMiles(job.ignored || 0)}`,
    `${labels.invalid}: ${formatMiles(job.invalid || 0)}`
  ]
    .map((item) => `<span>${item}</span>`)
    .join("");
  note.textContent = job.detail || "";

  renderImportProgressModal(job);
}

function renderImportProgressModal(job) {
  const overlay = document.getElementById("importProgressOverlay");
  const modal = document.getElementById("importProgressModal");
  const ring = document.getElementById("importProgressRing");
  const percentEl = document.getElementById("importProgressPercent");
  const heading = document.getElementById("importProgressHeading");
  const message = document.getElementById("importProgressMessage");
  const processedLabel = document.getElementById("importProcessedLabel");
  const insertedLabel = document.getElementById("importInsertedLabel");
  const mergedLabel = document.getElementById("importMergedLabel");
  const ignoredLabel = document.getElementById("importIgnoredLabel");
  const invalidLabel = document.getElementById("importInvalidLabel");
  const processed = document.getElementById("importProcessedValue");
  const inserted = document.getElementById("importInsertedValue");
  const merged = document.getElementById("importMergedValue");
  const ignored = document.getElementById("importIgnoredValue");
  const invalid = document.getElementById("importInvalidValue");
  const detail = document.getElementById("importProgressDetail");
  const viewBtn = document.getElementById("importViewReportBtn");
  const closeBtn = document.getElementById("importCloseProgressBtn");
  if (!overlay || !modal || !ring || !percentEl || !heading || !message || !processedLabel || !insertedLabel || !mergedLabel || !ignoredLabel || !invalidLabel || !processed || !inserted || !merged || !ignored || !invalid || !detail || !viewBtn || !closeBtn) {
    return;
  }

  if (!job) {
    overlay.classList.remove("visible");
    modal.classList.remove("visible");
    return;
  }

  const total = Number(job.total_rows || 0);
  const processedRows = Number(job.processed_rows || 0);
  const percent = total > 0 ? Math.min(100, Math.round((processedRows / total) * 100)) : 0;
  const progressDeg = `${Math.max(percent, job.status === "success" || job.status === "partial" ? 100 : 0) * 3.6}deg`;
  const labels = getImportLabels(job);

  ring.className = `import-progress-ring ${job.status || "processing"}`;
  ring.style.setProperty("--progress", progressDeg);
  percentEl.textContent = `${percent}%`;
  processedLabel.textContent = labels.processed;
  insertedLabel.textContent = labels.inserted;
  mergedLabel.textContent = labels.merged;
  ignoredLabel.textContent = labels.ignored;
  invalidLabel.textContent = labels.invalid;
  heading.textContent = job.status === "processing" || job.status === "pending"
    ? labels.headingProgress
    : labels.headingDone;
  message.textContent = job.message || (importJustStarted ? "Preparando carga..." : labels.defaultMessage);
  processed.textContent = formatMiles(processedRows);
  inserted.textContent = formatMiles(job.inserted || 0);
  merged.textContent = formatMiles(job.merged || 0);
  ignored.textContent = formatMiles(job.ignored || 0);
  invalid.textContent = formatMiles(job.invalid || 0);

  const parts = [
    `Inicio: ${formatDateTime(job.started_at)}`,
    `Fin: ${formatDateTime(job.finished_at)}`,
    `Usuario: ${job.user_name || "N/D"}`,
    `Empresa: ${job.group_name || "N/D"}`
  ];
  if (job.error_code) {
    parts.push(`Error: ${job.error_code}`);
  }
  detail.textContent = [job.detail || (importJustStarted ? labels.pendingDetail : ""), parts.join(" | ")].filter(Boolean).join(" | ");

  if (job.status === "processing" || job.status === "pending") {
    overlay.classList.add("visible");
    modal.classList.add("visible");
    viewBtn.style.display = "none";
    closeBtn.style.display = "none";
    document.body.classList.add("dashboard-modal-open");
    return;
  }

  overlay.classList.add("visible");
  modal.classList.add("visible");
  viewBtn.style.display = job.job_id ? "inline-flex" : "none";
  closeBtn.style.display = "inline-flex";
  document.body.classList.add("dashboard-modal-open");
}

async function cerrarImportProgressModal() {
  if (importStatusTimer) {
    window.clearTimeout(importStatusTimer);
    importStatusTimer = null;
  }

  if (IMPORT_CLOSE_URL) {
    try {
      const body = new URLSearchParams();
      body.set("_csrf_token", csrfToken);
      if (importCurrentJob?.job_id) {
        body.set("job_id", importCurrentJob.job_id);
      }
      await fetch(IMPORT_CLOSE_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
          "X-Requested-With": "XMLHttpRequest"
        },
        body: body.toString(),
        cache: "no-store"
      });
    } catch (error) {
      console.error("No se pudo cerrar el informe activo", error);
    }
  }

  importCurrentJob = null;
  importJustStarted = false;
  renderImportStatus(null);
  clearImportJobUrl();

  const overlay = document.getElementById("importProgressOverlay");
  const modal = document.getElementById("importProgressModal");
  if (overlay) overlay.classList.remove("visible");
  if (modal) modal.classList.remove("visible");
  document.body.classList.remove("dashboard-modal-open");
}

async function verInformeImportacion(jobId) {
  const url = buildImportReportUrl(jobId);
  if (!url) return;
  try {
    const response = await fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      cache: "no-store"
    });
    if (!response.ok) {
      alert("No se pudo cargar el informe.");
      return;
    }
    const payload = await response.json();
    if (!payload.ok || !payload.report) {
      alert("No se pudo cargar el informe.");
      return;
    }
    renderImportReport(payload.report);
  } catch (error) {
    console.error("No se pudo cargar el informe", error);
    alert("No se pudo cargar el informe.");
  }
}

async function verInformeImportacionActual() {
  if (!importCurrentJob || !importCurrentJob.job_id) return;
  const jobId = importCurrentJob.job_id;
  await cerrarImportProgressModal();
  verInformeImportacion(jobId);
}

function renderImportReport(report) {
  const overlay = document.getElementById("importReportOverlay");
  const modal = document.getElementById("importReportModal");
  const content = document.getElementById("importReportContent");
  if (!overlay || !modal || !content) return;

  const labels = getImportLabels(report);
  const mergedBlock = Number(report.merged || 0) > 0 || labels.importType === "pdf"
    ? `<div class="import-progress-stat"><strong>${labels.merged}</strong><span>${formatMiles(report.merged || 0)}</span></div>`
    : "";
  const invalidList = Array.isArray(report.invalid_details) && report.invalid_details.length
    ? `
      <div class="import-progress-detail">
        <strong>Invalidos detectados</strong>
        <ul class="report-invalid-list">
          ${report.invalid_details.map((item) => `<li>${escapeAttr(item)}</li>`).join("")}
        </ul>
      </div>
    `
    : `<div class="import-progress-detail"><strong>Invalidos detectados</strong><div>No hubo registros invalidos.</div></div>`;

  content.innerHTML = `
    <div class="import-progress-grid">
      <div class="import-progress-stat"><strong>Archivo</strong><span style="font-size:14px;">${escapeAttr(report.source_filename || "N/D")}</span></div>
      <div class="import-progress-stat"><strong>Estado</strong><span style="font-size:14px;">${escapeAttr(String(report.status || "").toUpperCase())}</span></div>
      <div class="import-progress-stat"><strong>Usuario</strong><span style="font-size:14px;">${escapeAttr(report.user_name || "N/D")}</span></div>
      <div class="import-progress-stat"><strong>Empresa</strong><span style="font-size:14px;">${escapeAttr(report.group_name || "N/D")}</span></div>
      <div class="import-progress-stat"><strong>Total</strong><span>${formatMiles(report.total_rows || 0)}</span></div>
      <div class="import-progress-stat"><strong>${labels.processed}</strong><span>${formatMiles(report.processed_rows || 0)}</span></div>
      <div class="import-progress-stat"><strong>${labels.inserted}</strong><span>${formatMiles(report.inserted || 0)}</span></div>
      ${mergedBlock}
      <div class="import-progress-stat"><strong>${labels.ignored}</strong><span>${formatMiles(report.ignored || 0)}</span></div>
      <div class="import-progress-stat"><strong>${labels.invalid}</strong><span>${formatMiles(report.invalid || 0)}</span></div>
      <div class="import-progress-stat"><strong>Error</strong><span style="font-size:14px;">${report.error_code ? "ERROR " + report.error_code : "Sin error"}</span></div>
      <div class="import-progress-stat"><strong>Inicio</strong><span style="font-size:14px;">${escapeAttr(formatDateTime(report.started_at))}</span></div>
      <div class="import-progress-stat"><strong>Fin</strong><span style="font-size:14px;">${escapeAttr(formatDateTime(report.finished_at))}</span></div>
    </div>
    <div class="import-progress-detail" style="margin-top:14px;">
      <strong>Resumen</strong>
      <div style="margin-top:6px;">${escapeAttr(report.detail || "Sin observaciones.")}</div>
    </div>
    ${invalidList}
  `;

  overlay.style.display = "block";
  modal.style.display = "block";
  document.body.classList.add("dashboard-modal-open");
}

function cerrarInformeImportacion() {
  const overlay = document.getElementById("importReportOverlay");
  const modal = document.getElementById("importReportModal");
  if (overlay) overlay.style.display = "none";
  if (modal) modal.style.display = "none";
  if (!document.getElementById("importProgressModal")?.classList.contains("visible")) {
    document.body.classList.remove("dashboard-modal-open");
  }
}

async function pollImportStatus() {
  if (!IMPORT_STATUS_URL) return;
  try {
    const response = await fetch(IMPORT_STATUS_URL, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      cache: "no-store"
    });
    if (!response.ok) {
      importStatusTimer = window.setTimeout(pollImportStatus, 1400);
      return;
    }
    const payload = await response.json();
    if (!payload.ok || !payload.job) {
      importStatusTimer = window.setTimeout(pollImportStatus, 1400);
      return;
    }
    importJustStarted = false;
    renderImportStatus(payload.job);

    const insertedNow = Number(payload.job.inserted || 0);
    importLastInserted = Math.max(importLastInserted, insertedNow);

    if (payload.job.status === "processing" || payload.job.status === "pending") {
      importStatusTimer = window.setTimeout(pollImportStatus, 1400);
      return;
    }

    if (payload.job.status === "success" || payload.job.status === "partial" || payload.job.status === "failed") {
      if (importStatusTimer) {
        window.clearTimeout(importStatusTimer);
        importStatusTimer = null;
      }
      const url = new URL(window.location.href);
      if (url.searchParams.get("import_done") !== "1" && payload.job.job_id) {
        url.searchParams.set("import_job", payload.job.job_id);
        url.searchParams.set("import_done", "1");
        window.location.replace(url.toString());
        return;
      }
      return;
    }
  } catch (error) {
    console.error("No se pudo consultar el estado de importacion", error);
    importStatusTimer = window.setTimeout(pollImportStatus, 1800);
  }
}

function mostrarImportacionInmediata(importType = "excel", total = 0, filename = "") {
  importJustStarted = true;
  importTypePending = importType;
  const labels = getImportLabels({ import_type: importType });
  renderImportStatus({
    job_id: "",
    import_type: importType,
    status: "pending",
    message: importType === "pdf" ? "Carga masiva de PDF iniciada." : "Importacion iniciada.",
    total_rows: total,
    processed_rows: 0,
    inserted: 0,
    merged: 0,
    ignored: 0,
    invalid: 0,
    source_filename: filename,
    detail: labels.pendingDetail,
    user_name: "",
    group_name: "",
    started_at: new Date().toISOString(),
    finished_at: null,
    error_code: null
  });
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

[
  "overlayCaja",
  "modalCaja",
  "overlayCajaMasiva",
  "modalCajaMasiva",
  "overlayDoc",
  "modalDoc",
  "overlayBuscar",
  "modalBuscar",
  "overlayEditar",
  "modalEditar",
  "overlayPdfDownload",
  "modalPdfDownload",
  "importReportOverlay",
  "importReportModal",
  "importProgressOverlay",
  "importProgressModal"
].forEach((id) => {
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
  ["Caja", "CajaMasiva", "Doc", "Buscar", "Editar", "PdfDownload"].forEach(tipo => {
    const ov = document.getElementById("overlay" + tipo);
    if (e.target === ov) {
      cerrarModal(tipo, tipo === "Buscar");
    }
  });

  if (e.target === document.getElementById("importReportOverlay")) {
    cerrarInformeImportacion();
  }
});

// Cerrar con ESC
document.addEventListener("keydown", function (e) {
  if (e.key !== "Escape") return;

  cerrarModal("Caja");
  cerrarModal("CajaMasiva");
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
      const selectedInBox = box.docs.filter((doc) => BULK_PDF.selectedDocs.has(String(doc.id))).length;
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
      const checked = BULK_PDF.selectedDocs.has(String(doc.id)) ? "checked" : "";
      return `
        <label class="bulk-doc-item">
          <div class="bulk-doc-copy">
            <strong>${formatMiles(doc.numero)}${doc.tipo_doc ? " · " + doc.tipo_doc : ""}</strong>
            <span>${String(doc.nombre || "").toUpperCase()}</span>
          </div>
          <input type="checkbox" ${checked} onchange="toggleBulkDoc('${doc.id}', this.checked)">
        </label>
      `;
    })
    .join("");

  updateBulkSummary();
}

function toggleBulkDoc(docId, checked) {
  if (checked) {
    BULK_PDF.selectedDocs.add(String(docId));
  } else {
    BULK_PDF.selectedDocs.delete(String(docId));
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
  box.docs.forEach((doc) => BULK_PDF.selectedDocs.add(String(doc.id)));
  renderBulkPdfBoxes();
}

function limpiarCajaActiva() {
  const box = getBulkBox(BULK_PDF.activeBoxId);
  if (!box) return;
  box.docs.forEach((doc) => BULK_PDF.selectedDocs.delete(String(doc.id)));
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

if (IMPORT_JOB) {
  if (new URL(window.location.href).searchParams.get("import_done") === "1" && IMPORT_JOB.job_id) {
    syncImportJobUrl(IMPORT_JOB.job_id, false);
  }
  renderImportStatus(IMPORT_JOB);
  if (IMPORT_JOB.status === "processing" || IMPORT_JOB.status === "pending") {
    importStatusTimer = window.setTimeout(pollImportStatus, 1200);
  }
}


