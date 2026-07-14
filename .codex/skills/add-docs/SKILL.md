---
name: add-docs
description: >
  Author one rich, media-heavy documentation page that explains a SPECIFIC piece of how the
  SaaS Bootstrap codebase works, and drop it into the Fumadocs docs site (`docs/content/docs/**`)
  so it renders with Mermaid diagrams, animated/static SVG, callouts and tables. Use when the
  user asks to "/add-docs <X>", "document <X>", "add docs for <X>", "write a doc explaining <X>",
  "diagram <X> in the docs", "explain how <X> works in the docs", or — in Spanish — "documentar <X>",
  "agrega documentación de <X>", "diagrama de <X>". The skill researches the REAL code first so
  diagrams are accurate, infers the right subfolder (and asks when it's unclear), prioritizes
  comprehension through heavy visual support, and verifies the page with `just docs build`.
  Writes the page in the reader's language — Spanish by default, and asks (Español / English)
  with AskUserQuestion when the request doesn't make the language explicit.
---

# /add-docs — Enriched docs for the SaaS Bootstrap docs site

Turn a request like **`/add-docs db diagrama entidad-relación`** into a single,
beautifully illustrated page under `docs/content/docs/**` that the docs site
(React Router 7 + Fumadocs MDX) renders — with Mermaid diagrams, **animated** SVG,
tables, and callouts.

The north star is **comprehension**: a reader should *get it from the picture
first*, then confirm in the prose. Every page you write should lead with a
diagram, not a wall of text.

Paths in this skill are relative to the repo root. The docs app lives in `docs/`.
**Read [`reference.md`](reference.md) before writing** — it holds the diagram
catalog, the exact frontmatter + `meta.json` conventions, the animated-SVG
recipes, and the conventions you cannot guess.

---

## The harness (run this to verify — every time)

The docs site IS the harness. After writing a page you MUST prove it renders:

```bash
# From repo root. Compiles every MDX page through fumadocs-mdx AND prerenders
# every /docs/* route — a bad frontmatter, broken MDX/JSX, or invalid import
# fails the build with the offending file path.
just docs build        # equivalent: pnpm --prefix docs build
```

A clean build means the page compiled and prerendered. New pages are picked up
automatically — `docs/react-router.config.ts` collects every `.mdx` under
`docs/content/docs` into the prerender list. `tools/preview-diagram.mjs` (see
below) renders a Mermaid block to a standalone HTML you can screenshot first.

If the dev server is already up (`just docs dev` → `http://127.0.0.1:4321`),
the page is live at the URL printed in step 7.

---

## Golden rules (site-specific — get these wrong and it won't render right)

1. **Output goes in `docs/content/docs/**` only** — never in `docs/internal/`
   (that folder is NOT rendered; it's internal engineering docs — good to *read*
   while researching). Pages are **`.mdx`** files with kebab-case ASCII names.
2. **Do NOT write the `# H1` title in the body.** Fumadocs renders the
   `title` and `description` from frontmatter automatically (as an `<h1>` + lead
   paragraph). Start the body with the `<Callout title="En resumen">` opener
   (house convention), then your first `##` section.
3. **The sidebar is driven by `meta.json`.** Each directory has a `meta.json`
   with `title` + `pages`; a page that isn't listed there doesn't show up in the
   sidebar. **Always add your new page's slug** (and, for a new folder, add the
   folder to the parent `meta.json` + create the folder's own `meta.json`).
4. **Mermaid = fenced ` ```mermaid ` blocks.** The site renders them client-side
   and re-themes them on light/dark switch — you get that for free. Write
   **plain** Mermaid, never inline `%%{init}%%` styling; it fights the theme.
   Prefer Mermaid for anything data-driven (ER, flow, sequence, class).
5. **Animated & static SVG live in `docs/public/diagrams/<name>.svg`**, referenced as
   `![alt](/diagrams/<name>.svg)`. Animate with **SMIL** (`<animate>`,
   `<animateMotion>`, `<animateTransform>`) or an inline `<style>@keyframes</style>` —
   both run inside an `<img>`. **`<script>` inside the SVG does NOT run** when embedded
   this way; never rely on it. Use animation only when *motion explains something*
   static can't (a flow, a state transition, data moving through a pipeline).
6. **Accuracy first.** A pretty diagram of code that doesn't exist is worse than no
   diagram. Research the real symbols (codegraph / grep / read) before you draw.
7. **Write in the reader's language.** Default to **Spanish** (the existing content is
   Spanish). If the request doesn't state a language, **ask with `AskUserQuestion`** (offer
   *Español* — recommended — and *English*) and don't start writing until you have the answer.
   The chosen language applies to everything a reader sees — frontmatter `title`/`description`,
   headings, prose, table text, "where next" links, and **diagram labels** (Mermaid node text,
   SVG `<text>`). Keep code identifiers, file paths, enum values, Mermaid keywords, and slugs
   **verbatim**. See `reference.md` → **Language**.

---

## Process

### 1. Parse the request — and fix the language
Extract **what** to document, **who** reads it, and **which language** to write in.
`/add-docs db diagrama entidad-relación` → subject "database schema", artifact "ER diagram",
audience "backend devs" → `arquitectura/` subfolder.

**Language:** default to **Spanish**. If the request explicitly names a language, honor it.
Otherwise **ask with `AskUserQuestion`** (options: *Español* — recommended — / *English*) and
wait for the answer before writing a single line. The whole page — including diagram labels —
is written in that language; identifiers/paths/enums/Mermaid keywords stay verbatim
(see `reference.md` → **Language**).

### 2. Research the real code (do not skip)
Diagrams must mirror reality. Use `codegraph_explore` / search, read the models,
trace the flow. For a DB ERD: read `backend/src/common/database/models/**` and use the
real `__tablename__`, columns, and FK relationships. For a request flow: trace the
router → use case → repository. `docs/internal/**` (architecture notes, ERD, API
reference) is a good research source. Capture exact names — the diagram uses them verbatim.

### 3. Decide placement — ASK when unclear
Pick `subfolder` + `slug` under `docs/content/docs/`. Existing groups: `conceptos/`,
`arquitectura/`, `operacion/` (see the table in `reference.md`). **When it is genuinely
ambiguous — e.g. could be a concept page or an architecture page, or the subfolder
doesn't exist yet — ask the user** with `AskUserQuestion` (offer the 2–3 most plausible
paths). Don't invent a deep new folder hierarchy silently. If you also still owe the user
the **language** question (step 1), bundle both into a **single `AskUserQuestion` call**
(it takes up to 4 questions) instead of interrupting twice.

### 4. Choose the richest diagram set for the subject
Match subject → diagram type (full catalog in `reference.md`). E.g. schema → `erDiagram`;
request/event flow → `sequenceDiagram`; lifecycle/status machine → `flowchart` with labeled
edges + an **animated SVG** of the happy path; layering → `flowchart` or a hand-drawn SVG.
A good page uses **2–4 complementary visuals**, not one.

### 5. Write the page (layered for comprehension)
Use the skeleton in [`templates/doc-template.mdx`](templates/doc-template.mdx). Order:
`<Callout title="En resumen">` opener → **overview diagram** → detailed sections (each with
its own visual or table) → an **animated SVG** where motion aids understanding → a "Where to
go next" links list. Keep prose tight; let visuals carry the load. Tables beat paragraphs for
enumerations; `<Steps>`/`<TypeTable>` beat prose for sequences and option lists. Update the
directory's `meta.json`. **Write every reader-facing string — prose, headings, table text,
and diagram labels — in the language chosen in step 1**; keep code, paths, enum values, and
Mermaid keywords verbatim (`reference.md` → Language).

### 6. Verify (the harness)
`just docs build` (or `pnpm --prefix docs build`). Fix any MDX/frontmatter error it reports.
Optionally preview a diagram in isolation: `node <this-skill-dir>/tools/preview-diagram.mjs
<file.mdx>` (the skill dir is `.claude/`, `.codex/` or `.opencode/skills/add-docs` per
runtime) writes `/tmp/add-docs-preview.html` you can open/screenshot.

### 7. Report
Give the user the rendered URL (`/docs/<subfolder>/<slug>` — e.g. `/docs/arquitectura/data-model`;
an `index.mdx` maps to the folder URL) and a one-line summary of the visuals you added.

---

## Files in this skill
- [`reference.md`](reference.md) — diagram catalog, frontmatter + `meta.json` conventions,
  animated-SVG recipes, MDX component list, and the full gotcha list. **Read first.**
- [`templates/doc-template.mdx`](templates/doc-template.mdx) — copy-paste page skeleton.
- [`templates/animated-pipeline.svg`](templates/animated-pipeline.svg) — a working
  SMIL-animated SVG you can adapt (a token traveling through pulsing phase nodes).
- [`tools/preview-diagram.mjs`](tools/preview-diagram.mjs) — extract a Mermaid block
  from a `.mdx` and render it to a standalone HTML for screenshotting.

## Worked example (in this repo)
`docs/content/docs/arquitectura/index.mdx` is the quality bar: a `<Callout>` opener,
a high-level `flowchart` of browser → frontend → BFF → backend → Postgres/Redis/MinIO,
a `<Steps>` walkthrough of the Clean Architecture layers, a frontend dependency-flow
`flowchart`, and a `<TypeTable>` of the docs app itself. It passes `just docs build`.

## Gotchas (learned the hard way)
- **Duplicate H1.** Fumadocs already prints `title`. Starting the body with
  `# Something` yields two H1s. Start with the `<Callout>`, then `##`.
- **Page missing from the sidebar** → you forgot to add it to the directory's
  `meta.json` `pages` array (or the folder to the parent `meta.json`).
- **MDX is JSX.** A bare `<` or `{` in prose is parsed as JSX and breaks the compile.
  Put generics/placeholders in backticks (`` `Dict[str, Any]` ``) or escape them.
- **Animated SVG via `<img>` ignores `<script>`** — SMIL and inline CSS keyframes work,
  JS does not. If you need interactivity (hover, click), use a Mermaid block instead.
- **Don't style Mermaid.** The site injects the theme (and re-renders on dark-mode
  toggle); inline color/`%%{init}%%` directives fight it and look wrong.
- **Prefer `flowchart`/`erDiagram`/`sequenceDiagram`.** Mermaid lazy-loads a separate
  module per diagram type; exotic types (e.g. `stateDiagram-v2`) can flake in the Vite
  dev server. Draw state machines as a `flowchart` with labeled edges — see
  `reference.md` → "State machine / lifecycle skeleton".
- **Only `title` + `description` in frontmatter** — both required by house convention.
  There is no `sidebar:`, `tags:`, `difficulty:` or `method:` schema on this site;
  ordering lives in `meta.json`.
