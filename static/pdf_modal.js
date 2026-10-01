(function(){
  const dataEl = document.getElementById("pdf-modal-data");
  if (!dataEl) return;

  const URL_LIST_BASE = dataEl.dataset.urlListBase || "";
  const URL_PDF_BASE = dataEl.dataset.urlBase || "";
  const URL_PAGES_BASE = dataEl.dataset.urlPages || "";
  const URL_DELETE_PAGES_BASE = dataEl.dataset.urlDeletePages || "";
  const URL_REORDER_PAGES_BASE = dataEl.dataset.urlReorderPages || "";
  const CSRF_TOKEN = dataEl.dataset.csrfToken || "";
  const CAN_DELETE_PAGES = dataEl.dataset.canDeletePages === "1";

  let pdfDoc = null;
  let currentNumero = null;
  let currentCedula = null;
  let currentNombre = "";
  let currentPdfList = [];
  let selectedPages = new Set();
  let pageOrder = [];
  let originalPageOrder = [];
  let thumbCache = new Map();
  let draggedPage = null;

  function buildPdfUrl(numero, fresh){
    const base = URL_PDF_BASE.replace("/0", "/" + String(numero));
    if (!fresh) return base;
    const sep = base.includes("?") ? "&" : "?";
    return base + sep + "v=" + Date.now();
  }

  function buildPdfListUrl(numero){
    return URL_LIST_BASE.replace("/0", "/" + String(numero));
  }

  function buildPagesUrl(numero, pages, download){
    const base = URL_PAGES_BASE.replace("/0", "/" + String(numero));
    const params = new URLSearchParams();
    params.set("pages", pages.join(","));
    if (download) params.set("download", "1");
    return base + "?" + params.toString();
  }

  function buildDeletePagesUrl(numero){
    return URL_DELETE_PAGES_BASE.replace("/0/", "/" + String(numero) + "/");
  }

  function buildReorderPagesUrl(numero){
    return URL_REORDER_PAGES_BASE.replace("/0/", "/" + String(numero) + "/");
  }

  function show(id){ document.getElementById(id).style.display = "block"; }
  function hide(id){ document.getElementById(id).style.display = "none"; }

  function arraysEqual(a, b){
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++){
      if (a[i] !== b[i]) return false;
    }
    return true;
  }

  function hasPendingOrder(){
    return !arraysEqual(pageOrder, originalPageOrder);
  }

  function updateOrderActions(){
    const note = document.getElementById("pdfOrderNote");
    const resetBtn = document.getElementById("pdfOrderResetBtn");
    const confirmBtn = document.getElementById("pdfOrderConfirmBtn");
    if (!note || !resetBtn || !confirmBtn) return;

    const pending = hasPendingOrder();
    note.textContent = pending ? "Cambios sin guardar" : "Orden sin cambios";
    resetBtn.disabled = !pending;
    confirmBtn.disabled = !pending;
  }

  async function renderPreview(pageNumber){
    if (!pdfDoc) return;
    const page = await pdfDoc.getPage(pageNumber);
    const viewport = page.getViewport({ scale: 1.1 });
    const canvas = document.getElementById("pdfPreviewCanvas");
    const ctx = canvas.getContext("2d");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvasContext: ctx, viewport }).promise;
  }

  async function ensureThumbCache(){
    if (!pdfDoc) return;
    for (let i = 1; i <= pdfDoc.numPages; i++){
      if (thumbCache.has(i)) continue;
      const page = await pdfDoc.getPage(i);
      const viewport = page.getViewport({ scale: 0.25 });
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: ctx, viewport }).promise;
      thumbCache.set(i, canvas.toDataURL("image/png"));
    }
  }

  function movePageInOrder(sourcePage, targetPage){
    const fromIdx = pageOrder.indexOf(sourcePage);
    const toIdx = pageOrder.indexOf(targetPage);
    if (fromIdx === -1 || toIdx === -1 || fromIdx === toIdx) return;
    const updated = [...pageOrder];
    updated.splice(fromIdx, 1);
    updated.splice(toIdx, 0, sourcePage);
    pageOrder = updated;
  }

  async function renderThumbs(previewPage){
    const thumbs = document.getElementById("pdfThumbs");
    if (!thumbs || !pdfDoc) return;

    thumbs.innerHTML = "";
    await ensureThumbCache();

    for (const pageNum of pageOrder){
      const wrap = document.createElement("div");
      wrap.className = "pdf-thumb" + (CAN_DELETE_PAGES ? " draggable" : "");
      wrap.dataset.page = String(pageNum);
      if (CAN_DELETE_PAGES) {
        wrap.draggable = true;
      }

      const image = document.createElement("img");
      image.src = thumbCache.get(pageNum);
      image.alt = "Pagina " + pageNum;
      image.style.width = "100%";
      image.style.height = "auto";
      image.style.display = "block";

      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.checked = selectedPages.has(pageNum);
      chk.addEventListener("change", () => {
        if (chk.checked){
          selectedPages.add(pageNum);
          wrap.classList.add("selected");
        } else {
          selectedPages.delete(pageNum);
          wrap.classList.remove("selected");
        }
        updateSelectedActions();
      });

      if (chk.checked) {
        wrap.classList.add("selected");
      }

      wrap.addEventListener("click", (e) => {
        if (e.target === chk) return;
        renderPreview(pageNum);
      });

      if (CAN_DELETE_PAGES) {
        wrap.addEventListener("dragstart", () => {
          draggedPage = pageNum;
          wrap.classList.add("dragging");
        });

        wrap.addEventListener("dragend", () => {
          draggedPage = null;
          wrap.classList.remove("dragging");
          document.querySelectorAll(".pdf-thumb.drag-over").forEach((el) => el.classList.remove("drag-over"));
        });

        wrap.addEventListener("dragover", (e) => {
          e.preventDefault();
          if (draggedPage && draggedPage !== pageNum) {
            wrap.classList.add("drag-over");
          }
        });

        wrap.addEventListener("dragleave", () => {
          wrap.classList.remove("drag-over");
        });

        wrap.addEventListener("drop", async (e) => {
          e.preventDefault();
          wrap.classList.remove("drag-over");
          if (!draggedPage || draggedPage === pageNum) return;
          movePageInOrder(draggedPage, pageNum);
          await renderThumbs(draggedPage);
          updateOrderActions();
        });
      }

      const label = document.createElement("div");
      label.className = "pdf-thumb-page";
      label.innerText = "Pagina " + pageNum;

      wrap.appendChild(image);
      wrap.appendChild(chk);
      wrap.appendChild(label);
      thumbs.appendChild(wrap);
    }

    updateSelectedActions();
    updateOrderActions();

    const pageToPreview = previewPage || pageOrder[0];
    if (pageToPreview) {
      await renderPreview(pageToPreview);
    }
  }

  function updateSelectedActions(){
    const actions = document.getElementById("pdfSelectedActions");
    if (!actions) return;
    actions.style.display = selectedPages.size > 0 ? "flex" : "none";
  }

  function renderPdfList(numero, nombre, pdfs, selectedId){
    const list = document.getElementById("pdfDocumentList");
    if (!list) return;
    list.innerHTML = "";
    pdfs.forEach((item) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "pdf-document-option" + (item.id === selectedId ? " active" : "");
      const title = document.createElement("strong");
      title.textContent = item.factura;
      const detail = document.createElement("span");
      const date = new Date(item.fecha + "T00:00:00").toLocaleDateString("es-CO");
      detail.textContent = date + " · " + (nombre || ("Cédula " + numero));
      option.appendChild(title);
      option.appendChild(detail);
      option.addEventListener("click", () => {
        openPdfModalFromNumero(numero, nombre, item.id, pdfs).catch(() => {
          alert("No se pudo cargar el PDF.");
        });
      });
      list.appendChild(option);
    });
  }

  async function openPdfModalFromNumero(numero, nombre, pdfId, pdfs){
    if (!window.pdfjsLib){
      alert("No se pudo cargar el visor de PDF.");
      return;
    }
    pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

    currentNumero = pdfId;
    currentCedula = numero;
    currentNombre = nombre || "";
    currentPdfList = pdfs || currentPdfList;
    thumbCache = new Map();
    selectedPages.clear();

    document.getElementById("pdfModalTitle").innerText = "Documentos PDF";
    document.getElementById("pdfModalSub").innerText = "Cédula: " + String(currentCedula);
    renderPdfList(currentCedula, currentNombre, currentPdfList, currentNumero);

    const url = buildPdfUrl(pdfId, true);
    pdfDoc = await pdfjsLib.getDocument(url).promise;
    pageOrder = Array.from({ length: pdfDoc.numPages }, (_, idx) => idx + 1);
    originalPageOrder = [...pageOrder];

    show("pdfModalOverlay");
    show("pdfModal");
    await renderThumbs(pageOrder[0]);
  }

  window.abrirPdfModal = function(btn){
    const numero = Number(btn.dataset.numero);
    const nombre = btn.dataset.nombre || "";
    if (!numero) return;
    fetch(buildPdfListUrl(numero), { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error("No se pudo cargar la lista.");
        return response.json();
      })
      .then((payload) => {
        const pdfs = Array.isArray(payload.pdfs) ? payload.pdfs : [];
        if (!pdfs.length) {
          alert("Este documento no tiene PDF.");
          return;
        }
        show("pdfModalOverlay");
        show("pdfModal");
        return openPdfModalFromNumero(numero, nombre, pdfs[0].id, pdfs);
      })
      .catch(() => {
        alert("No se pudo cargar la lista de PDFs.");
      });
  };

  window.cerrarPdfModal = function(){
    hide("pdfModalOverlay");
    hide("pdfModal");
  };

  window.abrirPdfCompleto = function(){
    if (!currentNumero) return;
    window.open(buildPdfUrl(currentNumero, true), "_blank", "noopener");
  };

  window.abrirSeleccionadas = function(){
    if (!currentNumero || selectedPages.size === 0) return;
    const pages = Array.from(selectedPages).sort((a,b)=>a-b);
    window.open(buildPagesUrl(currentNumero, pages, false), "_blank", "noopener");
  };

  window.descargarSeleccionadas = function(){
    if (!currentNumero || selectedPages.size === 0) return;
    const pages = Array.from(selectedPages).sort((a,b)=>a-b);
    window.open(buildPagesUrl(currentNumero, pages, true), "_blank", "noopener");
  };

  window.restablecerOrdenPdf = async function(){
    if (!hasPendingOrder()) return;
    pageOrder = [...originalPageOrder];
    await renderThumbs(pageOrder[0]);
  };

  window.confirmarOrdenPdf = async function(){
    if (!CAN_DELETE_PAGES || !currentNumero || !hasPendingOrder()) return;
    const ok = window.confirm("Se guardará el nuevo orden del PDF. Esta acción modificará el archivo actual.");
    if (!ok) return;

    try {
      const body = new URLSearchParams();
      body.set("_csrf_token", CSRF_TOKEN);
      body.set("order", pageOrder.join(","));

      const response = await fetch(buildReorderPagesUrl(currentNumero), {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
          "X-Requested-With": "XMLHttpRequest"
        },
        body: body.toString(),
        cache: "no-store"
      });

      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        alert(payload?.error || "No se pudo guardar el nuevo orden del PDF.");
        return;
      }

      alert(payload.message || "Orden guardado correctamente.");
      await openPdfModalFromNumero(currentCedula, currentNombre, currentNumero, currentPdfList);
    } catch (error) {
      console.error("No se pudo guardar el orden del PDF", error);
      alert("No se pudo guardar el nuevo orden del PDF.");
    }
  };

  window.eliminarSeleccionadasPdf = async function(){
    if (!CAN_DELETE_PAGES || !currentNumero || selectedPages.size === 0) return;
    const pages = Array.from(selectedPages).sort((a,b)=>a-b);
    const ok = window.confirm(
      "Se eliminarán de forma permanente las páginas seleccionadas del PDF. Esta acción no se puede deshacer.\n\nPáginas: " + pages.join(", ")
    );
    if (!ok) return;

    try {
      const body = new URLSearchParams();
      body.set("_csrf_token", CSRF_TOKEN);
      body.set("pages", pages.join(","));

      const response = await fetch(buildDeletePagesUrl(currentNumero), {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
          "X-Requested-With": "XMLHttpRequest"
        },
        body: body.toString(),
        cache: "no-store"
      });

      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        alert(payload?.error || "No se pudieron eliminar las páginas seleccionadas.");
        return;
      }

      alert(payload.message || "Páginas eliminadas correctamente.");
      await openPdfModalFromNumero(currentCedula, currentNombre, currentNumero, currentPdfList);
    } catch (error) {
      console.error("No se pudieron eliminar las páginas", error);
      alert("No se pudieron eliminar las páginas seleccionadas.");
    }
  };

  document.addEventListener("click", function(e){
    const overlay = document.getElementById("pdfModalOverlay");
    if (e.target === overlay){
      window.cerrarPdfModal();
    }
  });
})();
