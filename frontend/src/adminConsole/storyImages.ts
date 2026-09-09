// Story image upload for the admin editor. The server verifies, re-encodes and
// shrinks every file; this module only ships the bytes and remembers preview URLs.
import { httpClient } from "../api/client/httpClient";
import { isFixturePreview } from "../investorPortal/data";
import { storyImageUrl } from "../investorPortal/story";

export type StoryImageUploadResult = { id: string; url: string };
export type StoryImageUploader = (file: File) => Promise<StoryImageUploadResult>;

const previewImageUrls = new Map<string, string>();

export function storyEditorImageUrl(imageId: string) {
  return previewImageUrls.get(imageId) ?? storyImageUrl(imageId);
}

export function rememberPreviewImageUrl(imageId: string, url: string) {
  if (url && !previewImageUrls.has(imageId)) previewImageUrls.set(imageId, url);
}

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export const uploadStoryImage: StoryImageUploader = async (file) => {
  if (!file.type.startsWith("image/")) throw new Error("Choose an image file (JPEG, PNG, WebP, GIF, BMP or TIFF).");
  if (file.size > MAX_UPLOAD_BYTES) throw new Error("Images must be smaller than 25 MB before processing.");
  if (isFixturePreview) {
    const id = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `00000000-0000-4000-8000-${String(Date.now()).padStart(12, "0").slice(-12)}`;
    const url = typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : "";
    previewImageUrls.set(id, url);
    return { id, url };
  }
  const form = new FormData();
  form.append("file", file, file.name);
  const result = await httpClient<StoryImageUploadResult>("/api/v1/admin/story-images/", { method: "POST", body: form });
  return { id: result.id, url: result.url };
};

