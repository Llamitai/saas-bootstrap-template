# GitHub Container Registry and Actions reference

## Action versions

Current majors (verified against each action's `action.yml`):

| Action | Major |
| --- | --- |
| `docker/login-action` | **v4** |
| `docker/metadata-action` | **v6** |
| `docker/build-push-action` | **v7** |
| `docker/setup-buildx-action` | **v4** |
| `docker/setup-qemu-action` | **v4** |

These majors are Node 24 runtime bumps and require Actions Runner ≥ 2.327.1.
No input was renamed. This repo's workflows already use them.

## Build and push

```yaml
permissions:
  contents: read
  packages: write

steps:
  - uses: actions/checkout@v7
  - uses: docker/setup-buildx-action@v4        # REQUIRED for cache type=gha

  - uses: docker/login-action@v4
    with:
      registry: ghcr.io
      username: ${{ github.actor }}
      password: ${{ secrets.GITHUB_TOKEN }}

  - id: meta
    uses: docker/metadata-action@v6
    with:
      images: ${{ vars.BACKEND_REPOSITORY_URI }}
      tags: |
        latest
        type=sha,format=short

  - uses: docker/build-push-action@v7
    with:
      context: backend
      file: backend/Dockerfile
      target: production
      push: true
      tags: ${{ steps.meta.outputs.tags }}
      labels: ${{ steps.meta.outputs.labels }}
      cache-from: type=gha,scope=backend
      cache-to: type=gha,mode=max,scope=backend
```

### Things that silently break

- **Image names must be lowercase.** `metadata-action` auto-lowercases; a
  hand-rolled `docker tag` does not. GitHub's own docs pipe through
  `tr '[A-Z]' '[a-z]'`.
- **`type=gha` cache needs `setup-buildx-action`.** With the default `docker`
  driver it silently does nothing.
- **The default gha cache scope is literally `buildkit`.** Two images built in
  the same repo without distinct `scope=` values clobber each other's cache.
  Always set `scope=backend` / `scope=frontend` on **both** `cache-from` and
  `cache-to`.
- GHA cache is branch-restricted: only the current branch, its base, and the
  default branch are readable. Cold caches on feature branches are expected.
- `exporting to GitHub Actions Cache … maximum timeout reached` is cache-API
  rate limiting. Add `ghtoken=${{ secrets.GITHUB_TOKEN }}` to `cache-to` rather
  than disabling cache.
- Pre-release semver tags do not produce moving tags: with
  `type=semver,pattern={{major}}`, `v2.0.8-beta.67` emits `2.0.8-beta.67`, not
  `2`. Deliberate.

## Package visibility — the most common first-deploy failure

**A newly published GHCR package is private by default, even when the source
repository is public.** The stack deploys, then containers never start because
the Docker host gets `denied` pulling the image.

**There is no REST endpoint to change visibility.** The packages API exposes
`visibility` only as a read field and a list filter. Flipping it is UI-only:

> package page → **Package settings** → **Danger Zone** → **Change visibility**

Public → private is **irreversible**.

### Linking the package to its repository

```dockerfile
LABEL org.opencontainers.image.source=https://github.com/OWNER/REPO
```

This must exist on the **first** push. A package only inherits the linked
repository's access permissions automatically if the link exists *before*
publishing; connecting afterwards keeps the old permissions unless you
explicitly opt in.

`metadata-action` also emits these labels — but derived from the GitHub
repository API via its `github-token` input, **not** from the `images:` input.

### Pulling a private image on the Docker host

`GITHUB_TOKEN` works only inside Actions, and only for packages owned by the
same repository. For a Portainer/VM host you need a **classic** PAT.

> **GitHub Packages does not support fine-grained PATs at all.** Any
> instruction to "create a fine-grained token with Packages: read" is wrong and
> will fail authentication.

Scopes: `read:packages` to pull, `write:packages` to push, `delete:packages` to
delete.

Selecting `write:packages` in the normal UI auto-selects the broad `repo`
scope. Use the pre-scoped URL to avoid that:

```
https://github.com/settings/tokens/new?scopes=read:packages
```

Under SAML SSO the token must additionally be SSO-authorized for the org, or
every pull 403s.

Three ways to give the host credentials:

1. **Docker host login** (simplest):
   ```bash
   echo "$CR_PAT" | docker login ghcr.io -u USERNAME --password-stdin
   ```
   Lands in `~/.docker/config.json`, which the local daemon uses.
2. **Portainer custom registry** (works on CE): Registries → Add registry →
   *Custom registry*, URL `ghcr.io`, Authentication on, username + classic PAT.
3. **Portainer GitHub provider** — Business Edition only.

`GITHUB_TOKEN` is also insufficient when a package namespace was first pushed
from the CLI without being linked to the repo: the unlinked package owns the
namespace and the workflow token has no rights to it. Link it via its settings
page, or delete it and let the workflow recreate it.

## Cloudflare Access

When Portainer sits behind Cloudflare Access, the deploy step needs service
token headers. `cssnr/portainer-stack-deploy-action@v2` takes them via
`headers`:

```yaml
- uses: cssnr/portainer-stack-deploy-action@v2
  with:
    url: ${{ vars.PORTAINER_URL }}
    token: ${{ secrets.PORTAINER_TOKEN }}
    headers: >
      {
        "CF-Access-Client-Id": "${{ secrets.CF_ACCESS_CLIENT_ID }}",
        "CF-Access-Client-Secret": "${{ secrets.CF_ACCESS_CLIENT_SECRET }}"
      }
    # … name, file, repo, ref, standalone: true, endpoint, env_data
```

Without them Cloudflare returns its **login page as HTTP 200 with an HTML
body** — so the failure looks like a malformed Portainer response, not a 401.

> Storing `CF_ACCESS_*` secrets without adding this `headers:` input does
> nothing. Check whether the workflows actually reference them:
> `bash scripts/github_setup.sh --audit` reports configured-but-unreferenced
> names.

## Configuring the repository from the CLI

```bash
# Environments must exist BEFORE `--env` secrets can be set (otherwise 404).
gh api --method PUT repos/OWNER/REPO/environments/Production --input /dev/null

gh variable set PORTAINER_URL --env Production --body "https://portainer.example.com"
gh secret   set PORTAINER_TOKEN --env Production --body "$TOKEN"

gh variable list --env Production
gh secret   list --env Production
gh api repos/OWNER/REPO/environments --jq '.environments[].name'
```

- Environment names are **case-sensitive** (`Production`, not `production`).
- `gh secret set -f` means `--env-file`; `gh api -f` means `--raw-field`. Easy
  to confuse.
- `gh secret set NAME` with no `--body` and no stdin opens an interactive
  prompt and **hangs** in scripts. Always pass a value or pipe stdin.
- **Variable values are readable**: `gh variable list --json name,value`
  returns plaintext. Anything credential-shaped belongs in a secret.
- An unset `vars.*` expands to an **empty string** in Actions — the deploy step
  then targets a stack named `""` and reports success having changed nothing.
  This is why `github_setup.sh --audit` exists.

## Inspecting packages

```bash
gh api '/orgs/ORG/packages?package_type=container' --jq '.[] | "\(.name) \(.visibility)"'
gh api /orgs/ORG/packages/container/NAME/versions --jq '.[].metadata.container.tags[]'
```

`package_type` for ghcr.io is **`container`**. `docker` refers to the legacy
`docker.pkg.github.com` registry and returns wrong/empty results.

Deleted versions can be restored within 30 days, and only if the namespace has
not been reused.

## Sources

- <https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry>
- `docker/{login,metadata,build-push}-action` `action.yml` on master
- <https://docs.docker.com/build/cache/backends/gha/>
- `gh` CLI help (2.96.0)
