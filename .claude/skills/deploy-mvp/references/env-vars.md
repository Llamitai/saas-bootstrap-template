# Environment variable catalog

Contents: [Tier 1](#tier-1--application-secrets-stored-in-infisical) ·
[Backend project](#backend-project) · [Frontend project](#frontend-project) ·
[Invariants](#cross-service-invariants--verify-before-declaring-success) ·
[Tier 2](#tier-2--bootstrap-variables-portainer-stack-env) ·
[Tier 3](#tier-3--ci-configuration-github) ·
[Two names that need a decision](#two-names-that-need-a-decision) ·
[Unset variables](#why-an-unset-variable-is-dangerous)

Three distinct tiers. Confusing them is the single most common cause of a
broken first deploy.

| Tier | Lives in | Read by | Count |
| --- | --- | --- | --- |
| **1. Application secrets** | Infisical project | The app process, injected at container start by `infisical run` | ~45 |
| **2. Bootstrap variables** | Portainer stack env (sent by CI as `env_data`) | The container entrypoint, to reach Infisical; compose for Directus | 5 (+ `IMAGE_TAG`; backend adds 8 Directus keys) |
| **3. CI variables** | GitHub environment vars + secrets | GitHub Actions workflows | 16 variables + 8 secrets (`github_setup.sh`) |

The container never receives tier 1 from Portainer. Portainer only supplies
tier 2; the entrypoint uses those to log into Infisical and pull tier 1 at
boot. See `infisical.md` § Runtime injection.

---

## Tier 1 — Application secrets (stored in Infisical)

These are the keys from `backend/.env.example` and `frontend/.env.example`.
Seed them into the Infisical project for the target environment (`prod`).

### Backend project

```dotenv
# --- General ---
STAGE=prod
ENVIRONMENT=production
CORS_ORIGINS=https://app.example.com

# --- Google login ---
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://app.example.com/api/auth/google/callback
GOOGLE_CERTS_URL=https://www.googleapis.com/oauth2/v3/certs

# --- JWT ---
JWT_SECRET_KEY=            # openssl rand -hex 32  (>= 32 chars, REQUIRED in prod)
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_MINUTES=10080

# --- Common ---
SECRET_KEY=                # openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n'

# --- Database (from phase 1: provisioning) ---
POSTGRES_USER=<project_user>
POSTGRES_DB=<project_db>
POSTGRES_HOST=<db host reachable from the Docker network>
POSTGRES_PORT=5432
POSTGRES_PASSWORD=<generated>

# --- Valkey (Redis protocol; REDIS_* names) ---
# The production compose files ship NO Valkey service: use a Valkey the backend
# container can reach, configured like backend/docker/valkey/valkey.conf
# (maxmemory-policy allkeys-lru, appendonly yes): the refresh-session allowlist
# fails closed, so eviction only forces a re-login. Settings refuse to start in production without
# REDIS_PASSWORD (backend/src/common/settings.py validate_secrets), and the
# production redis_url embeds REDIS_USER verbatim — unset becomes "None".
REDIS_HOST=<redis reachable from the backend container>
REDIS_USER=default           # "default" for a requirepass-only Redis
REDIS_PASSWORD=              # REQUIRED in prod
REDIS_PORT=6379
REDIS_DB=0

# --- RabbitMQ (deferred commands: API publishes, worker consumes) ---
# The production compose files ship NO broker: provision RabbitMQ 4.x reachable
# from shared-network with the stability settings of
# backend/docker/rabbitmq/rabbitmq.conf. API and worker fail at startup if it is
# unreachable. Settings reject a missing or default ('app'/'guest') password.
RABBITMQ_HOST=<rabbitmq reachable from the backend container>
RABBITMQ_PORT=5672
RABBITMQ_USER=<dedicated user>
RABBITMQ_PASSWORD=           # REQUIRED in prod
RABBITMQ_VHOST=/             # or a dedicated vhost the user can configure/write/read

# --- Email ---
SMTP_HOST=
SMTP_PORT=587
SMTP_TLS=true
SMTP_USERNAME=
SMTP_PASSWORD=
DEFAULT_FROM_EMAIL=no-reply@example.com

# --- Storage (S3-compatible) ---
AWS_S3_ENDPOINT_URL=       # empty for real AWS S3
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_REGION_NAME=us-east-1
AWS_STORAGE_BUCKET_NAME=
AWS_S3_PUBLIC_URL=
AWS_CLOUDFRONT_DOMAIN=

# --- Monitoring ---
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
SENTRY_SEND_DEFAULT_PII=false

# --- Frontend / admin ---
FRONTEND_HOST=https://app.example.com
ADMIN_API_KEY=             # openssl rand -hex 32 — MUST equal frontend BACKEND_API_KEY
ADMIN_LOGO_URL=
ADMIN_LOGIN_LOGO_URL=
DIRECTUS_SECRET=            # read by the local compose; prod Directus uses the
DIRECTUS_ADMIN_PASSWORD=    # ADMIN_* stack block (Tier 2) instead
```

### Frontend project

```dotenv
NEXT_PUBLIC_BACKEND_API_HOST=https://api.example.com
BACKEND_API_HOST=https://api.example.com  # see note below
BACKEND_API_KEY=                      # MUST equal backend ADMIN_API_KEY
NEXT_PUBLIC_VERSION=1.0.0
NEXT_PUBLIC_APP_URL=https://app.example.com
NODE_ENV=production
SENTRY_DSN=
GOOGLE_CLIENT_ID=
TRUSTED_CLIENT_IP_HEADER=cf-connecting-ip  # header the edge sets with the real client IP
```

`TRUSTED_CLIENT_IP_HEADER` names the header the edge proxy sets (`cf-connecting-ip`
behind Cloudflare, `x-real-ip` behind nginx). The BFF sends that IP as
`X-Client-IP`, which the backend trusts only with the API key, so rate limits
apply per browser. Unset, the last `X-Forwarded-For` hop is used and a client
that reaches Next directly can choose it.

`BACKEND_API_HOST` is the server-side (BFF) route to the backend.
`frontend/docker-compose.prod.yml` joins **no** shared network, so the
internal address `http://api:8200` does not resolve from the `web` container.
Use the public API origin (or another address the frontend host can reach,
such as the backend's published host port). Only if the frontend compose is
changed to join `shared-network` does `http://api:8200` work.

### Cross-service invariants — verify before declaring success

- `ADMIN_API_KEY` (backend) **==** `BACKEND_API_KEY` (frontend). Mismatch → every
  BFF call 401s.
- `GOOGLE_REDIRECT_URI` must be registered verbatim in the Google Cloud console.
- `CORS_ORIGINS` must contain the frontend's public origin.
- `JWT_SECRET_KEY` empty in production is a hard failure (dev auto-generates; prod does not).
- `JWT_SECRET_KEY`, `SECRET_KEY`, `ADMIN_API_KEY`, `POSTGRES_PASSWORD`,
  `REDIS_PASSWORD` and `RABBITMQ_PASSWORD` are all required when
  `ENVIRONMENT=production`; placeholder values are rejected at startup.

---

## Tier 2 — Bootstrap variables (Portainer stack env)

The only variables the stack itself needs. Everything else arrives from
Infisical at container start.

```dotenv
INFISICAL_MACHINE_CLIENT_ID=       # secret
INFISICAL_MACHINE_CLIENT_SECRET=   # secret
PROJECT_ID=                        # Infisical project id for THIS service
INFISICAL_SECRET_ENV=prod          # Infisical environment slug
INFISICAL_API_URL=https://secrets.example.com
IMAGE_TAG=sha-abc1234              # optional; compose defaults to :latest
```

Backend stacks additionally need the Directus admin block, because those
values are consumed by the `directus-admin` service in
`backend/docker-compose.prod.yml` via compose substitution — not by the app:

```dotenv
ADMIN_SECRET=
ADMIN_EMAIL=
ADMIN_PASSWORD=
ADMIN_DB_HOST=
ADMIN_DB_DATABASE=
ADMIN_DB_USER=
ADMIN_DB_PASSWORD=
ADMIN_PUBLIC_URL=
```

> Directus needs its **own** database, separate from the application database.
> Provision it in phase 1 alongside the app database.

Every CI deploy sends this whole set as the action's `env_data`, which
**replaces** the stack env, so the GitHub environment (Tier 3) is the durable
source. For a stack created by hand, SKILL.md Phase 4 Path B builds
`.env.deploy.stack.backend` / `.env.deploy.stack.frontend` from
`.env.deploy.ci` for `portainer_stack.py create --stack-env`.

---

## Tier 3 — CI configuration (GitHub)

Configured **before the first CI build** (SKILL.md Phase 3): the build
workflows name the image from `vars.*_REPOSITORY_URI`, and their deploy step
creates or updates the Portainer stack from the other names below.

Set on **both** deployment environments, `Production` and `Development`. The
workflows pick one with:

```yaml
environment: ${{ github.event.workflow_run.head_branch == 'main' && 'Production' || 'Development' }}
```

(the build workflows run on `workflow_run` after `Code Quality`, so the branch
comes from the triggering run), so `main` reads `Production` and `dev` reads
`Development`. `rollback.yml` takes the environment as an input instead. Every name below
needs a value in each environment you actually deploy to — a name set only on
`Production` silently expands to `""` on a `dev` push.

`bash <skill-dir>/scripts/github_setup.sh --env-file .env.deploy.ci --environment <name>`
sets exactly this list: 16 variables and 8 secrets. It reads one file, so the
`ADMIN_DB_*` values phase 1 wrote to `.env.deploy.generated` must be merged in
first (SKILL.md Phase 3).

### Variables — `gh variable set` (readable in plaintext by anyone with repo access)

```dotenv
ADMIN_DB_DATABASE=<slug>_directus
ADMIN_DB_HOST=
ADMIN_DB_USER=<slug>
ADMIN_EMAIL=
ADMIN_PUBLIC_URL=https://admin.example.com

BACKEND_DEPLOYMENT_COMPOSE_FILE=backend/docker-compose.prod.yml
BACKEND_DEPLOYMENT_SERVICE=<portainer stack name>
BACKEND_PROJECT_ID=<infisical project id>
BACKEND_REPOSITORY_URI=ghcr.io/<org>/<project>-api-prod

FRONTEND_DEPLOYMENT_COMPOSE_FILE=frontend/docker-compose.prod.yml
FRONTEND_DEPLOYMENT_SERVICE=<portainer stack name>
FRONTEND_PROJECT_ID=<infisical project id>
FRONTEND_REPOSITORY_URI=ghcr.io/<org>/<project>-web-prod

INFISICAL_API_URL=https://secrets.example.com
INFISICAL_SECRET_ENV=prod

PORTAINER_URL=https://portainer.example.com
```

### Secrets — `gh secret set` (encrypted, never readable back)

```dotenv
ADMIN_DB_PASSWORD=
ADMIN_PASSWORD=
ADMIN_SECRET=

CF_ACCESS_CLIENT_ID=
CF_ACCESS_CLIENT_SECRET=

INFISICAL_MACHINE_CLIENT_ID=
INFISICAL_MACHINE_CLIENT_SECRET=
PORTAINER_TOKEN=
```

`GITHUB_TOKEN` is injected automatically and is what pushes to GHCR — no PAT is
needed to push from Actions in the same repository.

### Two names that need a decision

Running `github_setup.sh --audit` against **this** repository reports this
pair as *configured but read by no workflow*:

- **`CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET`** — these exist because
  Portainer sits behind Cloudflare Access, but **no workflow currently passes
  them**. Storing them alone does nothing. To use them, add the `headers:`
  input to the Portainer deploy step:

  ```yaml
  headers: >
    {
      "CF-Access-Client-Id": "${{ secrets.CF_ACCESS_CLIENT_ID }}",
      "CF-Access-Client-Secret": "${{ secrets.CF_ACCESS_CLIENT_SECRET }}"
    }
  ```

  Without it, Cloudflare answers the deploy step with its **login page as HTTP
  200 with an HTML body**, so the failure reads as a malformed Portainer
  response rather than an auth error. See `ghcr.md` § Cloudflare Access.

  If deploys currently succeed without this, Access is not actually enforcing
  on the CI path (an IP allowlist or bypass rule) — worth confirming rather
  than assuming.

### Why an unset variable is dangerous

An unset `vars.*` expands to an **empty string** in Actions — it is not an
error. The deploy step then targets a stack named `""`, the action finds no
match, and it happily *creates a new stack* or reports success having changed
nothing. `github_setup.sh --audit` cross-checks every `${{ vars.X }}` and
`${{ secrets.X }}` in the deploy workflows against what is configured, which is
the only reliable way to catch this before it bites.

---

## Where the repo already records this

- `.env.deploy.example` — root, groups by vars/secrets
- `backend/.env.deploy.example`, `frontend/.env.deploy.example` — per service
- `backend/.env.example`, `frontend/.env.example` — tier 1 source of truth

Regenerate the tier-1 checklist from the repo rather than trusting this file
if the app has gained settings since:

```bash
grep -oE '^[A-Z0-9_]+=' backend/.env.example | tr -d '='
```
