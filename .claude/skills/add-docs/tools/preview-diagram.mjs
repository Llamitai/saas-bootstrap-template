#!/usr/bin/env node
// preview-diagram.mjs — pull the Mermaid block(s) out of a Markdown/MDX page and render
// them to a single standalone HTML you can open or screenshot. No dev server needed.
//
//   node .claude/skills/add-docs/tools/preview-diagram.mjs <file.mdx> [--out /tmp/x.html]
//   node .claude/skills/add-docs/tools/preview-diagram.mjs --help
//
// Without --out it writes /tmp/add-docs-preview.html (overwritten on every run).
//
// The output HTML loads Mermaid from a CDN (needs network) with a teal-on-slate theme
// close to the docs site, so what you see matches production closely enough to vet
// layout/labels before `just docs build`.
import { readFileSync, writeFileSync } from "node:fs";

const DEFAULT_OUT = "/tmp/add-docs-preview.html";
const USAGE = `usage: preview-diagram.mjs <file.mdx> [--out <path.html>]

Extracts every \`\`\`mermaid block from <file.mdx> and writes one standalone HTML
page that renders them (Mermaid is loaded from a CDN, so viewing needs network).

  --out <path.html>  output file (default: ${DEFAULT_OUT}, overwritten each run)
  -h, --help         show this help and exit`;

const args = process.argv.slice(2);
if (args.includes("--help") || args.includes("-h")) {
  console.log(USAGE);
  process.exit(0);
}
const outFlag = args.indexOf("--out");
const file = args.find((a, i) => !a.startsWith("-") && i !== outFlag + 1);
const out = outFlag !== -1 ? args[outFlag + 1] : DEFAULT_OUT;

if (!file || (outFlag !== -1 && !out)) {
  console.error(USAGE);
  process.exit(1);
}

const escapeHtml = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;");

const src = readFileSync(file, "utf8");
const blocks = [...src.matchAll(/```mermaid\s*\n([\s\S]*?)```/g)].map((m) => m[1].trim());

if (blocks.length === 0) {
  console.error(`No \`\`\`mermaid blocks found in ${file}`);
  process.exit(2);
}

const theme = {
  background: "#ffffff",
  primaryColor: "#f0fdfa",
  primaryTextColor: "#0f172a",
  primaryBorderColor: "#0d9488",
  lineColor: "#334155",
  nodeBorder: "#2dd4bf",
  fontFamily: "Figtree, system-ui, sans-serif",
  fontSize: "13px",
};

const html = `<!doctype html>
<html><head><meta charset="utf-8"/>
<style>
  body { margin:0; padding:24px; background:#f8fafc; font-family:${theme.fontFamily}; }
  h2 { color:#475569; font-size:13px; font-weight:600; margin:24px 0 8px; }
  .mermaid { background:#fff; border:1px solid #cbd5e1; border-radius:10px; padding:16px; }
</style></head><body>
${blocks.map((_, i) => `<h2>Diagram ${i + 1}</h2><pre class="mermaid">${escapeHtml(blocks[i])}</pre>`).join("\n")}
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true, theme: "base", themeVariables: ${JSON.stringify(theme)} });
</script>
</body></html>`;

writeFileSync(out, html);
console.log(`Rendered ${blocks.length} diagram(s) from ${file}`);
console.log(`Open: ${out}`);
