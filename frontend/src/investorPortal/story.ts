// Investor-facing story documents (borrower / loan-originator narratives).
//
// The document is a small whitelisted block/run structure mirrored by
// backend/apps/platform_core/domain/story.py. Nothing here is ever rendered
// as HTML: the renderer builds React elements from these values only.

export type StoryRun = {
  text: string;
  bold?: boolean;
  italic?: boolean;
  href?: string;
};

export type StoryTextBlock = { type: "paragraph" | "quote"; runs: StoryRun[] };
export type StoryHeadingBlock = { type: "heading"; level: 2 | 3; runs: StoryRun[] };
export type StoryListBlock = { type: "bullet_list" | "numbered_list"; items: StoryRun[][] };
export type StoryImageBlock = { type: "image"; image_id: string; alt: string; caption: string };
export type StoryDividerBlock = { type: "divider" };
export type StoryBlock = StoryTextBlock | StoryHeadingBlock | StoryListBlock | StoryImageBlock | StoryDividerBlock;

export type StoryDocument = { version: 1; blocks: StoryBlock[] };

export const STORY_MAX_BLOCKS = 200;
export const STORY_MAX_TOTAL_CHARS = 60_000;

export function emptyStory(): StoryDocument {
  return { version: 1, blocks: [] };
}

export function storyImageUrl(imageId: string) {
  return `/api/v1/story-images/${encodeURIComponent(imageId)}/`;
}

export function isSafeStoryHref(value: string) {
  const href = value.trim();
  if (href.length === 0 || href.length > 2000 || /\s/.test(href)) return false;
  const lowered = href.toLowerCase();
  return lowered.startsWith("https://") || lowered.startsWith("mailto:");
}

function cleanRuns(value: unknown): StoryRun[] {
  if (!Array.isArray(value)) return [];
  const runs: StoryRun[] = [];
  for (const raw of value) {
    if (!raw || typeof raw !== "object") continue;
    const record = raw as Record<string, unknown>;
    const text = typeof record.text === "string" ? record.text : "";
    if (text === "") continue;
    const run: StoryRun = { text };
    if (record.bold === true) run.bold = true;
    if (record.italic === true) run.italic = true;
    if (typeof record.href === "string" && isSafeStoryHref(record.href)) run.href = record.href.trim();
    runs.push(run);
  }
  return runs;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Defensive normalisation of an API value into a renderable document. */
export function normalizeStory(value: unknown): StoryDocument {
  if (!value || typeof value !== "object") return emptyStory();
  const rawBlocks = (value as { blocks?: unknown }).blocks;
  if (!Array.isArray(rawBlocks)) return emptyStory();
  const blocks: StoryBlock[] = [];
  for (const raw of rawBlocks) {
    if (!raw || typeof raw !== "object") continue;
    const record = raw as Record<string, unknown>;
    switch (record.type) {
      case "paragraph":
      case "quote":
        blocks.push({ type: record.type, runs: cleanRuns(record.runs) });
        break;
      case "heading":
        blocks.push({ type: "heading", level: record.level === 3 ? 3 : 2, runs: cleanRuns(record.runs) });
        break;
      case "bullet_list":
      case "numbered_list": {
        const items = Array.isArray(record.items) ? record.items.map(cleanRuns).filter((item) => item.length > 0) : [];
        if (items.length > 0) blocks.push({ type: record.type, items });
        break;
      }
      case "image": {
        const imageId = typeof record.image_id === "string" ? record.image_id : "";
        if (!UUID_PATTERN.test(imageId)) break;
        blocks.push({
          type: "image",
          image_id: imageId,
          alt: typeof record.alt === "string" ? record.alt : "",
          caption: typeof record.caption === "string" ? record.caption : ""
        });
        break;
      }
      case "divider":
        blocks.push({ type: "divider" });
        break;
      default:
        break;
    }
    if (blocks.length >= STORY_MAX_BLOCKS) break;
  }
  return { version: 1, blocks };
}

export function runsText(runs: StoryRun[]) {
  return runs.map((run) => run.text).join("");
}

export function storyIsEmpty(story: StoryDocument) {
  return story.blocks.every((block) => {
    switch (block.type) {
      case "paragraph":
      case "quote":
      case "heading":
        return runsText(block.runs).trim() === "";
      case "bullet_list":
      case "numbered_list":
        return block.items.every((item) => runsText(item).trim() === "");
      case "divider":
        return true;
      default:
        return false;
    }
  });
}

export function storyCharacterCount(story: StoryDocument) {
  return story.blocks.reduce((total, block) => {
    switch (block.type) {
      case "paragraph":
      case "quote":
      case "heading":
        return total + runsText(block.runs).length;
      case "bullet_list":
      case "numbered_list":
        return total + block.items.reduce((sum, item) => sum + runsText(item).length, 0);
      case "image":
        return total + block.alt.length + block.caption.length;
      default:
        return total;
    }
  }, 0);
}

/** Drops empty text blocks / list items so the saved document is tidy. */
export function compactStory(story: StoryDocument): StoryDocument {
  const blocks: StoryBlock[] = [];
  for (const block of story.blocks) {
    if ((block.type === "paragraph" || block.type === "quote" || block.type === "heading") && runsText(block.runs).trim() === "") continue;
    if (block.type === "bullet_list" || block.type === "numbered_list") {
      const items = block.items.filter((item) => runsText(item).trim() !== "");
      if (items.length === 0) continue;
      blocks.push({ ...block, items });
      continue;
    }
    blocks.push(block);
  }
  return { version: 1, blocks };
}
