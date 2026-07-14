# Frontend — Next.js (port 3000). Run: just frontend <command>

set dotenv-load := false
set working-directory := "../frontend"

# List frontend commands
default:
    @just --list frontend

# Start the dev server
dev:
    pnpm dev

# Build for production
build:
    pnpm build

# Install dependencies
install:
    pnpm install

# Run unit tests
test:
    pnpm test

# ─── CODE QUALITY ───────────────────────────────────────────────

# Format with Biome
format:
    pnpm format:write

# Lint with Biome (safe autofix only)
lint:
    pnpm lint:fix

# Type-check with TypeScript
typecheck:
    pnpm type-check

# Enforce feature-first architecture boundaries
lint-imports:
    pnpm lint:boundaries

# Run format + lint + typecheck + architecture boundaries
code_quality: format lint typecheck lint-imports

# Full quality gate (type-check + biome + tests + boundaries + build)
verify:
    pnpm verify

# ─── E2E (Playwright) ────────────────────────────────────────────

# Run e2e tests headless
e2e:
    pnpm test:e2e

# Open the Playwright UI for interactive e2e testing
e2e-ui:
    pnpm exec playwright test --ui

# Run e2e tests with a visible browser
e2e-headed:
    pnpm exec playwright test --headed

# Run a single e2e spec: just frontend e2e-spec tests/end-to-end/example.spec.ts
e2e-spec spec:
    pnpm exec playwright test "{{spec}}"
