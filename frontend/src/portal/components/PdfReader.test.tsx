// IP of Webby-Soft SRL.
// Audit S2-6: a zoom change or closing the reader cancels the page drawing in progress, and a
// stopped drawing never shows the error state.
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { PdfReader } from "./PdfReader";

type Job = { scale: number; cancelled: boolean; resolve: () => void; reject: (error: Error) => void };
const jobs: Job[] = [];

// No canvas in jsdom: each drawing waits until the test ends it.
vi.mock("./pdf/pdfEngine", () => ({
  openPdf: async () => ({
    numPages: 1,
    renderPage: (_page: number, _canvas: HTMLCanvasElement, scale: number) => {
      let resolve: () => void = () => undefined;
      let reject: (error: Error) => void = () => undefined;
      const promise = new Promise<void>((done, fail) => {
        resolve = done;
        reject = fail;
      });
      const job: Job = { scale, cancelled: false, resolve, reject };
      jobs.push(job);
      return {
        promise,
        cancel: () => {
          job.cancelled = true;
          // Like PDF.js: a cancelled drawing rejects.
          reject(new Error("Rendering cancelled"));
        }
      };
    },
    destroy: () => undefined
  })
}));

test("rapid zoom changes cancel the drawings in progress without an error; Close cancels the last", async () => {
  const onClose = vi.fn();
  const { unmount } = render(
    <PdfReader load={async () => ({ data: new Uint8Array([1]), filename: "statement.pdf" })} onClose={onClose} title="Statement" />
  );
  const reader = await screen.findByRole("dialog", { name: "Statement" });
  expect(await within(reader).findByText("1 page")).toBeInTheDocument();
  expect(jobs.map((job) => job.scale)).toEqual([1]);

  // Two clicks while the first page is still drawing.
  fireEvent.click(within(reader).getByRole("button", { name: "Zoom in" }));
  fireEvent.click(within(reader).getByRole("button", { name: "Zoom out" }));
  expect(jobs.map((job) => job.scale)).toEqual([1, 1.25, 1]);
  expect(jobs.map((job) => job.cancelled)).toEqual([true, true, false]);
  await act(async () => {
    await Promise.resolve();
  });
  expect(within(reader).queryByRole("alert")).not.toBeInTheDocument();

  // The current drawing ends; the page stays.
  await act(async () => {
    jobs[2].resolve();
    await Promise.resolve();
  });
  expect(within(reader).getByRole("img", { name: "Page 1" })).toBeInTheDocument();

  // A new drawing still in progress when the reader closes is cancelled.
  fireEvent.click(within(reader).getByRole("button", { name: "Zoom in" }));
  unmount();
  expect(jobs.at(-1)).toMatchObject({ scale: 1.25, cancelled: true });
});

test("a failure of the current drawing still shows the error with Try again", async () => {
  jobs.length = 0;
  render(<PdfReader load={async () => ({ data: new Uint8Array([1]), filename: "x.pdf" })} onClose={() => undefined} title="Broken" />);
  const reader = await screen.findByRole("dialog", { name: "Broken" });
  await within(reader).findByText("1 page");
  await act(async () => {
    jobs[0].reject(new Error("Invalid PDF"));
    await Promise.resolve();
  });
  expect(within(reader).getByRole("alert")).toHaveTextContent("The document could not be shown.");
  expect(within(reader).getByRole("button", { name: "Try again" })).toBeInTheDocument();
});
