# syntax=docker/dockerfile:1
#
# Base images are pinned by tag + digest; Dependabot (docker ecosystem) bumps both.
# Debian bookworm is kept deliberately (python:3.14-slim-trixie exists; moving
# is a separate, tested change).

# uv binary source. The uv *-bookworm-slim variants are no longer published, so
# uv is copied into the official Python image instead.
FROM ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 AS uv

# Infisical CLI, verified through the official APT repository: the signing key
# must match the pinned fingerprint and APT checks the package hash against the
# signed index. Only the static binary reaches the runtime image.
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


#  P R O D U C T I O N   B U I L D E R
#
FROM python:3.14-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS production_builder
COPY --from=uv /uv /uvx /bin/
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_DEV=1 \
    UV_PROJECT_ENVIRONMENT=/venv

WORKDIR /app

# Some deps may lack prebuilt Python 3.14 wheels (cffi, asyncpg, ...), so uv
# can compile them from source; this stage alone carries the C toolchain.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libffi-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


#  P R O D U C T I O N
#
FROM python:3.14-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS production

# Runtime libraries only (bash ships with the base image).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libpq5 poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=infisical /usr/local/bin/infisical /usr/local/bin/infisical
COPY --from=production_builder --chown=app:app /app /app
COPY --from=production_builder --chown=app:app /venv /venv

# Entrypoint scripts stay root-owned and read/execute-only for the app user.
COPY --chmod=0755 docker/commands /commands
COPY --chmod=0755 docker/start-prod /start
COPY --chmod=0755 run-script /run-script
RUN sed -i 's/\r$//g' /commands /start /run-script

ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    INFISICAL_DISABLE_UPDATE_CHECK=true

WORKDIR /app
USER app:app

EXPOSE 8200

# Liveness only (no dependencies); readiness lives at /api/py/health/ready.
# start-period covers the Infisical login and `alembic upgrade head`.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8200/api/py/health', timeout=4).status == 200 else 1)"]

# /start <role>: api (default; migrates then serves), worker (RabbitMQ consumer) or migrate.
CMD ["/start", "api"]

#
#  D E V E L O P M E N T
#
FROM python:3.14-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS development

COPY --from=uv /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils build-essential libffi-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.14 \
    UV_PROJECT_ENVIRONMENT=/venv

ENV PATH="/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock /app/
RUN uv sync --locked --no-install-project

COPY docker/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY docker/start-dev /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start


ENTRYPOINT ["/entrypoint"]
CMD ["/start"]
