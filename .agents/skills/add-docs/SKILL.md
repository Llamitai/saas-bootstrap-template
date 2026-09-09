---
name: add-docs
description: >
  Write or update an illustrated MDX documentation page in the SaaS Bootstrap
  Fumadocs site under docs/content/docs. Use for site documentation or a diagram
  explaining current code there. Internal notes, ADRs, OpenSpec artifacts and
  product UI belong to their existing workflows.
---

# Add a documentation page

Explain one concrete part of the current boilerplate using the real code and
visuals that help readers understand it. Paths here are relative to the Git root.
The docs app uses React Router + Fumadocs; read installed versions from
`docs/package.json`. Its publishing format is independent of the frontend UI.

## Establish the page

Read the request, existing related pages and `docs/README.md`. Reuse the agreed
subject and audience. If the requested artifact is an ADR, internal engineering
note or change spec, use its existing location and workflow instead of creating
an MDX copy. This skill does not own architectural decisions or acceptance.

Write in Spanish by default, as required by the project. Honor an explicit user
language choice without asking again. This applies to titles, prose, tables,
links and diagram labels; preserve identifiers, paths, enums and syntax.

Choose the existing section that best fits: `conceptos/`, `arquitectura/` or
`operacion/`. Ask only if an unresolved subject/audience choice would materially
change the page; ordinary filename or section selection is an implementation
decision.

## Research and write

Read [reference.md](reference.md) for MDX/frontmatter, sidebar rules, components
and diagram recipes. Trace the actual symbols and flows before drawing: central
ORM models for an ERD, or routers, use cases and adapters for a request flow.
Internal docs help research, but diagrams must describe the installed code.

Use [the page skeleton](templates/doc-template.mdx) as needed. Keep these site
constraints:

- `.mdx` files and ASCII kebab-case slugs under `docs/content/docs/`.
- Required `title` and `description` frontmatter; no duplicate body H1. Start
  with the site's `<Callout title="En resumen">` opener.
- Register the slug in the directory's `meta.json`; new directories also need
  a parent entry and their own `meta.json`.
- Use plain fenced Mermaid for diagrams; the site owns its styling and theme.
  Put SVGs in `docs/public/diagrams/`. Animation must explain motion or change;
  embedded SVG images can use SMIL/CSS, but cannot execute scripts.

Choose complementary diagrams and tables according to the subject, without a
fixed visual quota. Keep prose connected to the diagrams and link to the next
useful page. Do not restate a separate specification or invent product modules.

## Verify and report

Run `just docs build` from the Git root to compile MDX and prerender the routes.
Fix frontmatter, JSX, imports or sidebar problems introduced by the page. A
successful build verifies rendering prerequisites, not diagram accuracy; check
the labels and relationships against the code you researched.

For optional Mermaid inspection, run
`node <skill-dir>/tools/preview-diagram.mjs <file.mdx>` and open its output with
an available browser. Resolve `<skill-dir>` from this loaded skill rather than
assuming a client-specific path. Use
[animated-pipeline.svg](templates/animated-pipeline.svg) when a flow benefits from
an animated illustration.

Report the page path, rendered `/docs/<section>/<slug>` URL and build result.
