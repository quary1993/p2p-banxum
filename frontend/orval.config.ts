import { defineConfig } from "orval";

export default defineConfig({
  banxumApi: {
    input: "../openapi/schema.yaml",
    output: {
      target: "src/api/generated/banxumApi.ts",
      client: "react-query",
      mode: "single",
      mock: true,
      prettier: false,
      override: {
        mutator: {
          path: "src/api/client/httpClient.ts",
          name: "httpClient"
        }
      }
    }
  }
});
