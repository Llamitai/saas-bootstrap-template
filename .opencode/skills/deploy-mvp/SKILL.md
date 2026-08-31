---
name: deploy-mvp
description: Run the first production deployment of this project onto the Portainer + Infisical + GitHub Container Registry + GitHub Actions stack. Use when the user asks to "deploy the MVP", "deploy to production for the first time", "set up the deployment", "provision the database and secrets", "create the Portainer stack", "configure GitHub Actions deployment", or in Spanish "desplegar el MVP", "primer despliegue", "configurar el deploy", "crear el stack en Portainer", "cargar los secretos en Infisical". Covers provisioning the Postgres role/database, seeding Infisical, publishing the image to ghcr.io, creating the Portainer stack from the Git repository, wiring GitHub Actions variables and secrets, and verifying that subsequent pushes deploy automatically.
---

# Deploy MVP

Take a project from "code on GitHub" to "running in production, redeploying on
every push to `main`" on this five-part stack:

| Concern | System |
| --- | --- |
| Data | PostgreSQL (existing server, one role + database per project) |
| Secrets | Infisical (one project per service, injected at container start) |
| Images | GitHub Container Registry (`ghcr.io`) |
| Orchestration | Portainer (standalone Docker Compose stack, deployed from the Git repo) |
| CI/CD | GitHub Actions (`.github/workflows/build_*.yml`) |

## How secrets actually flow

Get this wrong and nothing else matters. **Portainer never holds application
secrets.** It holds only the five bootstrap values the container needs to
authenticate to Infisical; the container pulls everything else at boot.

```
GitHub Actions ──build──▶ ghcr.io/<org>/<project>-api-prod:sha-abc1234
      │
      └──deploy──▶ Portainer  ──git clone──▶ backend/docker-compose.prod.yml
                       │                              │
                       │  injects 5 bootstrap vars    │  compose substitution
                       │  (+ Directus block)          ▼
                       └──────────────────────▶  container starts
                                                      │
                                        docker/start-prod runs:
                                        infisical login --method=universal-auth
                                        infisical run --projectId --env -- /commands
                                                      │
                                                      ▼
                                     Infisical  ──~45 app secrets──▶ app process
```

Read `references/env-vars.md` before touching any of the three tiers. The
single most common failure is putting an application secret into the Portainer
stack env, where the app will never see it.

## Safety contract

This skill provisions real infrastructure. Hold to these rules:

1. **Never print a secret value.** Print names, lengths, and fingerprints
   (`sha256 | head -c 8`) — never the value. This includes generated passwords:
   write them straight into Infisical and report only that they were set.
2. **Confirm before every mutation** in a system the user did not explicitly
   ask you to change. Creating a database, creating an Infisical project, and
   creating a Portainer stack each require an explicit go-ahead.
3. **Never `DROP` anything** without the user typing the object name back.
4. **Idempotency first.** Every script here is safe to re-run. If a step
   already happened, detect it and report "already present" rather than
   erroring or duplicating.
5. **Stop at the first failure.** A half-provisioned deploy is worse than none.
   Report exactly which phase failed and what state the earlier phases left.
6. **Never commit credentials.** `.env.deploy` is gitignored; verify before
   writing to it.

## Locate the bundled files

Resolve the absolute directory containing this loaded `SKILL.md`. Use
`<skill-dir>/scripts/...` and `<skill-dir>/references/...` regardless of
whether this skill was loaded from `.claude`, `.codex`, `.opencode`, or
`.agents`. Do not assume they live under the repository's top-level `scripts/`.

All scripts are Python 3 standard library only — no `pip install`, no `curl`.
Run them with `python3 <skill-dir>/scripts/<name>.py --help` to see options.

## Inputs the operator must supply

Collect these **before** starting; ask in one batch rather than one at a time.
Ask the user to place them in `.env.deploy` at the repo root (gitignored) and
read them from there — never inline in a shell command, where they land in
history and logs.

```dotenv
# Postgres superuser (used only in phase 1, never stored)
PGHOST=
PGPORT=5432
PGUSER=postgres
PGPASSWORD=

# Infisical
INFISICAL_API_URL=https://secrets.example.com
INFISICAL_MACHINE_CLIENT_ID=
INFISICAL_MACHINE_CLIENT_SECRET=

# Portainer
PORTAINER_URL=https://portainer.example.com
PORTAINER_TOKEN=

# Project identity
PROJECT_SLUG=            # e.g. acme — used for db/user/image/stack names
GITHUB_REPOSITORY=       # e.g. acme-inc/acme-app
PUBLIC_APP_URL=          # e.g. https://app.acme.com
PUBLIC_API_URL=          # e.g. https://api.acme.com
```

Copy the template with:

```bash
cp "<skill-dir>/assets/env.deploy.template" .env.deploy
```

---

## Phase 0 — Preflight

Never provision blind. Verify every system answers before mutating any of them.

```bash
python3 "<skill-dir>/scripts/preflight.py" --env-file .env.deploy
```

It checks, and reports a table of pass/fail:

- Postgres reachable, credentials valid, server version, whether the target
  role/database already exist.
- Infisical reachable, machine identity authenticates, which projects it can see.
- Portainer reachable, token valid, which environment (endpoint) IDs exist,
  whether a stack with the target name already exists.
- GitHub: `gh auth status`, repo exists, Actions enabled, whether the
  `Production` environment exists.
- Repo: `docker-compose.prod.yml` present for each service, workflows present.

**Do not proceed past a failure.** Fix it or ask the user.

Record the Portainer `endpointId` from this output — phases 4 needs it.

---

## Phase 1 — Provision the database

One role and one database per project, plus a **separate** database for
Directus if the backend stack includes it (it does by default in this repo).

```bash
python3 "<skill-dir>/scripts/provision_db.py" \
  --env-file .env.deploy \
  --name "$PROJECT_SLUG" \
  --with-directus \
  --dry-run
```

Review the emitted SQL with the user, then re-run without `--dry-run`.

The script generates a strong DSN-safe password, creates the role and database
idempotently, and applies the PostgreSQL 15+ schema grants that the naive
`GRANT ALL PRIVILEGES ON DATABASE` does **not** cover — without them migrations
fail with `permission denied for schema public`. See
`references/postgres.md` for the full rationale and the manual SQL if you
prefer to run it by hand.

It writes the generated credentials to `.env.deploy.generated` (gitignored) for
phase 2 to consume, and prints only the key names.

**Verify** before moving on:

```bash
python3 "<skill-dir>/scripts/provision_db.py" --env-file .env.deploy --name "$PROJECT_SLUG" --verify
```

---

## Phase 2 — Seed Infisical

One Infisical project per service (`<project>-backend`, `<project>-frontend`)
so a compromised frontend identity cannot read backend secrets.

1. Build the secret set from the repo's own `.env.example`, so nothing the app
   reads is missed:

   ```bash
   python3 "<skill-dir>/scripts/infisical_seed.py" \
     --env-file .env.deploy \
     --template backend/.env.example \
     --overrides .env.deploy.generated \
     --project-id "$BACKEND_PROJECT_ID" \
     --environment prod \
     --plan
   ```

   `--plan` prints a three-column table — key, source (template / override /
   generated / **MISSING**), and whether it already exists in Infisical. Never
   apply a plan containing `MISSING` values without walking the user through
   each one; those are the settings only a human can supply (OAuth client IDs,
   SMTP credentials, S3 keys).

2. Apply once the plan is clean:

   ```bash
   python3 "<skill-dir>/scripts/infisical_seed.py" ... --apply
   ```

3. Repeat for the frontend project with `--template frontend/.env.example`.

4. Enforce the cross-service invariants listed in `references/env-vars.md`
   (`ADMIN_API_KEY` == `BACKEND_API_KEY`, CORS origins, redirect URIs):

   ```bash
   python3 "<skill-dir>/scripts/infisical_seed.py" --env-file .env.deploy --check-invariants
   ```

API details, auth flow, and the CLI equivalents are in
`references/infisical.md`.

---

## Phase 3 — Publish the first image

The GitHub Actions workflow builds and pushes on every push to `main`, so the
cleanest first image is a workflow run — not a local build. Prefer it: it
proves the CI path works before you depend on it.

```bash
gh workflow run "Build & Deploy / Backend" --ref main
gh run watch
```

If CI is not wired yet (phase 5 hasn't run) or the user wants a local build,
`references/ghcr.md` has the manual `docker buildx` + `docker push` path and
the PAT scopes it needs.

Two things to confirm afterwards:

- The package exists at `ghcr.io/<org>/<project>-api-prod` and is **linked to
  the repository** (via the `org.opencontainers.image.source` label).
- The Portainer host can pull it. GHCR packages are **private by default**;
  either make the package public or add registry credentials on the Docker
  host. `references/ghcr.md` § Private pulls covers both.

This is the most common silent failure: the stack deploys, then the container
never starts because the host gets `denied` pulling the image.

---

## Phase 4 — Create the Portainer stack

Create the stack from the **Git repository**, not from an uploaded compose
file, so redeploys pull the current compose from the branch.

```bash
python3 "<skill-dir>/scripts/portainer_stack.py" create \
  --env-file .env.deploy \
  --endpoint-id 1 \
  --name "${PROJECT_SLUG}-backend-prod" \
  --repo "https://github.com/$GITHUB_REPOSITORY" \
  --ref refs/heads/main \
  --compose backend/docker-compose.prod.yml \
  --stack-env .env.deploy.stack \
  --private-repo \
  --dry-run
```

`.env.deploy.stack` holds only tier-2 bootstrap variables — see
`references/env-vars.md` § Tier 2. If it contains anything from
`backend/.env.example`, you have made the classic mistake; move it to Infisical.

Review the dry-run payload (secrets redacted), then apply without `--dry-run`.

Repeat for the frontend stack with `frontend/docker-compose.prod.yml`.

**Prerequisite:** `backend/docker-compose.prod.yml` attaches to an external
network named `shared-network`. It must already exist on the Docker host:

```bash
docker network create shared-network   # run on the Docker host, once
```

Then confirm the containers are healthy:

```bash
python3 "<skill-dir>/scripts/portainer_stack.py" status \
  --env-file .env.deploy --endpoint-id 1 --name "${PROJECT_SLUG}-backend-prod"
```

If a container is restarting, get its logs through the same script
(`logs --service api --tail 200`) before changing anything. The usual causes,
in order of frequency, are in § Troubleshooting.

---

## Phase 5 — Configure the GitHub environments

This is the step between "the stack exists because I made it" and "the stack
updates itself". Do it **after** phase 4 and **before** relying on any push.

The workflows in `.github/workflows/` already implement build → push → deploy.
They only need their variables — and they need them on **both** `Production`
and `Development`, because they select one by branch:

```yaml
environment: ${{ github.ref == 'refs/heads/main' && 'Production' || 'Development' }}
```

Run for each environment you deploy to:

```bash
bash "<skill-dir>/scripts/github_setup.sh" --env-file .env.deploy --environment Production --dry-run
bash "<skill-dir>/scripts/github_setup.sh" --env-file .env.deploy --environment Production

bash "<skill-dir>/scripts/github_setup.sh" --env-file .env.deploy --environment Development --dry-run
bash "<skill-dir>/scripts/github_setup.sh" --env-file .env.deploy --environment Development
```

It creates the environment if absent (`gh secret set --env` 404s otherwise),
then sets 17 variables and 8 secrets — the exact list is in
`references/env-vars.md` § Tier 3. Values come from the env file and are piped
via stdin, never passed as arguments where they would appear in the process
table. Secret values are never printed, only their length.

Then audit:

```bash
bash "<skill-dir>/scripts/github_setup.sh" --env-file .env.deploy --environment Production --audit
```

The audit extracts every `${{ vars.X }}` and `${{ secrets.X }}` from the deploy
workflows and reports any that is not configured — plus anything configured
that no workflow reads.

> **Why the audit matters:** an unset `vars.*` expands to an **empty string**
> in Actions, not an error. The deploy step then targets a stack named `""`,
> matches nothing, and either creates a stray stack or reports success having
> changed nothing.

Two names in the list need a judgement call — `BACKEND_ECR_REPOSITORY_URI` (no
workflow reads it) and the `CF_ACCESS_*` pair (stored, but not passed to the
Portainer step unless you add a `headers:` input). Both are explained in
`references/env-vars.md` § Two names that need a decision. Raise them with the
user rather than silently setting dead configuration.

> **Note:** In this template repository the deploy steps are guarded by
> `if: ${{ github.repository != 'Llamitai/wise' }}`, so they no-op here and run
> only in projects generated from the template. If you are testing in the
> template itself, that guard is why nothing deploys.

---

## Phase 6 — Verify the loop closes

The deploy is not done until an ordinary push deploys itself.

1. Push a trivial change touching the service path (`backend/**` or
   `frontend/**`) on `main`.
2. `gh run watch` — build, push, and the Portainer deploy step must all pass.
3. Confirm the running image tag advanced:

   ```bash
   python3 "<skill-dir>/scripts/portainer_stack.py" status \
     --env-file .env.deploy --endpoint-id 1 --name "${PROJECT_SLUG}-backend-prod"
   ```

   The reported image tag must equal the new commit's `sha-<short>`.
4. Hit the public URLs: API health endpoint, frontend root, and one
   authenticated round trip through the BFF (proves the
   `ADMIN_API_KEY`/`BACKEND_API_KEY` pair matches).

Only after step 4 report the deployment as complete.

---

## Rollback

The repo ships `.github/workflows/rollback.yml`. Prefer it over manual
intervention — it verifies the image exists before redeploying:

```bash
gh workflow run Rollback \
  -f service=backend -f target_environment=Production -f version=sha-abc1234
```

To find a known-good tag:

```bash
gh api "/orgs/<org>/packages/container/<project>-api-prod/versions" \
  --jq '.[].metadata.container.tags[]' | head -20
```

Rolling back the **image** does not roll back **secrets** or **migrations**.
If the bad deploy changed either, say so explicitly rather than implying the
rollback restored the previous state.

---

## Troubleshooting

| Symptom | Most likely cause | Where to look |
| --- | --- | --- |
| Container restart-loops immediately | Infisical login failed — wrong `PROJECT_ID`, `INFISICAL_SECRET_ENV`, or machine identity lacks project access | `references/infisical.md` § Troubleshooting |
| `denied` / `unauthorized` pulling image | GHCR package private, host not authenticated | `references/ghcr.md` § Private pulls |
| `permission denied for schema public` | PostgreSQL 15+ grants missing | `references/postgres.md` § Schema grants |
| Stack creates but no containers | `shared-network` missing on the host | Phase 4 prerequisite |
| Deploy step succeeds, nothing changes | Empty `vars.*DEPLOYMENT_SERVICE` — targeted a stack name that does not exist | Phase 5 audit |
| Portainer call returns HTML, or 401/403 from CI only | Behind Cloudflare Access without service-token headers | `references/ghcr.md` § Cloudflare Access |
| Redeploy wiped the stack's variables | `env` omitted from `/git/redeploy` — the API applies zero values | `references/portainer.md` § The env-wipe trap |
| App boots but every BFF call 401s | `ADMIN_API_KEY` != `BACKEND_API_KEY` | `references/env-vars.md` § invariants |
| Google login redirect mismatch | `GOOGLE_REDIRECT_URI` not registered in Google Cloud | `references/env-vars.md` |
| Infisical CLI errors on an API path | CLI version pinned in `backend/Dockerfile` (`INFISICAL_CLI_VERSION`) is mismatched with the self-hosted server | `references/infisical.md` § Version pinning |

## Reference index

| File | Contents |
| --- | --- |
| `references/env-vars.md` | The three variable tiers, full catalog, cross-service invariants |
| `references/postgres.md` | Provisioning SQL, PG15+ grants, idempotency, rollback |
| `references/infisical.md` | Machine identity auth, secret CRUD API, CLI, runtime injection |
| `references/portainer.md` | API auth, endpoints, git-stack create/redeploy, webhooks |
| `references/ghcr.md` | Build/push from Actions, package visibility, private pulls, `gh` config |
| `assets/env.deploy.template` | Operator input template |
