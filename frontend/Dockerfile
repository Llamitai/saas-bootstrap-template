FROM node:24-slim AS deps

WORKDIR /app

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
ENV COREPACK_ENABLE_STRICT=1
RUN corepack enable && corepack prepare pnpm@11.1.2 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile


FROM node:24-slim AS builder

WORKDIR /app

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
ENV COREPACK_ENABLE_STRICT=1
RUN corepack enable && corepack prepare pnpm@11.1.2 --activate

COPY --from=deps /app/node_modules ./node_modules
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN pnpm build


# Infisical CLI, verified through the official APT repository: the signing key
# must match the pinned fingerprint and APT checks the package hash against the
# signed index. Only the static binary reaches the runtime image, so curl and
# gnupg stay out of it.
FROM debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251 AS infisical
# Pin matched to the self-hosted server's API surface: 0.43.99 targets
# /api/v4/secrets. Override at build time once the server is bumped.
ARG INFISICAL_CLI_VERSION=0.43.99
ARG INFISICAL_GPG_FINGERPRINT=698CE22DCBD9C67562F3C4749CC397EDC268078E
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /tmp
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://artifacts-cli.infisical.com/infisical.gpg -o /tmp/infisical.asc \
    && test "$(gpg --show-keys --with-colons /tmp/infisical.asc | awk -F: '$1 == "fpr" { print $10; exit }')" = "${INFISICAL_GPG_FINGERPRINT}" \
    && gpg --dearmor < /tmp/infisical.asc > /usr/share/keyrings/infisical-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/infisical-archive-keyring.gpg] https://artifacts-cli.infisical.com/deb stable main" \
        > /etc/apt/sources.list.d/infisical.list \
    && apt-get update \
    && apt-get download "infisical=${INFISICAL_CLI_VERSION}" \
    && dpkg-deb -x "infisical_${INFISICAL_CLI_VERSION}_$(dpkg --print-architecture).deb" /tmp/infisical-root \
    && install -m 0755 /tmp/infisical-root/usr/bin/infisical /usr/local/bin/infisical \
    && /usr/local/bin/infisical --version \
    && rm -rf /var/lib/apt/lists/* /tmp/infisical*


FROM node:24-slim AS production

WORKDIR /app

RUN groupadd -r -g 1001 nodejs && \
    useradd -r -u 1001 -g nodejs -m -s /bin/bash -d /home/nodejs nodejs

# ca-certificates: the Infisical CLI (Go) verifies TLS with the system store.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates tzdata && \
    rm -rf /var/lib/apt/lists/*

COPY --from=infisical /usr/local/bin/infisical /usr/local/bin/infisical

COPY --from=builder --chown=nodejs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nodejs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nodejs:nodejs /app/public ./public

COPY --chown=nodejs:nodejs docker/commands.sh /commands
COPY --chown=nodejs:nodejs docker/start.sh /start

RUN sed -i 's/\r$//g' /commands /start && \
    chmod 550 /commands /start

USER nodejs

ENV NODE_ENV=production
ENV PORT=3200
ENV HOSTNAME=0.0.0.0

# NOTE: Only use in development/staging with self-signed certs
# For production, ensure your backend has valid SSL certificates
# ENV NODE_TLS_REJECT_UNAUTHORIZED=0

EXPOSE 3200

# Any non-5xx answer from the Next.js server counts as alive; redirects are not
# followed so the probe never leaves the container.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3200/', { redirect: 'manual', signal: AbortSignal.timeout(4000) }).then((r) => process.exit(r.status < 500 ? 0 : 1), () => process.exit(1))"]

CMD ["/start"]
