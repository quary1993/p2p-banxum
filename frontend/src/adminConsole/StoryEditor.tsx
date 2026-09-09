import { createElement, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ClipboardEvent, type KeyboardEvent, type MouseEvent } from "react";
import {
  STORY_MAX_BLOCKS,
  STORY_MAX_TOTAL_CHARS,
  compactStory,
  isSafeStoryHref,
  normalizeStory,
  runsText,
  storyCharacterCount,
  type StoryBlock,
  type StoryDocument,
  type StoryRun
} from "../investorPortal/story";
import { rememberPreviewImageUrl, storyEditorImageUrl, uploadStoryImage, type StoryImageUploader } from "./storyImages";

// ---------------------------------------------------------------------------
// Editor model: story blocks with stable React keys.
// ---------------------------------------------------------------------------

type ListBlockType = "bullet_list" | "numbered_list";

type EditorItem = { key: string; runs: StoryRun[]; seed?: number };
type EditorBlock =
  | { key: string; type: "paragraph" | "quote"; runs: StoryRun[]; seed?: number }
  | { key: string; type: "heading"; level: 2 | 3; runs: StoryRun[]; seed?: number }
  | { key: string; type: ListBlockType; items: EditorItem[] }
  | { key: string; type: "image"; image_id: string; alt: string; caption: string; uploading?: boolean; error?: string }
  | { key: string; type: "divider" };

type CaretPosition = "start" | "end" | number;
type FocusRequest = { key: string; itemKey?: string; position: CaretPosition; nonce: number };

let keyCounter = 0;
function nextKey() {
  keyCounter += 1;
  return `sb${keyCounter}`;
}

function paragraph(runs: StoryRun[] = []): EditorBlock {
  return { key: nextKey(), type: "paragraph", runs };
}

function fromDocument(story: StoryDocument): EditorBlock[] {
  return story.blocks.map((block): EditorBlock => {
    switch (block.type) {
      case "paragraph":
      case "quote":
        return { key: nextKey(), type: block.type, runs: block.runs };
      case "heading":
        return { key: nextKey(), type: "heading", level: block.level, runs: block.runs };
      case "bullet_list":
      case "numbered_list":
        return { key: nextKey(), type: block.type, items: block.items.map((runs) => ({ key: nextKey(), runs })) };
      case "image":
        return { key: nextKey(), type: "image", image_id: block.image_id, alt: block.alt, caption: block.caption };
      case "divider":
        return { key: nextKey(), type: "divider" };
    }
  });
}

function toDocument(blocks: EditorBlock[]): StoryDocument {
  const out: StoryBlock[] = [];
  for (const block of blocks) {
    switch (block.type) {
      case "paragraph":
      case "quote":
        out.push({ type: block.type, runs: block.runs });
        break;
      case "heading":
        out.push({ type: "heading", level: block.level, runs: block.runs });
        break;
      case "bullet_list":
      case "numbered_list":
        out.push({ type: block.type, items: block.items.map((item) => item.runs) });
        break;
      case "image":
        if (!block.uploading && !block.error) out.push({ type: "image", image_id: block.image_id, alt: block.alt, caption: block.caption });
        break;
      case "divider":
        out.push({ type: "divider" });
        break;
    }
  }
  return compactStory({ version: 1, blocks: out });
}

function isTextBlock(block: EditorBlock | undefined): block is Extract<EditorBlock, { runs: StoryRun[] }> {
  return !!block && (block.type === "paragraph" || block.type === "quote" || block.type === "heading");
}

function isListBlock(block: EditorBlock | undefined): block is Extract<EditorBlock, { items: EditorItem[] }> {
  return !!block && (block.type === "bullet_list" || block.type === "numbered_list");
}

function blockIsEmpty(block: EditorBlock) {
  if (isTextBlock(block)) return runsText(block.runs).trim() === "";
  if (isListBlock(block)) return block.items.every((item) => runsText(item.runs).trim() === "");
  return false;
}

// ---------------------------------------------------------------------------
// Runs <-> DOM. The DOM is only ever built from runs (createElement, never
// innerHTML) and parsed back through a whitelist, so pasted or injected markup
// can never survive a round-trip.
// ---------------------------------------------------------------------------

function runsToNodes(runs: StoryRun[]): Node[] {
  const nodes: Node[] = [];
  for (const run of runs) {
    const parts = run.text.split("\n");
    parts.forEach((part, index) => {
      if (index > 0) nodes.push(document.createElement("br"));
      if (part === "") return;
      let node: Node = document.createTextNode(part);
      if (run.bold) {
        const strong = document.createElement("strong");
        strong.appendChild(node);
        node = strong;
      }
      if (run.italic) {
        const em = document.createElement("em");
        em.appendChild(node);
        node = em;
      }
      if (run.href) {
        const anchor = document.createElement("a");
        anchor.setAttribute("href", run.href);
        anchor.appendChild(node);
        node = anchor;
      }
      nodes.push(node);
    });
  }
  return nodes;
}

type RunFormat = { bold?: boolean; italic?: boolean; href?: string };

function sameFormat(a: RunFormat, b: RunFormat) {
  return !!a.bold === !!b.bold && !!a.italic === !!b.italic && (a.href ?? "") === (b.href ?? "");
}

function nodesToRuns(root: Node): StoryRun[] {
  const runs: StoryRun[] = [];
  const push = (text: string, format: RunFormat) => {
    if (text === "") return;
    const last = runs[runs.length - 1];
    if (last && sameFormat(last, format)) {
      last.text += text;
      return;
    }
    const run: StoryRun = { text };
    if (format.bold) run.bold = true;
    if (format.italic) run.italic = true;
    if (format.href) run.href = format.href;
    runs.push(run);
  };
  const walk = (node: Node, format: RunFormat) => {
    if (node.nodeType === Node.TEXT_NODE) {
      push((node.textContent ?? "").replace(/\u00a0/g, " "), format);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const element = node as HTMLElement;
    const tag = element.tagName.toLowerCase();
    if (tag === "br") {
      push("\n", format);
      return;
    }
    if (tag === "script" || tag === "style" || tag === "template" || tag === "img" || tag === "iframe") return;
    const next: RunFormat = { ...format };
    const weight = element.style?.fontWeight ?? "";
    if (tag === "b" || tag === "strong" || weight === "bold" || weight === "bolder" || Number(weight) >= 600) next.bold = true;
    if (tag === "i" || tag === "em" || element.style?.fontStyle === "italic") next.italic = true;
    if (tag === "a") {
      const href = element.getAttribute("href") ?? "";
      if (isSafeStoryHref(href)) next.href = href.trim();
    }
    const blockish = tag === "div" || tag === "p" || tag === "li" || tag === "h1" || tag === "h2" || tag === "h3";
    if (blockish && runs.length > 0 && !runs[runs.length - 1].text.endsWith("\n")) push("\n", format);
    element.childNodes.forEach((child) => walk(child, next));
  };
  root.childNodes.forEach((child) => walk(child, {}));
  // Browsers keep a trailing <br> in contenteditable; it is not content.
  const last = runs[runs.length - 1];
  if (last && last.text.endsWith("\n")) {
    last.text = last.text.slice(0, -1);
    if (last.text === "") runs.pop();
  }
  return runs;
}

function placeCaret(element: HTMLElement, position: CaretPosition) {
  const selection = window.getSelection();
  if (!selection) return;
  const range = document.createRange();
  if (typeof position === "number") {
    let remaining = position;
    let placed = false;
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      const length = node.textContent?.length ?? 0;
      if (remaining <= length) {
        range.setStart(node, remaining);
        range.collapse(true);
        placed = true;
        break;
      }
      remaining -= length;
      node = walker.nextNode();
    }
    if (!placed) {
      range.selectNodeContents(element);
      range.collapse(false);
    }
  } else {
    range.selectNodeContents(element);
    range.collapse(position === "start");
  }
  selection.removeAllRanges();
  selection.addRange(range);
}

function caretOffsetForJoin(runs: StoryRun[]) {
  return runsText(runs).replace(/\n/g, "").length;
}

function caretAtStart(element: HTMLElement) {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || !selection.isCollapsed) return false;
  const range = selection.getRangeAt(0);
  if (!element.contains(range.startContainer)) return false;
  const before = document.createRange();
  before.selectNodeContents(element);
  before.setEnd(range.startContainer, range.startOffset);
  const fragment = before.cloneContents();
  return before.toString().length === 0 && fragment.querySelector("br") === null;
}

/** Splits the editable at the caret; returns the runs after the caret and removes them from the DOM. */
function extractAfterCaret(element: HTMLElement): StoryRun[] {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return [];
  const range = selection.getRangeAt(0);
  if (!element.contains(range.startContainer)) return [];
  range.deleteContents();
  if (!element.lastChild) return [];
  const after = document.createRange();
  after.setStart(range.startContainer, range.startOffset);
  after.setEndAfter(element.lastChild);
  const container = document.createElement("div");
  container.appendChild(after.extractContents());
  return nodesToRuns(container);
}

function execCommand(command: string, value?: string) {
  if (typeof document.execCommand !== "function") return false;
  return document.execCommand(command, false, value);
}

function syncEditable(element: HTMLElement | null) {
  element?.dispatchEvent(new Event("input", { bubbles: true }));
}

function editableFromSelection(root: HTMLElement | null) {
  const selection = window.getSelection();
  if (!root || !selection || selection.rangeCount === 0) return null;
  const node = selection.getRangeAt(0).startContainer;
  const element = node.nodeType === Node.ELEMENT_NODE ? (node as HTMLElement) : node.parentElement;
  const editable = element?.closest<HTMLElement>("[data-story-editable]") ?? null;
  return editable && root.contains(editable) ? editable : null;
}

// ---------------------------------------------------------------------------
// Editable text surface
// ---------------------------------------------------------------------------

type EditableTextProps = {
  tag: "p" | "h2" | "h3" | "blockquote" | "li";
  blockKey: string;
  itemKey?: string;
  runs: StoryRun[];
  seed?: number;
  placeholder: string;
  focusRequest: FocusRequest | null;
  onRunsChange: (runs: StoryRun[]) => void;
  onSplit: (before: StoryRun[], after: StoryRun[]) => void;
  onBackspaceAtStart: (runs: StoryRun[]) => void;
  onPasteLines: (lines: string[]) => void;
  onFocusBlock: () => void;
};

function EditableText({ tag, blockKey, itemKey, runs, seed = 0, placeholder, focusRequest, onRunsChange, onSplit, onBackspaceAtStart, onPasteLines, onFocusBlock }: EditableTextProps) {
  const ref = useRef<HTMLElement | null>(null);
  const runsRef = useRef(runs);
  runsRef.current = runs;

  // The DOM is seeded from runs on mount and whenever the editor changes the
  // block from outside (merges, conversions). Ordinary typing flows DOM → runs.
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    element.replaceChildren(...runsToNodes(runsRef.current));
    element.dataset.empty = element.textContent === "" ? "true" : "false";
  }, [seed]);

  useEffect(() => {
    const element = ref.current;
    if (!element || !focusRequest) return;
    if (focusRequest.key !== blockKey || (focusRequest.itemKey ?? undefined) !== itemKey) return;
    element.focus();
    placeCaret(element, focusRequest.position);
  }, [focusRequest, blockKey, itemKey]);

  const handleInput = () => {
    const element = ref.current;
    if (!element) return;
    element.dataset.empty = element.textContent === "" ? "true" : "false";
    onRunsChange(nodesToRuns(element));
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    const element = ref.current;
    if (!element) return;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const after = extractAfterCaret(element);
      element.dataset.empty = element.textContent === "" ? "true" : "false";
      onSplit(nodesToRuns(element), after);
      return;
    }
    if (event.key === "Enter" && event.shiftKey) {
      event.preventDefault();
      if (!execCommand("insertLineBreak")) execCommand("insertHTML", "<br>");
      handleInput();
      return;
    }
    if (event.key === "Backspace" && caretAtStart(element)) {
      event.preventDefault();
      onBackspaceAtStart(nodesToRuns(element));
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLElement>) => {
    event.preventDefault();
    const text = event.clipboardData.getData("text/plain").replace(/\r\n?/g, "\n");
    const lines = text.split(/\n{2,}|\n/).map((line) => line.trim()).filter((line) => line !== "");
    if (lines.length === 0) return;
    if (!execCommand("insertText", lines[0])) {
      ref.current?.appendChild(document.createTextNode(lines[0]));
    }
    handleInput();
    if (lines.length > 1) onPasteLines(lines.slice(1));
  };

  return createElement(tag, {
    className: `se-text se-${tag}`,
    contentEditable: true,
    "data-placeholder": placeholder,
    "data-story-editable": "true",
    onFocus: onFocusBlock,
    onInput: handleInput,
    onKeyDown: handleKeyDown,
    onPaste: handlePaste,
    ref: (node: HTMLElement | null) => {
      ref.current = node;
    },
    role: "textbox",
    "aria-label": placeholder,
    "aria-multiline": true,
    spellCheck: true,
    suppressContentEditableWarning: true
  });
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------

type InsertKind = "paragraph" | "heading" | "subheading" | "quote" | "bullet_list" | "numbered_list" | "image" | "divider";

const INSERT_OPTIONS: Array<{ kind: InsertKind; label: string; glyph: string }> = [
  { kind: "paragraph", label: "Text", glyph: "T" },
  { kind: "heading", label: "Heading", glyph: "H" },
  { kind: "subheading", label: "Subheading", glyph: "h" },
  { kind: "quote", label: "Quote", glyph: "“" },
  { kind: "bullet_list", label: "Bullet list", glyph: "•" },
  { kind: "numbered_list", label: "Numbered list", glyph: "1." },
  { kind: "image", label: "Image", glyph: "▣" },
  { kind: "divider", label: "Divider", glyph: "—" }
];

export function StoryEditor({
  value,
  onChange,
  label = "Investor story",
  hint,
  onReadyChange,
  uploadImage = uploadStoryImage
}: {
  value: unknown;
  onChange: (next: StoryDocument) => void;
  label?: string;
  hint?: string;
  onReadyChange?: (ready: boolean) => void;
  uploadImage?: StoryImageUploader;
}) {
  const [blocks, setBlocks] = useState<EditorBlock[]>(() => {
    const initial = fromDocument(normalizeStory(value));
    const last = initial[initial.length - 1];
    if (!last || !(isTextBlock(last) && last.type === "paragraph" && blockIsEmpty(last))) initial.push(paragraph());
    return initial;
  });
  const [focus, setFocus] = useState<FocusRequest | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [toolbar, setToolbar] = useState<{ top: number; left: number } | null>(null);
  const [linkDraft, setLinkDraft] = useState<{ value: string; error: string } | null>(null);
  const linkDraftRef = useRef(linkDraft);
  linkDraftRef.current = linkDraft;
  const savedRange = useRef<Range | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pendingImageTarget = useRef<string | null>(null);
  const focusNonce = useRef(0);

  const document_ = useMemo(() => toDocument(blocks), [blocks]);
  const characterCount = storyCharacterCount(document_);
  const ready = characterCount <= STORY_MAX_TOTAL_CHARS && document_.blocks.length <= STORY_MAX_BLOCKS
    && !blocks.some((block) => block.type === "image" && (block.uploading || block.error));
  useEffect(() => { onReadyChange?.(ready); }, [onReadyChange, ready]);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  useEffect(() => {
    onChangeRef.current(document_);
  }, [document_]);

  const requestFocus = useCallback((key: string, position: CaretPosition, itemKey?: string) => {
    focusNonce.current += 1;
    setFocus({ key, itemKey, position, nonce: focusNonce.current });
    setActiveKey(key);
  }, []);

  const commit = useCallback((updater: (current: EditorBlock[]) => EditorBlock[]) => {
    setBlocks((current) => {
      const next = updater(current);
      const last = next[next.length - 1];
      if (!last || !(isTextBlock(last) && last.type === "paragraph" && blockIsEmpty(last))) return [...next, paragraph()];
      return next;
    });
  }, []);

  // --- text block callbacks -------------------------------------------------

  const updateRuns = (key: string, runs: StoryRun[], itemKey?: string) => {
    setBlocks((current) =>
      current.map((block) => {
        if (block.key !== key) return block;
        if (isTextBlock(block)) return { ...block, runs };
        if (isListBlock(block) && itemKey) return { ...block, items: block.items.map((item) => (item.key === itemKey ? { ...item, runs } : item)) };
        return block;
      })
    );
  };

  const splitBlock = (key: string, before: StoryRun[], after: StoryRun[], itemKey?: string) => {
    let focusKey = "";
    let focusItem: string | undefined;
    commit((current) => {
      const index = current.findIndex((block) => block.key === key);
      if (index < 0) return current;
      const block = current[index];
      const next = [...current];
      if (isTextBlock(block)) {
        // Heading/quote → new paragraph; paragraph → paragraph (Medium behaviour).
        const created = paragraph(after);
        next[index] = { ...block, runs: before };
        next.splice(index + 1, 0, created);
        focusKey = created.key;
      } else if (isListBlock(block) && itemKey) {
        const itemIndex = block.items.findIndex((item) => item.key === itemKey);
        const currentItem = block.items[itemIndex];
        if (runsText(before).trim() === "" && runsText(after).trim() === "" && itemIndex === block.items.length - 1) {
          // Enter on a trailing empty item leaves the list.
          const created = paragraph();
          if (block.items.length > 1) next.splice(index, 1, { ...block, items: block.items.slice(0, itemIndex) }, created);
          else next.splice(index, 1, created);
          focusKey = created.key;
        } else if (currentItem) {
          const createdItem: EditorItem = { key: nextKey(), runs: after };
          const items = [...block.items];
          items[itemIndex] = { ...currentItem, runs: before };
          items.splice(itemIndex + 1, 0, createdItem);
          next[index] = { ...block, items };
          focusKey = block.key;
          focusItem = createdItem.key;
        }
      }
      return next;
    });
    if (focusKey) requestFocus(focusKey, "start", focusItem);
  };

  const backspaceAtStart = (key: string, runs: StoryRun[], itemKey?: string) => {
    let focusKey = "";
    let focusItem: string | undefined;
    let focusPosition: CaretPosition = "end";
    commit((current) => {
      const index = current.findIndex((block) => block.key === key);
      if (index < 0) return current;
      const block = current[index];
      const next = [...current];
      if (isListBlock(block) && itemKey) {
        const itemIndex = block.items.findIndex((item) => item.key === itemKey);
        if (itemIndex === 0) {
          // Turn the first item back into a paragraph before the list.
          const created = paragraph(runs);
          const rest = block.items.slice(1);
          if (rest.length === 0) next.splice(index, 1, created);
          else next.splice(index, 1, created, { ...block, items: rest });
          focusKey = created.key;
          focusPosition = "start";
        } else {
          const previous = block.items[itemIndex - 1];
          const items = block.items.filter((item) => item.key !== itemKey);
          items[itemIndex - 1] = { ...previous, runs: [...previous.runs, ...runs], seed: (previous.seed ?? 0) + 1 };
          next[index] = { ...block, items };
          focusKey = block.key;
          focusItem = previous.key;
          focusPosition = caretOffsetForJoin(previous.runs);
        }
        return next;
      }
      if (!isTextBlock(block)) return current;
      if (block.type !== "paragraph") {
        next[index] = { key: block.key, type: "paragraph", runs };
        focusKey = block.key;
        focusPosition = "start";
        return next;
      }
      if (index === 0) return current;
      const previous = current[index - 1];
      if (isTextBlock(previous)) {
        next[index - 1] = { ...previous, runs: [...previous.runs, ...runs], seed: (previous.seed ?? 0) + 1 };
        next.splice(index, 1);
        focusKey = previous.key;
        focusPosition = caretOffsetForJoin(previous.runs);
      } else if (isListBlock(previous)) {
        const lastItem = previous.items[previous.items.length - 1];
        const items = [...previous.items];
        items[items.length - 1] = { ...lastItem, runs: [...lastItem.runs, ...runs], seed: (lastItem.seed ?? 0) + 1 };
        next[index - 1] = { ...previous, items };
        next.splice(index, 1);
        focusKey = previous.key;
        focusItem = lastItem.key;
        focusPosition = caretOffsetForJoin(lastItem.runs);
      } else if (runsText(runs) === "") {
        next.splice(index, 1);
        const target = next[index - 1];
        focusKey = target && (isTextBlock(target) || isListBlock(target)) ? target.key : "";
        if (target && isListBlock(target)) focusItem = target.items[target.items.length - 1]?.key;
      }
      return next;
    });
    if (focusKey) requestFocus(focusKey, focusPosition, focusItem);
  };

  const pasteLines = (key: string, lines: string[]) => {
    let focusKey = "";
    commit((current) => {
      const index = current.findIndex((block) => block.key === key);
      if (index < 0) return current;
      const created = lines.map((line) => paragraph([{ text: line }]));
      focusKey = created[created.length - 1]?.key ?? "";
      const next = [...current];
      next.splice(index + 1, 0, ...created);
      return next;
    });
    if (focusKey) requestFocus(focusKey, "end");
  };

  // --- block type changes ---------------------------------------------------

  const convertBlock = (key: string, kind: Exclude<InsertKind, "image" | "divider">) => {
    let focusKey = "";
    let focusItem: string | undefined;
    commit((current) =>
      current.map((block): EditorBlock => {
        if (block.key !== key) return block;
        const runs = isTextBlock(block) ? block.runs : isListBlock(block) ? block.items.flatMap((item, index) => (index > 0 ? [{ text: "\n" }, ...item.runs] : item.runs)) : [];
        focusKey = block.key;
        switch (kind) {
          case "heading":
            return { key: block.key, type: "heading", level: 2, runs };
          case "subheading":
            return { key: block.key, type: "heading", level: 3, runs };
          case "quote":
            return { key: block.key, type: "quote", runs };
          case "bullet_list":
          case "numbered_list": {
            if (isListBlock(block)) return { ...block, type: kind };
            const item: EditorItem = { key: nextKey(), runs };
            focusItem = item.key;
            return { key: block.key, type: kind, items: [item] };
          }
          default:
            return { key: block.key, type: "paragraph", runs };
        }
      })
    );
    setMenuFor(null);
    if (focusKey) requestFocus(focusKey, "end", focusItem);
  };

  const insertAfter = (key: string, created: EditorBlock, replaceIfEmpty: boolean) => {
    commit((current) => {
      const index = current.findIndex((block) => block.key === key);
      if (index < 0) return [...current, created];
      const block = current[index];
      const next = [...current];
      if (replaceIfEmpty && isTextBlock(block) && block.type === "paragraph" && blockIsEmpty(block)) next.splice(index, 1, created);
      else next.splice(index + 1, 0, created);
      return next;
    });
  };

  const insertKind = (key: string, kind: InsertKind) => {
    setMenuFor(null);
    if (kind === "image") {
      pendingImageTarget.current = key;
      fileInputRef.current?.click();
      return;
    }
    if (kind === "divider") {
      const created: EditorBlock = { key: nextKey(), type: "divider" };
      const follow = paragraph();
      commit((current) => {
        const index = current.findIndex((block) => block.key === key);
        const next = [...current];
        const block = current[index];
        if (index >= 0 && isTextBlock(block) && block.type === "paragraph" && blockIsEmpty(block)) next.splice(index, 1, created, follow);
        else next.splice(index + 1, 0, created, follow);
        return next;
      });
      requestFocus(follow.key, "start");
      return;
    }
    const target = blocks.find((block) => block.key === key);
    if (target && isTextBlock(target) && (blockIsEmpty(target) || kind !== "paragraph")) {
      convertBlock(key, kind);
      return;
    }
    const created = kind === "bullet_list" || kind === "numbered_list"
      ? ({ key: nextKey(), type: kind, items: [{ key: nextKey(), runs: [] }] } as EditorBlock)
      : kind === "heading"
        ? ({ key: nextKey(), type: "heading", level: 2, runs: [] } as EditorBlock)
        : kind === "subheading"
          ? ({ key: nextKey(), type: "heading", level: 3, runs: [] } as EditorBlock)
          : kind === "quote"
            ? ({ key: nextKey(), type: "quote", runs: [] } as EditorBlock)
            : paragraph();
    insertAfter(key, created, true);
    requestFocus(created.key, "start", isListBlock(created) ? created.items[0]?.key : undefined);
  };

  const removeBlock = (key: string) => {
    commit((current) => current.filter((block) => block.key !== key));
  };

  const moveBlock = (key: string, direction: -1 | 1) => {
    commit((current) => {
      const index = current.findIndex((block) => block.key === key);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const updateImage = (key: string, patch: Partial<Extract<EditorBlock, { type: "image" }>>) => {
    setBlocks((current) => current.map((block) => (block.key === key && block.type === "image" ? { ...block, ...patch } : block)));
  };

  // --- images ----------------------------------------------------------------

  const handleFiles = async (files: FileList | null) => {
    const targetKey = pendingImageTarget.current;
    pendingImageTarget.current = null;
    const file = files?.[0];
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (!file || !targetKey) return;
    const created: EditorBlock = { key: nextKey(), type: "image", image_id: "", alt: "", caption: "", uploading: true };
    const follow = paragraph();
    commit((current) => {
      const index = current.findIndex((block) => block.key === targetKey);
      const next = [...current];
      const block = current[index];
      if (index >= 0 && isTextBlock(block) && block.type === "paragraph" && blockIsEmpty(block)) next.splice(index, 1, created, follow);
      else next.splice(index + 1, 0, created, follow);
      return next;
    });
    try {
      const result = await uploadImage(file);
      rememberPreviewImageUrl(result.id, result.url);
      updateImage(created.key, { image_id: result.id, uploading: false, error: undefined });
      requestFocus(follow.key, "start");
    } catch (error) {
      updateImage(created.key, { uploading: false, error: error instanceof Error ? error.message : "The image could not be uploaded." });
    }
  };

  // --- floating toolbar -----------------------------------------------------

  useEffect(() => {
    const onSelectionChange = () => {
      if (linkDraftRef.current) return;
      const root = rootRef.current;
      const selection = window.getSelection();
      if (!root || !selection || selection.rangeCount === 0 || selection.isCollapsed || !editableFromSelection(root)) {
        setToolbar(null);
        return;
      }
      const rect = selection.getRangeAt(0).getBoundingClientRect();
      const rootRect = root.getBoundingClientRect();
      setToolbar({ top: Math.max(0, rect.top - rootRect.top - 44), left: Math.max(0, rect.left - rootRect.left + rect.width / 2) });
    };
    document.addEventListener("selectionchange", onSelectionChange);
    return () => document.removeEventListener("selectionchange", onSelectionChange);
  }, []);

  const keepSelection = (event: MouseEvent) => event.preventDefault();

  const applyInline = (command: "bold" | "italic") => {
    const editable = editableFromSelection(rootRef.current);
    execCommand(command);
    syncEditable(editable);
  };

  const openLinkDraft = () => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    savedRange.current = selection.getRangeAt(0).cloneRange();
    const container = savedRange.current.commonAncestorContainer;
    const element = container.nodeType === Node.ELEMENT_NODE ? (container as HTMLElement) : container.parentElement;
    const existing = element?.closest("a")?.getAttribute("href") ?? "";
    setLinkDraft({ value: existing || "https://", error: "" });
  };

  const applyLink = (remove = false) => {
    const range = savedRange.current;
    const selection = window.getSelection();
    if (!range || !selection) return;
    selection.removeAllRanges();
    selection.addRange(range);
    const editable = editableFromSelection(rootRef.current);
    if (remove) {
      execCommand("unlink");
    } else {
      const href = (linkDraft?.value ?? "").trim();
      if (!isSafeStoryHref(href)) {
        setLinkDraft((current) => (current ? { ...current, error: "Links must start with https:// or mailto:." } : current));
        return;
      }
      execCommand("unlink");
      execCommand("createLink", href);
    }
    syncEditable(editable);
    setLinkDraft(null);
    setToolbar(null);
  };

  const activeBlock = blocks.find((block) => block.key === activeKey);
  const activeTextKind: InsertKind | null = !activeBlock
    ? null
    : activeBlock.type === "heading"
      ? activeBlock.level === 2 ? "heading" : "subheading"
      : activeBlock.type === "paragraph" || activeBlock.type === "quote" || activeBlock.type === "bullet_list" || activeBlock.type === "numbered_list"
        ? activeBlock.type
        : null;

  // --- render ----------------------------------------------------------------

  const renderTextBlock = (block: Extract<EditorBlock, { runs: StoryRun[] }>, index: number) => {
    const tag = block.type === "heading" ? (block.level === 2 ? "h2" : "h3") : block.type === "quote" ? "blockquote" : "p";
    const placeholder = block.type === "heading" ? (block.level === 2 ? "Heading" : "Subheading") : block.type === "quote" ? "Quote" : index === 0 ? "Tell investors the story…" : "Continue writing, or press + to add a heading, list or image";
    return (
      <EditableText
        blockKey={block.key}
        focusRequest={focus}
        key={`${block.key}-${tag}`}
        onBackspaceAtStart={(runs) => backspaceAtStart(block.key, runs)}
        onFocusBlock={() => setActiveKey(block.key)}
        onPasteLines={(lines) => pasteLines(block.key, lines)}
        onRunsChange={(runs) => updateRuns(block.key, runs)}
        onSplit={(before, after) => splitBlock(block.key, before, after)}
        placeholder={placeholder}
        runs={block.runs}
        seed={block.seed}
        tag={tag}
      />
    );
  };

  const renderListBlock = (block: Extract<EditorBlock, { items: EditorItem[] }>) => {
    const ListTag = block.type === "bullet_list" ? "ul" : "ol";
    return (
      <ListTag className="se-list" key={block.key}>
        {block.items.map((item) => (
          <EditableText
            blockKey={block.key}
            focusRequest={focus}
            itemKey={item.key}
            key={item.key}
            onBackspaceAtStart={(runs) => backspaceAtStart(block.key, runs, item.key)}
            onFocusBlock={() => setActiveKey(block.key)}
            onPasteLines={(lines) => pasteLines(block.key, lines)}
            onRunsChange={(runs) => updateRuns(block.key, runs, item.key)}
            onSplit={(before, after) => splitBlock(block.key, before, after, item.key)}
            placeholder="List item"
            runs={item.runs}
            seed={item.seed}
            tag="li"
          />
        ))}
      </ListTag>
    );
  };

  return (
    <div className="se-field">
      <div className="se-label-row">
        <span className="se-label">{label}</span>
        <span className={`se-count ${characterCount > STORY_MAX_TOTAL_CHARS || document_.blocks.length > STORY_MAX_BLOCKS ? "over" : ""}`}>
          {characterCount.toLocaleString("en-CH")} / {STORY_MAX_TOTAL_CHARS.toLocaleString("en-CH")} characters · {document_.blocks.length} blocks
        </span>
      </div>
      {hint ? <p className="se-hint">{hint}</p> : null}
      <div aria-label={label} className="se-root" ref={rootRef} role="group">
        {toolbar ? (
          <div className="se-toolbar" onMouseDown={keepSelection} style={{ top: toolbar.top, left: toolbar.left }}>
            {linkDraft ? (
              <div
                className="se-linkform"
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    event.stopPropagation();
                    applyLink();
                  }
                }}
              >
                <input
                  aria-label="Link URL"
                  autoFocus
                  onChange={(event) => setLinkDraft({ value: event.target.value, error: "" })}
                  onMouseDown={(event) => event.stopPropagation()}
                  placeholder="https://"
                  value={linkDraft.value}
                />
                <button aria-label="Apply link" onClick={() => applyLink()} title="Apply link" type="button">✓</button>
                <button aria-label="Remove link" onClick={() => applyLink(true)} title="Remove link" type="button">✕</button>
                {linkDraft.error ? <span className="se-linkerr" role="alert">{linkDraft.error}</span> : null}
              </div>
            ) : (
              <>
                <button aria-label="Bold" className="se-tb b" onClick={() => applyInline("bold")} title="Bold" type="button">B</button>
                <button aria-label="Italic" className="se-tb i" onClick={() => applyInline("italic")} title="Italic" type="button">I</button>
                <button aria-label="Link" className="se-tb" onClick={openLinkDraft} title="Link (https only)" type="button">⛓</button>
                {activeKey && activeTextKind ? (
                  <>
                    <span className="se-tb-sep" />
                    <button aria-label="Heading" aria-pressed={activeTextKind === "heading"} className="se-tb" onClick={() => convertBlock(activeKey, activeTextKind === "heading" ? "paragraph" : "heading")} title="Heading" type="button">H</button>
                    <button aria-label="Subheading" aria-pressed={activeTextKind === "subheading"} className="se-tb small" onClick={() => convertBlock(activeKey, activeTextKind === "subheading" ? "paragraph" : "subheading")} title="Subheading" type="button">h</button>
                    <button aria-label="Quote" aria-pressed={activeTextKind === "quote"} className="se-tb" onClick={() => convertBlock(activeKey, activeTextKind === "quote" ? "paragraph" : "quote")} title="Quote" type="button">“</button>
                  </>
                ) : null}
              </>
            )}
          </div>
        ) : null}

        {blocks.map((block, index) => {
          const isActive = activeKey === block.key;
          const body = isTextBlock(block)
            ? renderTextBlock(block, index)
            : isListBlock(block)
              ? renderListBlock(block)
              : block.type === "image"
                ? (
                  <figure className={`se-figure ${block.error ? "error" : ""}`} key={block.key}>
                    {block.uploading ? (
                      <div className="se-uploading" role="status">Uploading and optimising image…</div>
                    ) : block.error ? (
                      <div className="se-imgerr" role="alert">{block.error}</div>
                    ) : (
                      <img alt={block.alt} className="se-img" src={storyEditorImageUrl(block.image_id)} />
                    )}
                    {!block.uploading && !block.error ? (
                      <div className="se-imgmeta">
                        <input aria-label="Image caption" maxLength={300} onChange={(event) => updateImage(block.key, { caption: event.target.value })} placeholder="Caption (optional)" value={block.caption} />
                        <input aria-label="Image description for screen readers" maxLength={200} onChange={(event) => updateImage(block.key, { alt: event.target.value })} placeholder="Describe the image (accessibility)" value={block.alt} />
                      </div>
                    ) : null}
                  </figure>
                )
                : <hr className="se-hr" key={block.key} />;
          return (
            <div
              className={`se-block se-block-${block.type} ${isActive ? "active" : ""}`}
              data-block-key={block.key}
              key={block.key}
              onClick={() => setActiveKey(block.key)}
            >
              <div className="se-gutter">
                {(
                  <button
                    aria-expanded={menuFor === block.key}
                    aria-label={isTextBlock(block) && block.type === "paragraph" && blockIsEmpty(block) ? "Add block here" : "Add block after this one"}
                    className="se-plus"
                    onClick={(event) => {
                      event.stopPropagation();
                      setActiveKey(block.key);
                      setMenuFor((current) => (current === block.key ? null : block.key));
                    }}
                    title="Add a heading, list, image or divider"
                    type="button"
                  >
                    +
                  </button>
                )}
                {menuFor === block.key ? (
                  <div className="se-menu" role="menu">
                    {INSERT_OPTIONS.map((option) => (
                      <button className="se-menu-item" key={option.kind} onClick={() => insertKind(block.key, option.kind)} role="menuitem" type="button">
                        <span aria-hidden="true" className="se-menu-glyph">{option.glyph}</span>
                        {option.label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
              <div className="se-body">{body}</div>
              {!isTextBlock(block) || (block.type !== "paragraph" || !blockIsEmpty(block)) ? (
                <div className="se-tools">
                  {index > 0 ? <button aria-label="Move block up" className="se-tool" onClick={() => moveBlock(block.key, -1)} title="Move up" type="button">↑</button> : null}
                  {index < blocks.length - 2 ? <button aria-label="Move block down" className="se-tool" onClick={() => moveBlock(block.key, 1)} title="Move down" type="button">↓</button> : null}
                  <button aria-label={`Remove ${block.type.replace("_", " ")} block`} className="se-tool danger" onClick={() => removeBlock(block.key)} title="Remove block" type="button">✕</button>
                </div>
              ) : null}
            </div>
          );
        })}
        <input accept="image/*" aria-label="Upload story image" className="se-file" onChange={(event) => void handleFiles(event.target.files)} ref={fileInputRef} type="file" />
      </div>
      <p className="se-foot">
        Text, headings, quotes, lists, images and dividers only. Links must use https. Images are checked, stripped of metadata, resized to at most 1 MB and shown only to signed-in investors.
      </p>
    </div>
  );
}
