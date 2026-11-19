// IP of Webby-Soft SRL.
// 18.3: the in-app PDF reader's engine (pdfjs-dist, Apache-2.0), loaded only when a document is
// opened so it stays out of the main bundle. Tests replace this module (no canvas in jsdom).
export type PdfDocumentHandle = {
  numPages: number;
  /** Draws one page (1-based) into the canvas at the zoom (1 = 100%). */
  renderPage: (pageNumber: number, canvas: HTMLCanvasElement, scale: number) => Promise<void>;
  destroy: () => void;
};

export async function openPdf(data: Uint8Array): Promise<PdfDocumentHandle> {
  const pdfjs = await import("pdfjs-dist");
  if (!pdfjs.GlobalWorkerOptions.workerSrc) {
    pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
  }
  // A copy: the engine takes ownership of the buffer it gets.
  const task = pdfjs.getDocument({ data: data.slice() });
  const document = await task.promise;
  return {
    numPages: document.numPages,
    renderPage: async (pageNumber, canvas, scale) => {
      const page = await document.getPage(pageNumber);
      const ratio = window.devicePixelRatio || 1;
      const viewport = page.getViewport({ scale: scale * ratio });
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = `${Math.floor(viewport.width / ratio)}px`;
      canvas.style.height = `${Math.floor(viewport.height / ratio)}px`;
      await page.render({ canvas, viewport }).promise;
    },
    destroy: () => void task.destroy()
  };
}
