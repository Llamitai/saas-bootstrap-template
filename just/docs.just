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

# Type-check
typecheck:
    pnpm types:check
