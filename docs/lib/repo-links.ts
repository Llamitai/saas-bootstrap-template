import { execFileSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import path from "node:path";
import { getSlugs } from "fumadocs-core/source";

// Node-only helpers shared by source.config.ts, react-router.config.ts and route loaders.
// Paths resolve from the docs package root, where every docs script runs.
export const docsRoot = process.cwd();
export const repoRoot = path.resolve(docsRoot, "..");
export const contentDir = path.join(docsRoot, "content", "docs");

let cachedRepoUrl: string | null | undefined;

/** Browsable URL of the origin remote, or null when there is none (no link is invented). */
export function getRepoUrl(): string | null {
  if (cachedRepoUrl !== undefined) return cachedRepoUrl;
  try {
    const remote = execFileSync("git", ["remote", "get-url", "origin"], {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    const ssh = remote.match(/^git@([^:]+):(.+?)(?:\.git)?$/);
    const https = remote.match(
      /^https:\/\/(?:[^@/]+@)?([^/]+)\/(.+?)(?:\.git)?$/
    );
    const match = ssh ?? https;
    cachedRepoUrl = match ? `https://${match[1]}/${match[2]}` : null;
  } catch {
    cachedRepoUrl = null;
  }
  return cachedRepoUrl;
}

export function slugsToUrl(slugs: string[]): string {
  return slugs.length > 0 ? `/docs/${slugs.join("/")}` : "/docs";
}

/** Site URL of a content file (`guias/x.md` -> `/docs/guias/x`). */
export function contentFileToUrl(relativeFile: string): string {
  return slugsToUrl(getSlugs(relativeFile));
}

interface MdNode {
  type: string;
  url?: string;
  children?: MdNode[];
}

const EXTERNAL = /^(?:[a-z][a-z0-9+.-]*:|\/\/|\/|#)/i;

function rewrite(url: string, fromFile: string): string | null {
  const [target, hash = ""] = url.split(/(?=#)/);
  const absolute = path.resolve(path.dirname(fromFile), decodeURI(target));

  if (absolute.startsWith(contentDir + path.sep) && /\.mdx?$/.test(absolute)) {
    return contentFileToUrl(path.relative(contentDir, absolute)) + hash;
  }
  if (!absolute.startsWith(repoRoot + path.sep) || !existsSync(absolute)) {
    return null;
  }
  const repoUrl = getRepoUrl();
  if (!repoUrl) return null;
  const kind = statSync(absolute).isDirectory() ? "tree" : "blob";
  const repoPath = path.relative(repoRoot, absolute).split(path.sep).join("/");
  return `${repoUrl}/${kind}/HEAD/${repoPath}${hash}`;
}

/**
 * Keeps repository-relative links valid in both places: agents follow them on
 * disk, the site rewrites them to page URLs or to the repository host.
 * Links that cannot be resolved become plain text instead of dead links.
 */
export function remarkRepoLinks() {
  return (tree: MdNode, file: { path?: string }) => {
    const fromFile = file.path;
    if (!fromFile) return;

    const visit = (node: MdNode) => {
      if (!node.children) return;
      node.children = node.children.flatMap((child) => {
        visit(child);
        if (child.type !== "link" || !child.url || EXTERNAL.test(child.url)) {
          return [child];
        }
        const next = rewrite(child.url, fromFile);
        if (next) {
          child.url = next;
          return [child];
        }
        return child.children ?? [];
      });
    };
    visit(tree);
  };
}
