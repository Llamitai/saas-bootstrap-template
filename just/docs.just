# Docs — React Router + Fumadocs (port 4321). Run: just docs <command>

set dotenv-load := false
set working-directory := "../docs"

# List docs commands
default:
    @just --list docs

# Start the dev server
dev:
    pnpm dev

# Build for production
build:
    pnpm build

# Preview the static production build locally
preview:
    pnpm start

# Install dependencies
install:
    pnpm install

# ─── CODE QUALITY ───────────────────────────────────────────────

# Format with Biome
format:
    pnpm format:write

# Lint with Biome and organize imports (safe autofix only)
lint:
    pnpm check:fix

# Type-check (React Router typegen + tsc)
typecheck:
    pnpm types:check

# Run format + lint + typecheck
code_quality: format lint typecheck

# Static gate without autofix (typecheck + Biome)
check:
    pnpm check:static
