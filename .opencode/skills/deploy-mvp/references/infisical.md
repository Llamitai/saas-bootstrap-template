# Infisical API and CLI reference

Base URL shape: `{origin}/api/...` — pass the **bare origin**
(`https://secrets.example.com`), never with `/api` appended. The CLI appends
`/api` itself; direct HTTP calls include it in the path.

> **The secrets API is v4.** The entire `/api/v3/secrets/raw` family still
> responds but is filed under *deprecated* in the official docs. v4 drops the
> `raw` path segment and replaces `workspaceId`/`projectSlug` with a single
> required `projectId`. This repo's `backend/Dockerfile` already pins
> `INFISICAL_CLI_VERSION=0.43.99` with a comment noting it targets
> `/api/v4/secrets` — keep the CLI pin and the server in step.

## Authentication — machine identity (Universal Auth)

The only unauthenticated call. Everything else uses its output as
`Authorization: Bearer <accessToken>`.

```
POST /api/v1/auth/universal-auth/login
{"clientId": "<uuid>", "clientSecret": "<secret>"}
```

```jsonc
// 200
{"accessToken": "…", "expiresIn": 7200, "accessTokenMaxTTL": 7200, "tokenType": "Bearer"}
```

`expiresIn` is **seconds**; the default is 7200 (2 hours). That TTL is why the
container entrypoint mints a fresh token at boot rather than baking one in.

Service tokens are the older mechanism and are being deprecated in favour of
identities. `INFISICAL_TOKEN` accepts either.

### Creating the identity (one-time, needs an admin token)

1. `POST /api/v1/identities` — `{name, organizationId, role: "no-access"}`.
   Keep the org role at `no-access` and grant project scope separately.
2. `POST /api/v1/auth/universal-auth/identities/{identityId}` — attaches
   Universal Auth and yields the **clientId** (not secret).
3. `POST /api/v1/auth/universal-auth/identities/{identityId}/client-secrets` —
   returns `clientSecret` **once**. Capture it immediately; later reads return
   only the prefix.
4. `POST /api/v1/projects/{projectId}/identity-memberships/{identityId}` —
   `{role: "admin", roles: [{role: "admin", isTemporary": false}]}`.

Shortcut: `POST /api/v1/projects/{projectId}/identities` creates the identity
*and* its project membership in one call, but you still need steps 2 and 3.

## Projects

```
POST /api/v1/projects        {"projectName": "acme-backend", "type": "secret-manager"}
GET  /api/v1/projects?type=secret-manager
GET  /api/v1/projects/slug/{slug}
```

Only `projectName` is required (max 64). An explicit `slug` has a **5-character
minimum**. `shouldCreateDefaultEnvs` defaults true, giving you `dev`/`staging`/
`prod`. The response's **`project.id`** is what every other call means by
`projectId` (and what v3 called `workspaceId`).

Read environment slugs from the project object's `environments` array rather
than assuming them.

```
POST /api/v1/projects/{projectId}/environments   {"name": "Production", "slug": "prod"}
```

## Seeding secrets — use the batch upsert

```
PATCH /api/v4/secrets/batch
```

```jsonc
{
  "projectId": "<uuid>",
  "environment": "prod",
  "secretPath": "/",
  "mode": "upsert",
  "secrets": [
    {"secretKey": "JWT_SECRET_KEY", "secretValue": "…"},
    {"secretKey": "POSTGRES_HOST",  "secretValue": "…"}
  ]
}
```

**`mode` is the whole point.** Its values are `ignore` | `upsert` |
`failOnNotFound`, and the **default is `failOnNotFound`**. With
`mode: "upsert"` this single call creates what is missing and updates what
exists, which makes seeding safely re-runnable — no create-then-fall-back-to-
update dance.

Do not reach for the single-secret `PATCH /api/v4/secrets/{name}`: it has **no
upsert flag** and 404s when the secret does not exist.

Other endpoints:

| Purpose | Call |
| --- | --- |
| Create one | `POST /api/v4/secrets/{secretName}` — body `{projectId, environment, secretValue, secretPath, type}` |
| Create many | `POST /api/v4/secrets/batch` |
| Read all | `GET /api/v4/secrets?projectId=…&environment=…&secretPath=/` |
| Read one | `GET /api/v4/secrets/{secretName}?projectId=…&environment=…` |
| Update/rename | `PATCH /api/v4/secrets/{secretName}` — `newSecretName` renames |

Batch items have **no `type` field** — the shared/personal selector exists only
on the single-secret endpoints. Use `shared` when seeding; `personal` values
are per-user and invisible to a machine identity.

`GET /api/v4/secrets` defaults `expandSecretReferences=true`. When you are
*comparing* stored values (as `infisical_seed.py plan` does) set it to `false`,
or a `${REF}` indirection compares unequal to itself.

## CLI

```bash
export INFISICAL_DISABLE_UPDATE_CHECK=true
export INFISICAL_TOKEN=$(infisical login \
    --method=universal-auth \
    --client-id="$CLIENT_ID" --client-secret="$CLIENT_SECRET" \
    --domain="$INFISICAL_URL" --plain --silent)

infisical secrets set --file=./.env --projectId="$PROJECT_ID" --env=prod
infisical secrets get FOO --plain --silent
infisical export --format=dotenv --output-file=./.env
infisical run --token "$INFISICAL_TOKEN" --projectId "$PROJECT_ID" \
    --env prod --domain "$INFISICAL_URL" -- /your/start/script
```

`infisical secrets set` is upsert by definition. `--projectId` is **required**
when authenticating as a machine identity. `--plain --silent` is what makes the
login output capturable.

### Base URL precedence

`--domain` flag → `INFISICAL_DOMAIN` → `domain` in `.infisical.json` → US cloud.

`INFISICAL_API_URL` is documented as the **legacy** variable — still honoured,
but `INFISICAL_DOMAIN` wins when both are set. This repo uses
`INFISICAL_API_URL` and passes it explicitly as `--domain`, which sidesteps the
precedence question entirely.

> **Gotcha:** if you pass `--domain` at login you must repeat it on *every*
> subsequent command, or you get auth errors against the wrong host.

## Runtime injection — how this repo does it

`backend/docker/start-prod`:

```bash
export INFISICAL_DISABLE_UPDATE_CHECK=true
export INFISICAL_TOKEN=$(infisical login --method=universal-auth \
    --client-id=$INFISICAL_MACHINE_CLIENT_ID \
    --client-secret=$INFISICAL_MACHINE_CLIENT_SECRET \
    --domain=$INFISICAL_API_URL --plain --silent)
exec infisical run \
    --token $INFISICAL_TOKEN --projectId $PROJECT_ID \
    --env $INFISICAL_SECRET_ENV --domain $INFISICAL_API_URL \
    -- /commands
```

The token is minted **inside the container at boot**, so it never outlives the
process and is never stored anywhere. The five variables it needs are exactly
the tier-2 set the Portainer stack supplies.

`infisical run` flags: `--projectId` (required with a machine identity),
`--env`, `--path`, `--token`, `--domain`, `--watch` (restart the child when
secrets change), `--include-imports` (default true), `--expand` (default true).

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Container restart-loops at boot, no app logs | Login failed. Check `PROJECT_ID`, `INFISICAL_SECRET_ENV`, and that the identity has project access. |
| `401` from the login call | Wrong `clientId`/`clientSecret`, or the identity was revoked. |
| Login succeeds, `run` finds no secrets | Right project, wrong `--env` slug or `--path`. Slugs are `prod`, not `Production`. |
| Works locally, fails in the container | The CLI version in the image targets a different API version than the server. Check `INFISICAL_CLI_VERSION` in `backend/Dockerfile`. |
| Token expires mid-run | Default TTL is 2h but it is only needed at boot; a long-lived container that re-reads secrets should use the Infisical agent instead. |

## Sources

- <https://infisical.com/docs/api-reference/overview/introduction>
- <https://infisical.com/docs/cli/commands/run>
- `backend/docker/start-prod`, `backend/Dockerfile` in this repo
