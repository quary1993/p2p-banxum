import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { StoryEditor } from "./StoryEditor";
import type { StoryDocument } from "../investorPortal/story";

function typeInto(element: HTMLElement, text: string) {
  element.replaceChildren(document.createTextNode(text));
  fireEvent.input(element);
}

test("story editor seeds from a document and emits whitelisted runs only", () => {
  const onChange = vi.fn<(next: StoryDocument) => void>();
  render(
    <StoryEditor
      onChange={onChange}
      value={{
        version: 1,
        blocks: [
          { type: "heading", level: 2, runs: [{ text: "About us" }] },
          { type: "paragraph", runs: [{ text: "Family " }, { text: "bakery", bold: true }, { text: " since 1987", href: "https://example.test" }] }
        ]
      }}
    />
  );

  const heading = screen.getByRole("textbox", { name: "Heading" });
  expect(heading.tagName).toBe("H2");
  expect(heading).toHaveTextContent("About us");
  const paragraphs = screen.getAllByRole("textbox", { name: /Continue writing|Tell investors/ });
  const body = paragraphs[0];
  expect(body.querySelector("strong")).toHaveTextContent("bakery");
  expect(body.querySelector("a")).toHaveAttribute("href", "https://example.test");

  // Markup that sneaks into the DOM (e.g. via a browser extension) is parsed through the whitelist.
  body.replaceChildren();
  const span = document.createElement("span");
  span.setAttribute("onclick", "alert(1)");
  span.textContent = "safe ";
  const bold = document.createElement("b");
  bold.textContent = "text";
  const badLink = document.createElement("a");
  badLink.setAttribute("href", "javascript:alert(1)");
  badLink.textContent = " evil";
  const script = document.createElement("script");
  script.type = "application/x-test-inert";
  script.textContent = "alert(1)";
  body.append(span, bold, badLink, script);
  fireEvent.input(body);

  const last = onChange.mock.calls.at(-1)?.[0];
  expect(last?.blocks[1]).toEqual({ type: "paragraph", runs: [{ text: "safe " }, { text: "text", bold: true }, { text: " evil" }] });
  expect(JSON.stringify(last)).not.toContain("onclick");
  expect(JSON.stringify(last)).not.toContain("javascript:");
});

test("story editor inserts blocks from the plus menu and uploads images through the pipeline", async () => {
  const onChange = vi.fn<(next: StoryDocument) => void>();
  const uploadImage = vi.fn(async (file: File) => {
    expect(file.name).toBe("shop.png");
    return { id: "6f1d2c3e-4b5a-4c6d-8e9f-0a1b2c3d4e5f", url: "/api/v1/story-images/6f1d2c3e-4b5a-4c6d-8e9f-0a1b2c3d4e5f/" };
  });
  render(<StoryEditor onChange={onChange} uploadImage={uploadImage} value={undefined} />);

  // Empty editor: one placeholder paragraph, plus menu converts it into a heading.
  const first = screen.getByRole("textbox", { name: "Tell investors the story…" });
  fireEvent.click(screen.getByRole("button", { name: "Add block here" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Heading" }));
  const heading = screen.getByRole("textbox", { name: "Heading" });
  typeInto(heading, "Who we are");
  expect(first).not.toBeInTheDocument();

  // A trailing paragraph is always available; use it for a bullet list.
  const trailing = screen.getByRole("textbox", { name: /Continue writing/ });
  fireEvent.click(screen.getAllByRole("button", { name: /Add block/ })[1]);
  fireEvent.click(screen.getByRole("menuitem", { name: "Bullet list" }));
  typeInto(screen.getByRole("textbox", { name: "List item" }), "Founded 1987");
  expect(trailing).not.toBeInTheDocument();

  // Image upload from the plus menu of the new trailing paragraph.
  fireEvent.click(screen.getAllByRole("button", { name: /Add block/ }).at(-1)!);
  fireEvent.click(screen.getByRole("menuitem", { name: "Image" }));
  const fileInput = screen.getByLabelText("Upload story image") as HTMLInputElement;
  const file = new File([new Uint8Array([137, 80, 78, 71])], "shop.png", { type: "image/png" });
  await act(async () => {
    fireEvent.change(fileInput, { target: { files: [file] } });
  });
  await waitFor(() => expect(document.querySelector("img.se-img")).toHaveAttribute("src", "/api/v1/story-images/6f1d2c3e-4b5a-4c6d-8e9f-0a1b2c3d4e5f/"));
  fireEvent.change(screen.getByLabelText("Image caption"), { target: { value: "Our shop" } });
  fireEvent.change(screen.getByLabelText("Image description for screen readers"), { target: { value: "Bakery storefront" } });

  const last = onChange.mock.calls.at(-1)?.[0];
  expect(last).toEqual({
    version: 1,
    blocks: [
      { type: "heading", level: 2, runs: [{ text: "Who we are" }] },
      { type: "bullet_list", items: [[{ text: "Founded 1987" }]] },
      { type: "image", image_id: "6f1d2c3e-4b5a-4c6d-8e9f-0a1b2c3d4e5f", alt: "Bakery storefront", caption: "Our shop" }
    ]
  });
  expect(uploadImage).toHaveBeenCalledTimes(1);

  // Rejected uploads never reach the document.
  const failing = vi.fn(async () => {
    throw new Error("The file is not a valid image.");
  });
  render(<StoryEditor onChange={onChange} uploadImage={failing} value={undefined} />);
  const editors = screen.getAllByRole("group", { name: "Investor story" });
  const second = editors[1];
  fireEvent.click(second.querySelector("button.se-plus")!);
  fireEvent.click(screen.getByRole("menuitem", { name: "Image" }));
  await act(async () => {
    fireEvent.change(second.querySelector("input[type=file]")!, { target: { files: [new File(["<script>"], "evil.png", { type: "image/png" })] } });
  });
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("The file is not a valid image."));
  expect(onChange.mock.calls.at(-1)?.[0]).toEqual({ version: 1, blocks: [] });
});

test("link editing never submits the enclosing borrower form", () => {
  const submit = vi.fn((event: React.FormEvent) => event.preventDefault());
  render(<form onSubmit={submit}><StoryEditor onChange={vi.fn()} value={{ version: 1, blocks: [
    { type: "paragraph", runs: [{ text: "Example link" }] }
  ] }} /></form>);
  const editor = screen.getByRole("textbox", { name: "Tell investors the story…" });
  fireEvent.focus(editor);
  const range = document.createRange();
  range.selectNodeContents(editor);
  range.getBoundingClientRect = () => new DOMRect(40, 80, 100, 20);
  const selection = window.getSelection()!;
  selection.removeAllRanges();
  selection.addRange(range);
  fireEvent(document, new Event("selectionchange"));
  fireEvent.click(screen.getByRole("button", { name: "Link" }));
  expect(document.querySelectorAll("form")).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("Link URL"), { target: { value: "https://example.test" } });
  fireEvent.keyDown(screen.getByLabelText("Link URL"), { key: "Enter" });
  expect(submit).not.toHaveBeenCalled();
  expect(screen.queryByLabelText("Link URL")).not.toBeInTheDocument();
  selection.removeAllRanges();
});

test("unfinished or failed image uploads prevent the containing form from saving", async () => {
  let failUpload: (error: Error) => void = () => {};
  const uploadImage = vi.fn(() => new Promise<{ id: string; url: string }>((_resolve, reject) => { failUpload = reject; }));
  const ready = vi.fn();
  render(<StoryEditor onChange={vi.fn()} onReadyChange={ready} uploadImage={uploadImage} value={undefined} />);
  fireEvent.click(screen.getByRole("button", { name: "Add block here" }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Image" }));
  fireEvent.change(screen.getByLabelText("Upload story image"), { target: { files: [new File(["image"], "a.png", { type: "image/png" })] } });
  expect(ready).toHaveBeenLastCalledWith(false);
  await act(async () => failUpload(new Error("Upload failed")));
  expect(ready).toHaveBeenLastCalledWith(false);
  fireEvent.click(screen.getByRole("button", { name: "Remove image block" }));
  expect(ready).toHaveBeenLastCalledWith(true);
});
