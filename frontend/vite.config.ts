import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

import { scopeAdminStyles } from "./src/adminConsole/adminCssScope";

const emptyFixturesPath = fileURLToPath(new URL("./src/investorPortal/fixtures.empty.ts", import.meta.url));
const emptyAdminFixturesPath = fileURLToPath(new URL("./src/adminConsole/adminFixtures.empty.ts", import.meta.url));
const emptySiteFixturesPath = fileURLToPath(new URL("./src/site/siteFixtures.empty.ts", import.meta.url));

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
          },
          {
            // The public site's preview data (design sample projects) stays out of production.
            find: /^\.\/siteFixtures$/,
            replacement: emptySiteFixturesPath
          }
        ]
        : []
    },
    css: {
      // Audit S4-9: every rule of src/styles.css (the admin stylesheet) goes below :where(html.bxa).
      postcss: { plugins: [scopeAdminStyles()] }
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
