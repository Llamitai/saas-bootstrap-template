import { glob } from "node:fs/promises";
import type { Config } from "@react-router/dev/config";
import { getSlugs } from "fumadocs-core/source";
import { openapi, openapiPages } from "./lib/openapi";
import { contentDir, slugsToUrl } from "./lib/repo-links";

async function pageSlugs() {
  const slugs: string[][] = [];
  for await (const entry of glob("**/*.{md,mdx}", { cwd: contentDir })) {
    slugs.push(getSlugs(entry));
  }
  const generated = await openapi.staticSource(openapiPages);
  for (const file of generated.files) {
    if (file.type === "page") slugs.push(getSlugs(file.path));
  }
  return slugs;
}

export default {
  ssr: true,
  async prerender({ getStaticPaths }) {
    const paths = getStaticPaths();
    for (const slugs of await pageSlugs()) {
      paths.push(slugsToUrl(slugs));
      paths.push(`/llms.mdx/docs/${[...slugs, "content.md"].join("/")}`);
    }
    return paths;
  },
} satisfies Config;
