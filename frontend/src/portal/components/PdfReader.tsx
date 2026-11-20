// IP of Webby-Soft SRL.
/*
 * 18.3: the in-app PDF reader (design: the document modal, .modal-lg > .bxm-doc with "Download PDF"
 * and "Close"). Pages one under the other, zoom out / in, the page count, download, an error with
 * "Try again", Escape or Close; focus goes back to what opened it (Dialog). Used for credit-file
 * documents, Documents and Reports. The file is loaded by the caller (`load`), so the reader never
 * knows where it comes from.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { useT } from "../../i18n";
import { Dialog } from "./Dialog";
import { NiIcon } from "./Icon";
import type { PdfDocumentHandle } from "./pdf/pdfEngine";

export type PdfFile = { data: Uint8Array; filename: string };

const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2];

function saveFile(file: PdfFile) {
  const url = window.URL.createObjectURL(new Blob([file.data as BlobPart], { type: "application/pdf" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = file.filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

function PdfPage({ handle, pageNumber, scale, onError }: { handle: PdfDocumentHandle; pageNumber: number; scale: number; onError: () => void }) {
  const t = useT();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvasRef.current) return;
    // Audit S2-6: a new zoom (or closing) cancels the drawing in progress; only the current
    // drawing can show the error.
    let current = true;
    const job = handle.renderPage(pageNumber, canvasRef.current, scale);
    job.promise.catch(() => {
      if (current) onError();
    });
    return () => {
      current = false;
      job.cancel();
    };
  }, [handle, pageNumber, scale, onError]);
  return <canvas aria-label={t("Page {page}", { page: pageNumber })} className="u33-pdf-page" ref={canvasRef} role="img" />;
}

export function PdfReader({ title, load, onClose }: { title: string; load: () => Promise<PdfFile>; onClose: () => void }) {
  const t = useT();
  const [file, setFile] = useState<PdfFile | null>(null);
  const [handle, setHandle] = useState<PdfDocumentHandle | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [zoom, setZoom] = useState(2);
  const markFailed = useCallback(() => setFailed(true), []);
  // The file of this reader: taken once when it opens (a reader shows one document).
  const [loader] = useState(() => load);

  useEffect(() => {
    let cancelled = false;
    let opened: PdfDocumentHandle | null = null;
    setFailed(false);
    setHandle(null);
    loader()
      .then(async (loaded) => {
        if (cancelled) return;
        setFile(loaded);
        const engine = await import("./pdf/pdfEngine");
        opened = await engine.openPdf(loaded.data);
        if (cancelled) opened.destroy();
        else setHandle(opened);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      opened?.destroy();
    };
  }, [loader, attempt]);

  const scale = ZOOMS[zoom];
  const footer = (
    <>
      <button className="btn btn-primary" disabled={!file} onClick={() => file && saveFile(file)} type="button">
        <NiIcon name="download" /><span>{t("Download PDF")}</span>
      </button>
      <button className="btn btn-outline-light" onClick={onClose} type="button">{t("Close")}</button>
    </>
  );
  return (
    <Dialog className="u33-pdf-reader" footer={footer} onClose={onClose} size="lg" title={title}>
      <div aria-label={t("Document view")} className="u33-pdf-toolbar" role="toolbar">
        <span aria-live="polite">{handle ? (handle.numPages === 1 ? t("1 page") : t("{count} pages", { count: handle.numPages })) : ""}</span>
        <span className="u33-pdf-zoom">
          <button aria-label={t("Zoom out")} disabled={!handle || zoom === 0} onClick={() => setZoom((value) => Math.max(0, value - 1))} type="button"><NiIcon name="minus" /></button>
          <output aria-live="polite">{`${Math.round(scale * 100)}%`}</output>
          <button aria-label={t("Zoom in")} disabled={!handle || zoom === ZOOMS.length - 1} onClick={() => setZoom((value) => Math.min(ZOOMS.length - 1, value + 1))} type="button"><NiIcon name="plus" /></button>
        </span>
      </div>
      <div className="bxm-doc u33-pdf-pages" tabIndex={0}>
        {failed ? (
          <div className="bxm-empty" role="alert">
            <NiIcon name="alert-circle" />
            <p>{t("The document could not be shown.")}</p>
            <button className="btn btn-outline-light" onClick={() => setAttempt((value) => value + 1)} type="button">{t("Try again")}</button>
          </div>
        ) : handle ? (
          Array.from({ length: handle.numPages }, (_, index) => <PdfPage handle={handle} key={index} onError={markFailed} pageNumber={index + 1} scale={scale} />)
        ) : (
          <div className="bxm-empty" role="status"><NiIcon name="loader" /><p>{t("Loading document...")}</p></div>
        )}
      </div>
    </Dialog>
  );
}
