# Rollback

The repo ships `.github/workflows/rollback.yml`. Prefer it over manual
intervention — it verifies the image exists before redeploying:

```bash
gh workflow run Rollback \
  -f service=backend -f target_environment=Production -f version=sha-abc1234
```

To find a known-good tag (organization-owned packages):

```bash
gh api "/orgs/<org>/packages/container/<project>-api-prod/versions" \
  --jq '.[].metadata.container.tags[]' | head -20
```

For a package owned by a **personal account**, the `/orgs/...` path 404s; use
`/users/<user>/packages/container/<project>-api-prod/versions` (or
`/user/packages/...` for the authenticated user).

Rolling back the **image** does not roll back **secrets** or **migrations**.
If the bad deploy changed either, say so explicitly rather than implying the
rollback restored the previous state.

## Gotchas

- **The compose file comes from `github.ref`, not from the image's commit.**
  The deploy step passes `ref: ${{ github.ref }}`, i.e. the branch the
  workflow was dispatched on (the default branch unless you pass `--ref`).
  Portainer redeploys that branch's current `docker-compose.prod.yml` with the
  old image tag. If the compose file changed since the known-good image
  (services, env names, networks), compare them first
  (`git diff <image-commit> origin/main -- backend/docker-compose.prod.yml`)
  and, when they are incompatible, dispatch with `--ref` set to a branch or
  tag at the image's commit. That ref must itself contain `rollback.yml`.
- **The stack env is replaced by today's values.** `env_data` is rebuilt from
  the current GitHub environment, so bootstrap values and the Directus block
  are the current ones, not those of the old deploy.
- **Tags are mutable; verify the digest.** The workflow deploys by tag, and a
  `sha-*` tag can be re-pushed. Record the digest of the known-good image and
  confirm the tag still resolves to it before dispatching:

  ```bash
  docker buildx imagetools inspect ghcr.io/<owner>/<project>-api-prod:sha-abc1234 \
    --format '{{json .Manifest.Digest}}'
  ```

  In the versions listing above, each version's `.name` is its digest. Never
  roll back to `latest`: it moves on every build.
