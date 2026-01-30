(function(){
  const dataEl = document.getElementById("pdf-modal-data");
  if (!dataEl) return;

  const URL_PDF_BASE = dataEl.dataset.urlBase || "";
  const URL_PAGES_BASE = dataEl.dataset.urlPages || "";

  let pdfDoc = null;
  let currentNumero = null;
  let selectedPages = new Set();

  function buildPdfUrl(numero){
    return URL_PDF_BASE.replace("/0", "/" + String(numero));
  }
  function buildPagesUrl(numero, pages, download){
    const base = URL_PAGES_BASE.replace("/0", "/" + String(numero));
    const params = new URLSearchParams();
    params.set("pages", pages.join(","));
    if (download) params.set("download", "1");
    return base + "?" + params.toString();
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
      thumbs.appendChild(wrap);

      if (i === 1){
        await renderPreview(1);
      }
    }
  }

  function updateSelectedActions(){
    const actions = document.getElementById("pdfSelectedActions");
    if (!actions) return;
    actions.style.display = selectedPages.size > 0 ? "flex" : "none";
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

    const url = buildPdfUrl(numero);
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
    window.open(buildPdfUrl(currentNumero), "_blank", "noopener");
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

  document.addEventListener("click", function(e){
    const overlay = document.getElementById("pdfModalOverlay");
    if (e.target === overlay){
      window.cerrarPdfModal();
    }
  });
})();
