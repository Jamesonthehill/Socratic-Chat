import { useEffect, useRef, useState } from "react";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

export default function PdfMaterialPreview({ blob, title, focusPage, focusTerm, zoom }) {
  const [document, setDocument] = useState(null);
  const [pageNumber, setPageNumber] = useState(focusPage || 1);
  const [width, setWidth] = useState(0);
  const [error, setError] = useState("");
  const [match, setMatch] = useState(null);
  const viewportRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let loadingTask;
    setDocument(null);
    setError("");
    setMatch(null);
    (async () => {
      try {
        const { getDocument, GlobalWorkerOptions } = await import("pdfjs-dist");
        GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
        loadingTask = getDocument({ data: new Uint8Array(await blob.arrayBuffer()) });
        const pdf = await loadingTask.promise;
        if (cancelled) { await pdf.destroy(); return; }
        setDocument(pdf);
      } catch {
        if (!cancelled) setError("This PDF could not be displayed. Use Download to open the original file.");
      }
    })();
    return () => {
      cancelled = true;
      loadingTask?.destroy();
    };
  }, [blob]);

  useEffect(() => { setPageNumber(focusPage || 1); }, [focusPage, blob]);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const updateWidth = () => setWidth(element.clientWidth);
    updateWidth();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(updateWidth);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!document || !width || !canvasRef.current) return;
    let cancelled = false;
    let renderTask;
    setMatch(null);
    (async () => {
      try {
        const page = await document.getPage(Math.min(pageNumber, document.numPages));
        if (cancelled) return;
        const naturalWidth = page.getViewport({ scale: 1 }).width;
        const scale = ((width - 32) / naturalWidth) * (zoom / 100);
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current;
        const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.floor(viewport.width * pixelRatio);
        canvas.height = Math.floor(viewport.height * pixelRatio);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        renderTask = page.render({
          canvas,
          canvasContext: canvas.getContext("2d"),
          viewport,
          transform: [pixelRatio, 0, 0, pixelRatio, 0, 0],
        });
        await renderTask.promise;
        if (cancelled || !focusTerm) return;
        const content = await page.getTextContent();
        const items = content.items.filter((item) => typeof item.str === "string");
        const fullText = items.map((item) => item.str).join(" ");
        const start = fullText.toLocaleLowerCase().indexOf(focusTerm.toLocaleLowerCase());
        if (start < 0 || cancelled) return;
        let offset = 0;
        for (const item of items) {
          const itemStart = offset;
          offset += item.str.length + 1;
          if (start >= offset) continue;
          const transform = viewport.transform;
          const x = transform[0] * item.transform[4] + transform[2] * item.transform[5] + transform[4];
          const baseline = transform[1] * item.transform[4] + transform[3] * item.transform[5] + transform[5];
          const height = Math.max(12, Math.abs(item.height * scale));
          const width = Math.max(24, item.width * scale);
          const result = { left: x, top: baseline - height, width, height };
          if (!cancelled) {
            setMatch(result);
            const scrollport = viewportRef.current?.closest(".material-preview-viewport");
            if (scrollport) scrollport.scrollTop = Math.max(0, result.top - 100);
          }
          break;
        }
      } catch (failure) {
        if (!cancelled && failure?.name !== "RenderingCancelledException") {
          setError("This PDF page could not be displayed. Use Download to open the original file.");
        }
      }
    })();
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [document, pageNumber, width, zoom, focusTerm]);

  const totalPages = document?.numPages || 0;
  const shownPage = Math.min(pageNumber, totalPages || pageNumber);
  return (
    <div className="material-preview-pdf" ref={viewportRef}>
      {error ? <p role="alert" className="material-preview-unavailable">{error}</p> : <>
        {totalPages > 1 && <div className="material-preview-pages" role="group" aria-label="PDF pages">
          <button type="button" className="secondary compact" disabled={shownPage <= 1}
            onClick={() => setPageNumber((page) => Math.max(1, page - 1))}>Previous page</button>
          <span>Page {shownPage} of {totalPages}</span>
          <button type="button" className="secondary compact" disabled={shownPage >= totalPages}
            onClick={() => setPageNumber((page) => Math.min(totalPages, page + 1))}>Next page</button>
        </div>}
        {!document && <p role="status" className="material-preview-loading">Opening PDF…</p>}
        <div className="material-preview-page">
          <canvas ref={canvasRef} aria-label={`${title}, page ${shownPage}`} />
          {match && <span className="material-preview-match" aria-hidden="true" style={match} />}
        </div>
      </>}
    </div>
  );
}
