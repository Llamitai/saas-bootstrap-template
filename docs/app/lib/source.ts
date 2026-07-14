import { docs } from "collections/server";
import { loader } from "fumadocs-core/source";

export const source = loader({
  baseUrl: "/docs",
  source: docs.toFumadocsSource(),
});

export function markdownPathToSlugs(segments: string[]) {
  if (segments.length === 0) {
    return [];
  }

  const out = [...segments];
  out[out.length - 1] = out[out.length - 1].replace(/\.mdx?$/, "");

  if (out.length === 1 && out[0] === "index") {
    out.pop();
  }

  return out;
}

export function slugsToMarkdownPath(slugs: string[]) {
  const segments = [...slugs];

  if (segments.length === 0) {
    segments.push("index.mdx");
  } else {
    segments[segments.length - 1] += ".mdx";
  }

  return {
    segments,
    url: `/docs/${segments.join("/")}`,
  };
}
