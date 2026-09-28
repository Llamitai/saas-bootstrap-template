# Frontend constitution

Binding for any change under `frontend/`. The root [AGENTS.md](../AGENTS.md)
still applies; this file adds the frontend rules.

## Read for the task

- [Frontend architecture](../docs/content/docs/conceptos/arquitectura-frontend.md)
  is authoritative. Read the sections relevant to the change: §§3–4 for feature
  and import boundaries, §§5–7 for server/client and HTTP/BFF/session behavior,
  §§8–11 for state, UI and configuration, and §12 for test layout. Paths there
  are relative to `frontend/`. Target-only ideas in
  [the roadmap](../docs/content/docs/conceptos/roadmap-frontend.md) are not rules
  until implemented.
- For building or restyling UI, read [PRODUCT.md](../PRODUCT.md) and
  [DESIGN.md](../DESIGN.md); live tokens are in `src/app/globals.css`.

## Commands

Run from the Git root: `just frontend <recipe>`. `just frontend check` is static
without autofix; `just frontend code_quality` autofixes; `just frontend verify`
adds Vitest and the build. Browser → BFF → API journeys run with
`just integration`.

## Architecture

- Keep `app -> features -> entities -> shared`, public slice facades
  (server-only code behind `<feature>/server.ts`) and thin routes. Never
  reintroduce global DDD layers.
- Browser requests stay same-origin under `/api` through the shared HTTP
  helpers; server-only code may call the backend through `backendHeadersFrom`,
  which forwards the client IP and adds infrastructure credentials. Keep those
  credentials out of client code.
- Only `proxy.ts` and route handlers rotate tokens or set cookies; route
  handlers read cookies from the request. Server Components read the session
  without rotating it. Only a token rejection (`isSessionRejected`) ends a
  session; 429, 5xx and network failures keep the cookies.
- TanStack Query owns remote state and Zustand client state; a scope change
  destroys the cache. User-visible text, metadata titles and aria labels come
  from the locale catalogs.
- Use impeccable for design work. Preserve forms, i18n/themes, keyboard access
  and observable error/recovery states.

## Enforced gates

`pnpm lint:boundaries` (layers, facades, server-only imports), Biome (including
its a11y rules) and `tsc`. A failure is a project rule, not noise.
