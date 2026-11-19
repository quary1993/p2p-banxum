// IP of Webby-Soft SRL.
/** Bytes of a file the API returns as base64 or text (documents and reports downloads). */
export function bytesOfArtifact(artifact: { content: string; content_encoding: string }) {
  return artifact.content_encoding === "base64"
    ? Uint8Array.from(window.atob(artifact.content), (character) => character.charCodeAt(0))
    : new TextEncoder().encode(artifact.content);
}
