(function(){
  const dataEl = document.getElementById("pdf-modal-data");
  if (!dataEl) return;

  const URL_PDF_BASE = dataEl.dataset.urlBase || "";
  const URL_PAGES_BASE = dataEl.dataset.urlPages || "";
  const URL_DELETE_PAGES_BASE = dataEl.dataset.urlDeletePages || "";
  const URL_REORDER_PAGES_BASE = dataEl.dataset.urlReorderPages || "";
  const CSRF_TOKEN = dataEl.dataset.csrfToken || "";
  const CAN_DELETE_PAGES = dataEl.dataset.canDeletePages === "1";

  let pdfDoc = null;
  let currentNumero = null;
  let selectedPages = new Set();

  function buildPdfUrl(numero, fresh){
    const base = URL_PDF_BASE.replace("/0", "/" + String(numero));
    if (!fresh) return base;
    const sep = base.includes("?") ? "&" : "?";
    return base + sep + "v=" + Date.now();
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

  async function renderThumbs(){
    const thumbs = document.getElementById("pdfThumbs");
    thumbs.innerHTML = "";
    selectedPages.clear();
    updateSelectedActions();

    for (let i = 1; i <= pdfDoc.numPages; i++){
      const page = await pdfDoc.getPage(i);
      const viewport = page.getViewport({ scale: 0.25 });
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: ctx, viewport }).promise;

      const wrap = document.createElement("div");
      wrap.className = "pdf-thumb";
      wrap.dataset.page = String(i);

      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.addEventListener("change", () => {
        const pageNum = Number(wrap.dataset.page);
        if (chk.checked){
          selectedPages.add(pageNum);
          wrap.classList.add("selected");
        } else {
          selectedPages.delete(pageNum);
          wrap.classList.remove("selected");
        }
        updateSelectedActions();
      });

      wrap.addEventListener("click", (e) => {
        if (e.target === chk) return;
        renderPreview(i);
      });

      wrap.appendChild(canvas);
      wrap.appendChild(chk);

      const label = document.createElement("div");
      label.className = "pdf-thumb-page";
      label.innerText = "Pagina " + i;
      wrap.appendChild(label);

      thumbs.appendChild(wrap);

      if (i === 1){
        await renderPreview(1);
      }
    }
  }

  function updateSelectedActions(){
    const actions = document.getElementById("pdfSelectedActions");
    const moveUpBtn = document.getElementById("pdfMoveUpBtn");
    const moveDownBtn = document.getElementById("pdfMoveDownBtn");
    if (!actions) return;
    actions.style.display = selectedPages.size > 0 ? "flex" : "none";
    const singleSelected = selectedPages.size === 1;
    const selectedPage = singleSelected ? Array.from(selectedPages)[0] : null;
    if (moveUpBtn) moveUpBtn.disabled = !singleSelected || selectedPage <= 1;
    if (moveDownBtn) moveDownBtn.disabled = !singleSelected || !pdfDoc || selectedPage >= pdfDoc.numPages;
  }

  async function openPdfModalFromNumero(numero, nombre){
    if (!window.pdfjsLib){
      alert("No se pudo cargar el visor de PDF.");
      return;
    }
    pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

    currentNumero = numero;
    document.getElementById("pdfModalTitle").innerText = "PDF";
    document.getElementById("pdfModalSub").innerText = nombre ? ("Documento: " + nombre) : "";

    const url = buildPdfUrl(numero, true);
    pdfDoc = await pdfjsLib.getDocument(url).promise;

    show("pdfModalOverlay");
    show("pdfModal");
    await renderThumbs();
  }

  window.abrirPdfModal = function(btn){
    const numero = Number(btn.dataset.numero);
    const nombre = btn.dataset.nombre || "";
    if (!numero){
      return;
    }
    openPdfModalFromNumero(numero, nombre).catch(() => {
      alert("No se pudo cargar el PDF.");
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

  window.eliminarSeleccionadasPdf = async function(){
    if (!CAN_DELETE_PAGES || !currentNumero || selectedPages.size === 0) return;
    const pages = Array.from(selectedPages).sort((a,b)=>a-b);
    const ok = window.confirm(
      "Se eliminarán de forma permanente las paginas seleccionadas del PDF. Esta accion no se puede deshacer.\n\nPaginas: " + pages.join(", ")
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
        alert(payload?.error || "No se pudieron eliminar las paginas seleccionadas.");
        return;
      }

      alert(payload.message || "Paginas eliminadas correctamente.");
      const currentSub = document.getElementById("pdfModalSub")?.innerText || "";
      await openPdfModalFromNumero(currentNumero, currentSub.replace(/^Documento:\s*/, ""));
    } catch (error) {
      console.error("No se pudieron eliminar las paginas", error);
      alert("No se pudieron eliminar las paginas seleccionadas.");
    }
  };

  window.moverPaginaPdf = async function(direction){
    if (!CAN_DELETE_PAGES || !currentNumero || selectedPages.size !== 1) return;
    if (direction !== "up" && direction !== "down") return;

    const selectedPage = Array.from(selectedPages)[0];
    try {
      const body = new URLSearchParams();
      body.set("_csrf_token", CSRF_TOKEN);
      body.set("page", String(selectedPage));
      body.set("direction", direction);

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
        alert(payload?.error || "No se pudo reordenar la pagina seleccionada.");
        return;
      }

      const currentSub = document.getElementById("pdfModalSub")?.innerText || "";
      await openPdfModalFromNumero(currentNumero, currentSub.replace(/^Documento:\s*/, ""));
      const previewPage = Number(payload.new_page || selectedPage);
      if (previewPage > 0) {
        await renderPreview(previewPage);
      }
      const thumbs = document.querySelectorAll(".pdf-thumb");
      thumbs.forEach((thumb) => {
        const chk = thumb.querySelector('input[type="checkbox"]');
        const pageNum = Number(thumb.dataset.page);
        if (!chk) return;
        if (pageNum === previewPage) {
          chk.checked = true;
          selectedPages.add(pageNum);
          thumb.classList.add("selected");
        }
      });
      updateSelectedActions();
    } catch (error) {
      console.error("No se pudo reordenar la pagina", error);
      alert("No se pudo reordenar la pagina seleccionada.");
    }
  };

  document.addEventListener("click", function(e){
    const overlay = document.getElementById("pdfModalOverlay");
    if (e.target === overlay){
      window.cerrarPdfModal();
    }
  });
})();
