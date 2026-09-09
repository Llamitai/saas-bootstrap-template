---
name: frontend-change
description: Build or refine Next.js pages, features, forms, state, BFF routes or shared UI. Excludes backend-only work and read-only reviews.
---

# frontend-change

Read `docs/internal/architecture/frontend-architecture.md` first (paths relative to frontend), then the profile and affected contract. Read PRODUCT.md and DESIGN.md before building/restyling UI. Functional work uses one OpenSpec change and incremental [TDD](../tdd/SKILL.md); reuse an already defined scope.

Keep `app -> features -> entities -> shared`, thin routes, public index.ts facades, colocated DTOs/transport and local state. Shared has no product domain or model directory. Add adapters only for real complexity. Browser requests use same-origin /api through shared HTTP helpers; server-only requests may call the backend. Preserve server secrets, cookies, forwarded headers and error envelopes.

Prefer server rendering where suitable and client islands where interaction needs them. TanStack Query owns remote client state; Zustand owns client state. Keep QueryClient stable, include active scope in query identity and invalidate affected data after mutations/context changes. Check zod/forms, loading/empty/success/error/recovery, i18n and themes. UI permission gates complement server authorization.

Build one tested vertical interaction at a time. Use next-best-practices for a Next boundary, vercel-react-best-practices for measured performance, vercel-composition-patterns for composition, or typescript-advanced-types for a difficult type contract; do not load all by default. Use impeccable for visual design/refinement with the project's tokens/components.

Refinement mode: take a concrete finding/objective, preserve behavior, improve composition/state/hierarchy/copy/accessibility in a small step, then renew affected evidence. Check keyboard, focus, labels, narrow viewport and error recovery in the browser. Performance improvements require measurement. New behavior returns to define-change.

`just frontend new-feature <name>` refuses existing features. Run `just frontend verify` for functional work, `just spec-check <id>`, and applicable browser/BFF tests from `docs/internal/verification.md`. A shared contract needs a real browser -> BFF -> API journey. A screenshot or mocked backend does not prove integration. Pass results to [validate-change](../validate-change/SKILL.md).
