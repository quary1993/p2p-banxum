import { readFileSync, writeFileSync } from "node:fs";

const files = ["src/api/generated/banxumApi.ts"];

for (const file of files) {
  const input = readFileSync(file, "utf8");
  const output = input
    .split("\n")
    .map((line) => line.replace(/[ \t]+$/u, ""))
    .join("\n");
  if (output !== input) {
    writeFileSync(file, output, "utf8");
  }
}
