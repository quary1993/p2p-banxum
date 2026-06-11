import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

const emptyFixturesPath = fileURLToPath(new URL("./src/investorPortal/fixtures.empty.ts", import.meta.url));
const emptyAdminFixturesPath = fileURLToPath(new URL("./src/adminConsole/adminFixtures.empty.ts", import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");

  if (mode === "production" && env.VITE_PREVIEW === "true") {
    throw new Error("VITE_PREVIEW=true is not allowed for production builds.");
  }

  return {
    plugins: [react()],
    resolve: {
      alias: mode === "production"
        ? [
          {
            find: /^\.\/(?:investorPortal\/)?fixtures$/,
            replacement: emptyFixturesPath
          },
          {
            find: /^\.\/adminFixtures$/,
            replacement: emptyAdminFixturesPath
          }
        ]
        : []
    },
    server: {
      port: 5173,
      proxy: {
        "/api": "http://localhost:8000"
      }
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts"
    }
  };
});
