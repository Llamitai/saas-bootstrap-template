# GitHub Container Registry and Actions reference

Contents: [Action versions](#action-versions) · [Build and push](#build-and-push) ·
[Provenance and SBOM](#provenance-and-sbom) ·
[Manual first push](#manual-first-push) ·
[Package visibility](#package-visibility--the-most-common-first-deploy-failure) ·
[Private pulls](#pulling-a-private-image-on-the-docker-host) ·
[Cloudflare Access](#cloudflare-access) ·
[Repository CLI](#configuring-the-repository-from-the-cli) ·
[Inspecting packages](#inspecting-packages)

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

**Pin third-party actions by full commit SHA** (40 hex characters) with the
version as a trailing comment; a tag such as `@v2` can be moved to different
code. Resolve a SHA read-only instead of copying one from memory:

```bash
gh api repos/<owner>/<action>/git/ref/tags/<tag> --jq '.object.type + " " + .object.sha'
# if the type is "tag" (annotated), dereference it to the commit:
gh api repos/<owner>/<action>/git/tags/<sha> --jq .object.sha
```

The workflows in this repo pin every action by SHA, and the `Workflow lint` job
(actionlint + zizmor) rejects unpinned additions.

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

## Provenance and SBOM

The repo's build workflows already set `provenance: mode=max` and `sbom: true`;
the Sigstore attestation below is optional further hardening. BuildKit attaches an SLSA provenance and SBOM attestation to the pushed
image, and `actions/attest-build-provenance` adds a Sigstore-signed GitHub
attestation that `gh attestation verify` can check on the pull side. SHAs
below were resolved with the commands above on 2026-09-26 (`v7.4.0`,
`v4.2.2`); re-resolve before adopting them.

```yaml
permissions:
  contents: read
  packages: write           # push image + attestation to GHCR
  id-token: write           # OIDC token for the Sigstore signing certificate
  attestations: write       # persist the attestation
  artifact-metadata: write  # storage record (created when push-to-registry is true)

steps:
  # … checkout, setup-buildx, login, metadata as above
  - id: push
    uses: docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0
    with:
      context: backend
      file: backend/Dockerfile
      target: production
      push: true
      tags: ${{ steps.meta.outputs.tags }}
      labels: ${{ steps.meta.outputs.labels }}
      provenance: mode=max    # full SLSA provenance, including build args
      sbom: true

  - uses: actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8 # v4.2.2
    with:
      subject-name: ${{ vars.BACKEND_REPOSITORY_URI }}   # fully qualified, no tag
      subject-digest: ${{ steps.push.outputs.digest }}
      push-to-registry: true
```

- Grant these permissions on the build job only, never workflow-wide; the
  rollback jobs need just `contents: read` and `packages: read`.
- `mode=max` records build arguments in the provenance: never pass secrets as
  `build-args` (use BuildKit secrets).
- Verify: `gh attestation verify oci://<image>:<tag> --owner <owner>`.
- Artifact attestations on **private** repositories depend on the GitHub plan;
  confirm availability before relying on them.

## Manual first push

Only when the first image must exist before CI runs (SKILL.md Phase 4 Path B).
Needs a classic PAT with `write:packages` (see § Pulling a private image on the Docker host for why
fine-grained tokens fail) and `docker` with Buildx:

```bash
echo "$CR_PAT" | docker login ghcr.io -u USERNAME --password-stdin
TAG="sha-$(git rev-parse --short HEAD)"
docker buildx build backend \
  --file backend/Dockerfile --target production \
  --platform linux/amd64 \
  --label "org.opencontainers.image.source=https://github.com/OWNER/REPO" \
  --tag "ghcr.io/OWNER/PROJECT-api-prod:$TAG" \
  --tag "ghcr.io/OWNER/PROJECT-api-prod:latest" \
  --push
```

Match `--platform` to the Docker host, use the exact lowercase image name from
`backend/docker-compose.prod.yml`, and keep the `source` label so the package
links to the repository on its first push (below). Repeat for the frontend
with `frontend/Dockerfile` and the `-web-prod` image.

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
> `bash <skill-dir>/scripts/github_setup.sh --env-file .env.deploy.ci --environment Production --audit` reports configured-but-unreferenced
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
