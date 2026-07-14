import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: false,
    include: ["tests/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["tests/end-to-end/**", "node_modules/**", ".next/**"],
  },
  resolve: {
    tsconfigPaths: true,
    alias: {
      "@/entities": path.resolve(__dirname, "src/entities"),
      "@/features": path.resolve(__dirname, "src/features"),
      "@/shared": path.resolve(__dirname, "src/shared"),
      "@lineiconshq/free-icons": path.resolve(
        __dirname,
        "node_modules/@lineiconshq/free-icons/dist/index.esm.js"
      ),
      // Belt-and-braces for `@/src/...` imports — tsconfigPaths covers
      // most of it but the explicit alias keeps things deterministic.
      "@": path.resolve(__dirname, "."),
    },
  },
});
