/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: "..", // one .env at the repo root (see .env.example)
  test: {
    environment: "node", // hook tests opt in to jsdom with a file comment (jsdom signals clash with Node Request)
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    coverage: { provider: "v8", include: ["src/api/**"], exclude: ["src/api/schema.d.ts", "src/api/__tests__/**"] },
  },
});
