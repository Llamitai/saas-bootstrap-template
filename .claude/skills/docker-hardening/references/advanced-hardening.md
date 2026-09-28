# Advanced hardening — supply chain, runtime profiles, host, monitoring

This file covers the deeper layers of the audit beyond CIS Level-1 and the compose runtime block. Each section is self-contained; jump to the layer the user asked about.

Contents:

- [§A — Supply chain](#a--supply-chain): [A.1 frontend](#a1-pin-the-buildkit-frontend) ·
  [A.2 SBOM](#a2-sbom-generation) · [A.3 signing](#a3-image-signing-with-cosign) ·
  [A.4 provenance](#a4-provenance-slsa) · [A.5 .dockerignore](#a5-dockerignore-essentials) ·
  [A.6 scanning](#a6-image-scanning-matrix) · [A.7 Dependabot/Renovate](#a7-renovate--dependabot-for-digests)
- [§B — Runtime profiles (caps, seccomp, AppArmor, SELinux)](#b--runtime-profiles)
- [§C — User namespaces & rootless Docker](#c--user-namespaces--rootless-docker)
- [§D — Host & daemon configuration](#d--host--daemon-configuration)
- [§E — Network hardening](#e--network-hardening)
- [§F — Monitoring & runtime detection](#f--monitoring--runtime-detection)
- [§G — Image strategy (distroless, Docker Hardened Images, Wolfi, Chainguard)](#g--image-strategy)

---

## A — Supply chain

### A.1 Pin the BuildKit frontend

The `# syntax=` directive specifies the Dockerfile frontend, which is executable code BuildKit pulls and runs.

```dockerfile
# 🔴 DANGER — untrusted / unpinned frontend
# syntax=registry.example.com/custom-frontend:latest

# ✅ Safe — official Docker frontend, version tag
# syntax=docker/dockerfile:1
# syntax=docker/dockerfile:1.7

# ✅ Safest — pinned by digest (verify from docker.com release notes)
# syntax=docker/dockerfile:1@sha256:<digest>
```

Audit:
```bash
grep -rn "^# syntax=" .
```
Flag any frontend that is not `docker/dockerfile:*`.

Optionally restrict at the BuildKit level (`/etc/buildkit/buildkitd.toml`).
The documented frontend keys are `dockerfile.v0` (built-in Dockerfile
frontend) and `gateway.v0` (images loaded via `# syntax=`); there is no
wildcard key. An empty `allowedRepositories` allows every gateway source;
only repository names (no tag) are compared
([buildkitd.toml reference](https://docs.docker.com/build/buildkit/toml-configuration/)):
```toml
[frontend."dockerfile.v0"]
  enabled = true

[frontend."gateway.v0"]
  enabled = true
  allowedRepositories = ["docker.io/docker/dockerfile"]
```
Allowlisting only the official frontend blocks untrusted `# syntax=` images;
setting `gateway.v0` `enabled = false` blocks all `# syntax=` frontends.

### A.2 SBOM generation

#### Using BuildKit attestations
```bash
docker buildx build \
  --sbom=true \
  --provenance=mode=max \
  --output type=image,name=ghcr.io/org/repo:tag,push=true .
```

View attestations:
```bash
docker buildx imagetools inspect ghcr.io/org/repo:tag --format '{{json .SBOM}}'
docker buildx imagetools inspect ghcr.io/org/repo:tag --format '{{json .Provenance}}'
```

> ⚠️ BuildKit attestations are stored as OCI artifacts but are **not cryptographically signed by default** — pair with `cosign attest` for integrity.

#### Using Syft (independent)
```bash
syft <image>                       # text summary
syft <image> -o spdx-json > sbom.json
syft <image> -o cyclonedx-json > sbom.cdx.json
```

#### In CI (GitHub Actions)
Third-party actions are pinned by full commit SHA (tags are mutable); the
comment records the release tag the SHA was resolved from.
```yaml
- uses: anchore/sbom-action@3ad7283483fc7af8ff2b4ea19663c2d5ca935e26 # v0.24.2
  with:
    image: ghcr.io/${{ github.repository }}:${{ github.sha }}
    format: spdx-json
    output-file: sbom.spdx.json
- uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
  with: { name: sbom, path: sbom.spdx.json }
```

#### Scan an SBOM (faster than image scan)
```bash
grype sbom:./sbom.spdx.json
trivy sbom ./sbom.spdx.json
```

### A.3 Image signing with cosign

Generate keys (one-time):
```bash
cosign generate-key-pair                    # cosign.key (keep secret) + cosign.pub
# or use OIDC / KMS:
cosign generate-key-pair --kms gcpkms://projects/p/locations/l/keyRings/r/cryptoKeys/k
```

Sign on push:
```bash
docker push ghcr.io/org/repo:tag
cosign sign --key cosign.key ghcr.io/org/repo:tag
```

Verify on deploy:
```bash
cosign verify --key cosign.pub ghcr.io/org/repo:tag
```

#### Keyless (Sigstore / OIDC, recommended)
Sign the digest, not a mutable tag. In GitHub Actions the job needs an OIDC
token and registry write access:
```yaml
permissions:
  contents: read
  id-token: write   # OIDC token for Sigstore keyless signing
  packages: write   # push the signature to GHCR
steps:
  - uses: sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6 # v4.1.2
  # ... build and push with docker/build-push-action (id: build) ...
  - run: cosign sign --yes ghcr.io/org/repo@${{ steps.build.outputs.digest }}
```
```bash
cosign verify \
  --certificate-identity=https://github.com/org/repo/.github/workflows/release.yml@refs/heads/main \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  ghcr.io/org/repo@sha256:<digest>
```

#### GitHub artifact attestations (GHCR alternative)
GitHub-signed build provenance (Sigstore-backed) without managing cosign
([docs](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)):
```yaml
permissions:
  contents: read
  id-token: write
  attestations: write
  packages: write
steps:
  - uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2
    with:
      subject-name: ghcr.io/${{ github.repository }}   # no tag
      subject-digest: ${{ steps.build.outputs.digest }}
      push-to-registry: true
```
```bash
gh attestation verify oci://ghcr.io/org/repo:tag -R org/repo
```

#### Notation (CNCF Notary Project)
Notation signatures are the other OCI-native option when the registry or
platform standardizes on Notary Project/X.509 PKI.

> **Docker Content Trust (DCT / Notary v1) is retired.** The Notary v1 service
> at `notary.docker.io` shuts down on December 8, 2026; Docker points to
> Sigstore/Cosign and Notation instead
> ([retirement notice](https://docs.docker.com/retired/#docker-content-trust-dct)).
> Flag `DOCKER_CONTENT_TRUST=1`, `docker trust` or `notary` usage as a finding
> and migrate it; never recommend DCT.

#### Admission controller (Kubernetes)
Use **Sigstore Policy Controller** or **Kyverno** to enforce `cosign verify` before admitting any pod. Without enforcement, signing is documentation, not security.

### A.4 Provenance (SLSA)

```bash
docker buildx build --provenance=mode=max --sbom=true -t ghcr.io/org/repo:tag --push .
```
- `mode=min` (default with `--push`): base info only.
- `mode=max`: includes build args, env, source, dependencies.

BuildKit provenance alone is unsigned. SLSA Build L2 requires provenance that
the **hosted** build platform generates and signs, and consumers verify
([SLSA Build track](https://slsa.dev/spec/v1.2/build-track-basics)). Use
`mode=max` on a hosted CI runner plus a signed attestation (`cosign attest` or
GitHub artifact attestations, §A.3) and verify it at deploy; do not claim an
SLSA level from `--provenance=true` alone.

### A.5 `.dockerignore` essentials

Treat `.dockerignore` as part of the audit. Required entries:
```gitignore
# Secrets / creds
.env
.env.*
*.pem
*.key
*.crt
id_rsa
id_rsa.pub
.npmrc
.netrc
.aws/
.gcp/
secrets/

# VCS / IDE
.git
.gitignore
.vscode
.idea
*.swp
.DS_Store

# Build artifacts (varies per stack)
node_modules
dist
build
target
__pycache__
*.pyc
.pytest_cache
.venv
venv

# Local-only
docker-compose.override.yml
*.log
```

### A.6 Image scanning matrix

| Tool | Best for | Exit-1 flag |
|---|---|---|
| Docker Scout | Docker ecosystem, policy violations | `--exit-code` (boolean; exits 2 on findings) |
| Trivy | Wide ecosystem (OS pkgs, libs, IaC, secrets) | `--exit-code 1` |
| Grype | SBOM-first scanning, fast | `--fail-on high` |
| Snyk | Commercial, dev-focused remediation advice | `--severity-threshold=high` |

Pick one for CI gating; consider a second for periodic registry-wide scans.

### A.7 Renovate / Dependabot for digests

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: docker          # FROM lines in Dockerfiles
    directory: /
    schedule: { interval: weekly }
  - package-ecosystem: docker-compose  # image: lines in compose files
    directory: /
    schedule: { interval: weekly }
  - package-ecosystem: github-actions  # SHA-pinned actions in workflows
    directory: /
    schedule: { interval: weekly }
```
Adjust directories to where the Dockerfiles and compose files live. See
[supported ecosystems](https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories).

Renovate equivalent — set `"pinDigests": true` and `"docker"` enabled.

---

## B — Runtime profiles

### B.1 Capabilities

Default Docker drops most capabilities but keeps ~14. The hardening pattern:

```bash
docker run --cap-drop ALL --cap-add NET_BIND_SERVICE …
```

```yaml
# compose
services:
  api:
    cap_drop: [ALL]
    cap_add:
      - NET_BIND_SERVICE   # bind <1024 ports
      # - CHOWN            # if you must chown at runtime
      # - SETGID
      # - SETUID
```

Common reasons to add a capability back:

| Capability | Why you might need it |
|---|---|
| `NET_BIND_SERVICE` | bind to ports <1024 without root |
| `CHOWN`, `SETUID`, `SETGID` | `gosu` / `su-exec` patterns at startup |
| `DAC_OVERRIDE` | reading files regardless of perms (avoid if possible) |
| `KILL` | signaling other processes in the container |

Never add: `SYS_ADMIN`, `SYS_PTRACE`, `SYS_MODULE`, `NET_ADMIN` (unless explicitly required and documented).

### B.2 Seccomp

Default Docker seccomp profile blocks ~44 syscalls. Use it (don't disable!):
```bash
docker run --security-opt seccomp=default …
# never:
# docker run --security-opt seccomp=unconfined …
```

Tighter custom profile (start from Docker's `default.json`, remove syscalls your app proves it doesn't need):
```bash
docker run --security-opt seccomp=/etc/docker/seccomp/strict.json …
```

In compose:
```yaml
services:
  api:
    security_opt:
      - "seccomp:/etc/docker/seccomp/strict.json"
      - "no-new-privileges:true"
```

Generate a minimal profile from a runtime trace with `oci-seccomp-bpf-hook` or `falco`'s syscall analyzer.

### B.3 AppArmor (Debian / Ubuntu)

Default Docker profile (`docker-default`) is auto-applied on AppArmor-enabled hosts.

Custom profile:
```bash
# Load profile (host-side)
sudo apparmor_parser -r -W /etc/apparmor.d/docker-myapp

# Apply
docker run --security-opt apparmor=docker-myapp …
```

```yaml
services:
  api:
    security_opt: ["apparmor=docker-myapp"]
```

Verify on host: `aa-status | grep docker`.

### B.4 SELinux (RHEL / CentOS / Fedora)

Enable SELinux for Docker (host):
```json
# /etc/docker/daemon.json
{ "selinux-enabled": true }
```

Volume labels:
```bash
docker run -v /host/path:/container/path:Z …   # private label
docker run -v /host/path:/container/path:z …   # shared label
```

```yaml
services:
  api:
    security_opt:
      - "label=type:my_container_t"
    volumes:
      - ./config:/app/config:ro,Z
```

### B.5 Read-only root filesystem

```bash
docker run --read-only --tmpfs /tmp --tmpfs /run …
```
```yaml
services:
  api:
    read_only: true
    tmpfs:
      - /tmp:size=64m,mode=1777
      - /run:size=16m,mode=0755
```

Watch for: app writing logs/cache/sessions to non-tmpfs paths — either redirect to `/tmp`, mount a named volume, or relocate the app's writable dir.

### B.6 No-new-privileges + comprehensive secure run

```bash
docker run \
  --user 1001:1001 \
  --read-only \
  --tmpfs /tmp \
  --tmpfs /run \
  --cap-drop ALL \
  --cap-add NET_BIND_SERVICE \
  --security-opt no-new-privileges \
  --security-opt seccomp=default \
  --security-opt apparmor=docker-default \
  --pids-limit 200 \
  --memory 512m \
  --cpus 1.0 \
  --network app_internal \
  --restart unless-stopped \
  --init \
  --health-cmd "curl -fs http://127.0.0.1:8080/health || exit 1" \
  --health-interval 30s --health-timeout 5s --health-retries 3 \
  ghcr.io/org/repo@sha256:<digest>
```

---

## C — User namespaces & rootless Docker

### C.1 User namespace remapping (rooted daemon, mapped uid)

Daemon side:
```json
// /etc/docker/daemon.json
{
  "userns-remap": "default"
}
```
Then `systemctl restart docker`. Container root (uid 0) becomes a non-root uid (e.g. 100000) on the host. Many escape paths (mount, kill, chown of host files) stop working.

Trade-offs:
- Some volume mounts need ownership adjustment on host (`chown -R 100000:100000 …`).
- Privileged containers, `--pid=host`, `--network=host`, `--userns=host` bypass it.

### C.2 Rootless Docker

The whole `dockerd` runs as a non-root user. Best fit for multi-tenant / shared / untrusted workloads.

Install (per-user):
```bash
curl -fsSL https://get.docker.com/rootless | sh
systemctl --user enable --now docker
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock
```

Limitations:
- No host networking for the container (use slirp4netns / RootlessKit).
- Ports <1024 need `setcap`.
- Cgroup v2 required for resource limits.
- AppArmor / SELinux profiles for `dockerd` itself differ.

### C.3 Podman (rootless-native alternative)

Podman is API-compatible with Docker, rootless by default, daemonless. Often a better default for multi-tenant workloads. Same `Dockerfile` and most compose features work.

---

## D — Host & daemon configuration

### D.1 `/etc/docker/daemon.json` hardened

```json
{
  "icc": false,
  "userns-remap": "default",
  "no-new-privileges": true,
  "live-restore": true,
  "userland-proxy": false,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "5"
  },
  "default-ulimits": {
    "nofile": { "Name": "nofile", "Hard": 64000, "Soft": 64000 }
  },
  "seccomp-profile": "/etc/docker/seccomp/default.json"
}
```

Restart: `systemctl restart docker`.

Note: `"icc": false` disables container-to-container traffic on the default bridge — services must use **user-defined networks**.

### D.2 Audit rules (auditd)

```bash
sudo tee /etc/audit/rules.d/docker.rules <<'EOF'
-w /usr/bin/dockerd -k docker
-w /var/lib/docker -k docker
-w /etc/docker -k docker
-w /etc/docker/daemon.json -k docker
-w /etc/default/docker -k docker
-w /etc/sysconfig/docker -k docker
-w /usr/lib/systemd/system/docker.service -k docker
-w /usr/lib/systemd/system/docker.socket -k docker
EOF
sudo augenrules --load
```

### D.3 `docker-bench-security`

```bash
# As container (read-only)
docker run --rm --net host --pid host --userns host --cap-add audit_control \
  -v /etc:/etc:ro -v /var/lib:/var/lib:ro \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  --label docker_bench_security \
  docker/docker-bench-security
```

Treat WARN/FAIL items as TODOs. Don't expect 100% — document exemptions per workload.
docker-bench-security implements CIS Docker Benchmark v1.6.0 numbering; CIS
has since published newer revisions (v1.8.0), so check section numbers against
the benchmark version the organization adopts. Its content-trust check (4.5)
relies on the retired DCT/Notary v1 — record it as an exception covered by
cosign/Notation/attestation verification instead of enabling DCT.

### D.4 Keep the daemon updated

- Subscribe to the Docker security advisory list.
- Pin a minor version in the host repo and bump with the same cadence as kernel updates.
- `docker version` must match what the scanner expects (some scanners flag pre-Moby `docker` builds).

---

## E — Network hardening

### E.1 User-defined networks

```yaml
networks:
  edge: {}                          # only nginx/traefik sits here
  app: { internal: true }           # API services
  data: { internal: true }          # DB / cache, only reachable from app

services:
  nginx:
    networks: [edge, app]
    ports: ["443:443"]
  api:
    networks: [app, data]
  db:
    networks: [data]
```

### E.2 Disable inter-container communication on default bridge

```json
// /etc/docker/daemon.json
{ "icc": false }
```
Effect: containers on the default `bridge` network cannot talk to each other. Forces explicit user-defined networks (good).

### E.3 Bind published ports to loopback

```bash
docker run -p 127.0.0.1:8080:8080 …
```
```yaml
ports:
  - "127.0.0.1:8080:8080"
```
Pair with a reverse proxy (nginx, traefik, caddy) on the public interface.

### E.4 Never use host namespaces

- `--network=host` — bypasses Docker network isolation.
- `--pid=host` — sees / signals all host processes.
- `--ipc=host` — shared SysV IPC with the host.
- `--uts=host` — shared hostname namespace.

Audit:
```bash
docker inspect --format='{{.HostConfig.NetworkMode}} {{.HostConfig.PidMode}} {{.HostConfig.IpcMode}}' $(docker ps -q)
```

### E.5 Egress control

Most threat models care about exfiltration. Options:
- Per-network egress filter via an `iptables` chain on `DOCKER-USER`.
- Sidecar proxy (envoy, squid) on the only egress network.
- Service mesh with strict egress policy.

---

## F — Monitoring & runtime detection

### F.1 Centralized logging

```yaml
services:
  api:
    logging:
      driver: fluentd                  # or syslog, journald, awslogs, gelf, splunk
      options:
        fluentd-address: fluent.internal:24224
        tag: docker.{{.Name}}
        fluentd-async-connect: "true"
```

Never rely solely on `json-file` for production — disk fills, no aggregation, no retention policy.

### F.2 Ship container lifecycle events

```bash
docker events --format '{{json .}}' | jq -c 'select(.Type=="container")' \
  | log-shipper --topic docker.events
```

### F.3 Falco (runtime detection)

```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco \
  --namespace falco --create-namespace \
  --set tty=true \
  --set falcosidekick.enabled=true
```

Default rules cover container escapes, unexpected `exec` into running container, write to `/etc`, sensitive mounts, crypto-mining patterns. Tune via `custom-rules.yaml`.

### F.4 CVE-watch on deployed images

- Trivy DB updates daily — schedule a nightly scan of all images in the production registry.
- Docker Scout policies can fire alerts on newly-discovered CVEs in already-pushed images.
- Pair with `cosign attest` so the latest scan result lives next to the image as an attestation.

---

## G — Image strategy

Pick the smallest image that runs the app. In order of preference:

1. **`scratch`** — single static binary (Go, Rust, .NET AOT). No shell, no package manager. Smallest attack surface.
2. **Distroless** (`gcr.io/distroless/<lang>-debian12:nonroot`) — language runtime only, no shell, no apt. Comes with a non-root user.
3. **Docker Hardened Images / Chainguard Images / Wolfi** — distroless-style, low-CVE goal, SBOM + signature included. DHI Community images are free under Apache 2.0 from `dhi.io` (sign in with a Docker account: `docker login dhi.io`) and ship signed SBOMs, VEX and SLSA Build L3 provenance; Select/Enterprise tiers add SLA-backed updates and compliance variants ([docs](https://docs.docker.com/dhi/)).
4. **`*-alpine`** — small (~5 MB), `apk` package manager, may have musl-libc edge cases.
5. **`*-slim`** — Debian slim, apt-get available, ~70 MB.
6. **Full `*`** — Debian/Ubuntu standard, ~200 MB. Avoid for production.

### Wolfi / Chainguard example

Pin the digest resolved from the tag you choose
(`docker buildx imagetools inspect cgr.dev/chainguard/python:<tag>`) so the
audit's `:latest` rule is satisfied and Dependabot/Renovate bump it.

```dockerfile
# Build with full toolchain
FROM cgr.dev/chainguard/python@sha256:<dev-digest> AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt
COPY . .

# Run in zero-CVE final image
FROM cgr.dev/chainguard/python@sha256:<runtime-digest>
WORKDIR /app
COPY --from=builder /root/.local /home/nonroot/.local
COPY --from=builder /app /app
USER nonroot
ENV PATH=/home/nonroot/.local/bin:$PATH
ENTRYPOINT ["python", "-m", "app"]
```

Chainguard images ship with SBOM attestations and cosign signatures — verify them in CI:
```bash
cosign verify --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  --certificate-identity=https://github.com/chainguard-images/images/.github/workflows/release.yaml@refs/heads/main \
  cgr.dev/chainguard/python@sha256:<runtime-digest>
```

### Distroless example

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .

FROM gcr.io/distroless/nodejs20-debian12:nonroot
WORKDIR /app
COPY --from=builder --chown=nonroot:nonroot /app /app
USER nonroot
EXPOSE 8080
CMD ["server.js"]
```

Distroless has no shell, so HEALTHCHECK must use a bundled binary or the runtime itself:
```dockerfile
HEALTHCHECK CMD ["node", "healthcheck.js"]
```
