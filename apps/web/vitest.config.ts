import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@mirror-ops/types": path.resolve(__dirname, "../../packages/types/index.ts"),
      "@mirror-ops/config": path.resolve(__dirname, "../../packages/config/index.ts"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["tests/**/*.test.tsx"],
  },
});
