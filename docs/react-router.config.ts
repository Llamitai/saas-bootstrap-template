import { existsSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import type { Config } from "@react-router/dev/config";

const docsDir = path.join(process.cwd(), "content", "docs");

function toRoutePath(filePath: string) {
  const relative = path.relative(docsDir, filePath).replace(/\\/g, "/");
  const withoutExtension = relative.replace(/\.mdx?$/, "");
  const segments = withoutExtension.split("/");

  if (segments.at(-1) === "index") {
    segments.pop();
  }

  return `/docs${segments.length > 0 ? `/${segments.join("/")}` : ""}`;
}

function collectMdxFiles(dir: string): string[] {
  if (!existsSync(dir)) {
    return [];
  }

  return readdirSync(dir).flatMap((entry) => {
    const fullPath = path.join(dir, entry);
    const stats = statSync(fullPath);

    if (stats.isDirectory()) {
      return collectMdxFiles(fullPath);
    }

    return /\.mdx?$/.test(entry) ? [fullPath] : [];
  });
}

const docPaths = collectMdxFiles(docsDir).map(toRoutePath);
const llmsMdxPaths = docPaths
  .filter((url) => url !== "/docs")
  .map((url) => url.replace(/^\/docs/, "/llms.mdx/docs"));

export default {
  ssr: true,
  prerender: {
    paths: [
      "/",
      "/login",
      "/api/search",
      "/llms.txt",
      "/llms-full.txt",
      ...docPaths,
      ...llmsMdxPaths,
    ],
    concurrency: 4,
  },
} satisfies Config;
