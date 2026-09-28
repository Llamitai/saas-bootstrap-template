# Docs constitution

Binding for any change under `docs/` (the React Router + Fumadocs site). The
root [AGENTS.md](../AGENTS.md) still applies; this file adds the docs rules.

## Read for the task

- For a hand-authored tutorial, guide, concept or reference page under
  `content/docs/` (outside ADRs and generated API pages), use
  [add-docs](../.claude/skills/add-docs/SKILL.md) and the relevant part of
  [Escribir páginas](content/docs/guias/documentacion/escribir-paginas.mdx).
- For an ADR, use the format in [the ADR index](content/docs/equipo/adr/index.md).
- For a backend HTTP contract or generated API reference, use
  [openapi-sync](../.claude/skills/openapi-sync/SKILL.md); never hand-edit
  generated endpoint pages.
- For site code, routes, prerendering or LLM routes, use
  [Sitio de documentación](content/docs/guias/operacion/sitio-de-documentacion.mdx)
  and inspect the affected files in `app/` or `lib/`.

## Commands

Run from the Git root: `just docs dev` (:4321), `just docs check` (typecheck +
Biome, no autofix), `just docs code_quality` (autofix) and `just docs build`,
which prerenders every page and fails on a broken one.

## Content rules

- Pages live in `content/docs/`, organized by reader need: `(empezar)`,
  `guias`, `conceptos`, `referencia` and `equipo`. Content is Spanish; site code
  in `app/` and `lib/` is English.
- Every page has frontmatter with at least `title`; use file-relative links to
  pages and repository files.
- ADRs live in `content/docs/equipo/adr/` with the sections and index described
  in its `index.md`. An accepted ADR is never rewritten; a new ADR replaces it.
- The API reference is generated from `openapi/openapi.json`; refresh it with
  openapi-sync (`just backend openapi`) and never edit endpoint pages by hand.
- Describe the current code. Remove plans once they are implemented instead of
  archiving them.

## Enforced gates

`just agent-check` (frontmatter titles and local links), `just docs check`
(`tsc` and Biome) and the prerendering build. A failure is a project rule, not
noise.
