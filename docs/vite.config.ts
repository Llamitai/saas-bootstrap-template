import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import mdx from "fumadocs-mdx/vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

const fumadocsPackages = [
  "fumadocs-core",
  "fumadocs-ui",
  "fumadocs-mdx",
  "@fumadocs/base-ui",
];

export default defineConfig({
  plugins: [mdx(), tailwindcss(), reactRouter(), tsconfigPaths()],
  server: {
    host: "127.0.0.1",
    port: 4321,
  },
  optimizeDeps: {
    exclude: fumadocsPackages,
  },
  ssr: {
    noExternal: fumadocsPackages,
  },
});
