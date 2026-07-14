#!/usr/bin/env node
// preview-diagram.mjs — pull the Mermaid block(s) out of a Markdown/MDX page and render
// them to a single standalone HTML you can open or screenshot. No dev server needed.
//
//   node .claude/skills/add-docs/tools/preview-diagram.mjs <file.mdx> [--out /tmp/x.html]
//
// The output HTML loads Mermaid from a CDN (needs network) with a teal-on-slate theme
// close to the docs site, so what you see matches production closely enough to vet
// layout/labels before `just docs build`.
import { readFileSync, writeFileSync } from "node:fs";

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith("--"));
const outFlag = args.indexOf("--out");
const out = outFlag !== -1 ? args[outFlag + 1] : "/tmp/add-docs-preview.html";

if (!file) {
  console.error("usage: preview-diagram.mjs <file.mdx> [--out <path.html>]");
  process.exit(1);
}

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
${blocks.map((_, i) => `<h2>Diagram ${i + 1}</h2><pre class="mermaid">${blocks[i].replace(/</g, "&lt;")}</pre>`).join("\n")}
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true, theme: "base", themeVariables: ${JSON.stringify(theme)} });
</script>
</body></html>`;

writeFileSync(out, html);
console.log(`Rendered ${blocks.length} diagram(s) from ${file}`);
console.log(`Open: ${out}`);
