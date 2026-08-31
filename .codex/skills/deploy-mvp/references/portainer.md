# Portainer API reference

Verified against the Portainer CE source (`release/2.19` … `release/2.33`) and
the `cssnr/portainer-stack-deploy-action@v2` source. Applies to Portainer CE
2.19+; Business Edition adds fields not covered here.

Base URL shape: `{PORTAINER_URL}/api/...` — the operator supplies the bare
origin and `/api` is part of every path.

## Authentication

Two mechanisms, both accepted on the same endpoints:

| Method | Header | Notes |
| --- | --- | --- |
| API access token | `X-API-Key: ptr_…` | **Use this.** Long-lived, made for CI. |
| JWT | `Authorization: Bearer <jwt>` | From `POST /api/auth`; expires (default 8h). |

Create a token in the UI: username menu (top right) → **My account** →
**Access tokens** → **Add access token**. Shown once. The token inherits
exactly the permissions of the user that owns it, so a non-admin token gets
403 `Stack creation is disabled for non-admin users` where that setting applies.

### Behind Cloudflare Access

If Portainer sits behind Cloudflare Access, every API call additionally needs a
service token:

```
CF-Access-Client-Id: <client-id>
CF-Access-Client-Secret: <client-secret>
```

Without them Cloudflare answers with its **login page, HTTP 200, HTML body** —
so a JSON parse error, not a 401, is the symptom. `portainer_stack.py` detects
that case and says so. In GitHub Actions, pass them through the deploy action's
`headers` input (see `ghcr.md` § Cloudflare Access).

## Find the environment (endpoint) id

```
GET /api/endpoints?excludeSnapshots=true
```

The field you need is **`Id`** — not `EndpointID`. (Confusingly, on a *stack*
object the same value is called `EndpointId`.) Mixing them up is the most
common cause of a stack landing on the wrong host.

`Type`: 1 local Docker, 2 agent on Docker, 3 Azure, 4 edge agent, 5 local k8s.
`Status`: 1 up, 2 down. A single-node install is usually `Id: 1`.

`excludeSnapshots=true` matters — without it the response includes a full
container/image snapshot per environment and can be megabytes.

## Create a standalone Compose stack from Git

```
POST /api/stacks/create/standalone/repository?endpointId=N
```

```jsonc
{
  "name": "acme-backend-prod",
  "repositoryURL": "https://github.com/acme/app",   // trailing / stripped server-side
  "repositoryReferenceName": "refs/heads/main",     // blank = default branch
  "composeFile": "backend/docker-compose.prod.yml", // blank = docker-compose.yml
  "additionalFiles": [],
  "repositoryAuthentication": true,
  "repositoryUsername": "x-access-token",
  "repositoryPassword": "ghp_…",   // REQUIRED when repositoryAuthentication is true
  "tlsskipVerify": false,
  "fromAppTemplate": false,
  "env": [{"name": "IMAGE_TAG", "value": "sha-abc1234"}],
  "autoUpdate": null
}
```

Responses: **200** the stack object · **400** invalid · **409 the stack name
(or webhook UUID) already exists** · **500**.

Treat 409 as "already exists → redeploy instead". Names are normalized
(lowercased/sanitized) before the uniqueness check, so two names that differ
only in case collide.

> **Never use** `POST /api/stacks?type=2&method=repository`. That legacy
> rewrite was **removed in 2.27.0** (commit `a245e939`, 2025-02-09) and is also
> absent from 2.19.0 due to a regression. The canonical route above works on
> every 2.19+ release.

### autoUpdate

Omit it or send `null` for no GitOps. If you send the object, validation
requires **at least one** of `webhook` (must be a valid UUID, generate it
yourself) or `interval` (Go duration: `5m`, `1m30s`). Sending an object with
both empty is a 400.

## Redeploy an existing Git stack

```
PUT /api/stacks/{stackId}/git/redeploy?endpointId=N
```

```jsonc
{
  "repositoryReferenceName": "refs/heads/main",
  "repositoryAuthentication": true,
  "repositoryPassword": "",     // empty + auth true = keep the stored password
  "env": [ /* the FULL set */ ],
  "pullImage": true,
  "prune": false
}
```

> ### The env-wipe trap
>
> This payload's `Validate()` is a no-op, and the handler runs
> `stack.Env = payload.Env` and
> `stack.GitConfig.ReferenceName = payload.RepositoryReferenceName`
> **unconditionally**. Every omitted field is applied as its zero value:
>
> - omit `env` → **all stored stack variables are deleted**
> - omit `repositoryReferenceName` → **the tracked branch is blanked**
>
> Always `GET /api/stacks` first and echo the existing `Env` back, merged with
> whatever you are changing. `portainer_stack.py redeploy` does this by
> default; `--replace-env` opts out and lists what it will drop.

`prune` is **ignored** for standalone Compose — the handler only applies it
`if stack.Type == DockerSwarmStack`. `pullImage: true` forces a
`docker compose pull` even when the tag string is unchanged, which is what you
need for mutable tags like `:latest`.

`PUT /api/stacks/{id}` (no `/git/redeploy`) is for **file-based stacks only**;
it requires a non-empty `stackFileContent` and detaches the stack from Git.

## Find a stack by name

```
GET /api/stacks?filters={"EndpointID":1}
```

There is **no name filter** — `filters` accepts only
`{SwarmID, EndpointID, IncludeOrphanedStacks}`. Match `.Name` client-side, and
match `.EndpointId` too, because the same name can exist on several
environments.

It can return **204 No Content** rather than `[]` when there are no stacks —
guard against an empty body.

## How stack env vars actually reach containers

They do **not** become container environment automatically.

At deploy time Portainer writes `<ProjectPath>/stack.env` containing first a
copy of the repo's own `.env` (if present next to the entrypoint), then the
stack's `Env` pairs, and passes that file as Compose's `--env-file`. So they
are **interpolation variables** for `${VAR}` in the compose YAML. Because the
stack pairs are written last, they win over the repo's `.env`.

To get a value inside a container you must still reference it:

```yaml
services:
  api:
    environment:
      FOO: ${FOO}
```

which is exactly what `backend/docker-compose.prod.yml` does for the Infisical
bootstrap block.

Env vars persist on the stack record, so webhook- and interval-triggered
redeploys reuse the stored set.

## Webhooks

```
POST /api/stacks/webhooks/{webhookUUID}
```

**No authentication** — the route is registered with `PublicAccess`. Anyone who
learns the UUID can trigger a redeploy, so treat it as a secret.

It returns **200 immediately** and does the work in a background goroutine, so
200 means "accepted", not "deployed". Poll `GET /api/stacks/{id}`
(`UpdateDate`, `Status`) to confirm.

A webhook redeploy only acts **if the git commit hash changed**, unless
`AutoUpdate.ForceUpdate` is set. Pushing a new image tag without a new commit
does nothing — use `PUT /stacks/{id}/git/redeploy` with the new `env` instead.

Returns **409 "Autoupdate for the stack isn't available"** when the user who
created or last updated the stack has been deleted (the redeploy runs as
`stack.UpdatedBy || stack.CreatedBy`). Create stacks with a service account you
will not delete.

## The community GitHub Action

`cssnr/portainer-stack-deploy-action@v2` wraps the same calls: it resolves the
endpoint, `GET /stacks`, then either `POST /stacks/create/standalone/repository`
or `PUT /stacks/{id}/git/redeploy`.

Three defaults worth knowing:

| Input | Default | Why it matters |
| --- | --- | --- |
| `standalone` | **`false`** | i.e. it assumes **Swarm**. Must be `true` for plain Docker, or it calls `/docker/swarm` and fails. |
| `endpoint` | first endpoint from `GET /api/endpoints` | On multi-environment Portainer this silently picks the wrong host. Always set it. |
| — | — | Its axios client sets `rejectUnauthorized: false` **unconditionally** — TLS verification against Portainer is always off. |

Env semantics: with neither `env_data` nor `env_file`, it re-sends the stack's
existing `Env` verbatim (nothing is lost). With either, it **replaces** the
whole set unless `merge_env: true`.

The action never sets `autoUpdate`, so it does not create webhooks.

Extra headers (Cloudflare Access) go through the `headers` input as a JSON
string.

## Version check

```
GET /api/system/version
```

Returns `ServerVersion`, `ServerEdition` (`CE`/`EE`), `DatabaseVersion`.
Useful to gate EE-only behaviour.

## Sources

- `portainer/portainer` `api/http/handler/stacks/*.go` (release/2.19 … 2.33)
- `api/http/security/bouncer.go`, `api/stacks/deployments/deploy.go`
- <https://docs.portainer.io/api/access>
- `cssnr/portainer-stack-deploy-action` `action.yml`, `src/portainer.js`
