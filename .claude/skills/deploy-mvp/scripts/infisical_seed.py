#!/usr/bin/env python3
"""Seed an Infisical project with the application secrets an app actually reads.

Standard library only (urllib). Uses the CURRENT v4 secrets API; the
`/api/v3/secrets/raw` family still responds but is documented as deprecated.

The key set comes from the repo's own `.env.example`, so a setting the app
gained cannot be silently forgotten. Every value is resolved through an
explicit precedence chain and anything still unresolved is reported as MISSING
rather than guessed.

Commands:
    projects        list projects the machine identity can see
    create-project  create a project (and report its id)
    plan            show key / source / status without writing anything
    apply           upsert the planned secrets (idempotent)
    check           verify cross-service invariants after seeding

Example:
    infisical_seed.py plan --env-file .env.deploy \\
        --template backend/.env.example --overrides .env.deploy.generated \\
        --project-id "$BACKEND_PROJECT_ID" --environment prod
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import secrets as pysecrets
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SECRETISH = re.compile(r"(PASSWORD|SECRET|TOKEN|KEY|CREDENTIAL|DSN)", re.IGNORECASE)
NOT_SECRET = {"JWT_ALGORITHM", "SENTRY_SEND_DEFAULT_PII", "AWS_S3_PUBLIC_URL"}

# Keys the skill may generate rather than ask a human for, with how.
#   hex32     -> openssl rand -hex 32   equivalent
#   b64url32  -> openssl rand -base64 32, made URL-safe
GENERATABLE = {
    "JWT_SECRET_KEY": "hex32",
    "SECRET_KEY": "b64url32",
    "ADMIN_API_KEY": "hex32",
    "BACKEND_API_KEY": "hex32",
    "DIRECTUS_SECRET": "b64url32",
    "DIRECTUS_ADMIN_PASSWORD": "b64url32",
    "ADMIN_SECRET": "b64url32",
    "ADMIN_PASSWORD": "b64url32",
}

# STRICT ALLOWLIST. `.env.example` describes LOCAL DEVELOPMENT — it points at
# the bundled Mailpit, MinIO and localhost. Inheriting those defaults into
# production is silent breakage of exactly the kind this skill exists to
# prevent (mail vanishing into a container that isn't there, uploads written to
# a dev bucket). So a template value is reused ONLY when it is a protocol
# constant that does not vary by environment. Everything else must come from
# an override, be derived, be generated, or be reported as MISSING.
SAFE_TEMPLATE_DEFAULTS = {
    "JWT_ALGORITHM",
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "JWT_REFRESH_TOKEN_EXPIRE_MINUTES",
    "POSTGRES_PORT",
    "REDIS_PORT",
    "REDIS_DB",
    "GOOGLE_CERTS_URL",
    "SENTRY_TRACES_SAMPLE_RATE",
    "SENTRY_PROFILES_SAMPLE_RATE",
    "SENTRY_SEND_DEFAULT_PII",
}

# Keys that may legitimately be blank in production. They are reported as
# warnings and skipped rather than blocking the apply.
#   AWS_S3_ENDPOINT_URL empty  -> real AWS S3 rather than a MinIO-compatible host
#   REDIS_USER/PASSWORD empty  -> Redis reachable only on the private network
#   SENTRY_DSN empty           -> error reporting off
OPTIONAL_EMPTY = {
    "AWS_S3_ENDPOINT_URL",
    "AWS_CLOUDFRONT_DOMAIN",
    "AWS_S3_PUBLIC_URL",
    "REDIS_USER",
    "REDIS_PASSWORD",
    "SENTRY_DSN",
    "ADMIN_LOGO_URL",
    "ADMIN_LOGIN_LOGO_URL",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
}

# Template values that are obviously placeholders, never real configuration.
PLACEHOLDER = re.compile(
    r"(your-|-here$|changeme|placeholder|example\.com|localhost|127\.0\.0\.1"
    r"|mailpit|minio|-dev$|dev-)",
    re.IGNORECASE,
)

# Keys whose production value is derived from operator input, not the template.
DERIVED = {
    "STAGE": lambda e: e.get("INFISICAL_SECRET_ENV", "prod"),
    "ENVIRONMENT": lambda e: "production",
    "NODE_ENV": lambda e: "production",
    "SENTRY_ENVIRONMENT": lambda e: "production",
    "FRONTEND_HOST": lambda e: e.get("PUBLIC_APP_URL", ""),
    "CORS_ORIGINS": lambda e: e.get("PUBLIC_APP_URL", ""),
    "NEXT_PUBLIC_APP_URL": lambda e: e.get("PUBLIC_APP_URL", ""),
    "NEXT_PUBLIC_BACKEND_API_HOST": lambda e: e.get("PUBLIC_API_URL", ""),
    "ADMIN_PUBLIC_URL": lambda e: e.get("ADMIN_PUBLIC_URL", ""),
    "GOOGLE_REDIRECT_URI": lambda e: (
        e.get("PUBLIC_APP_URL", "").rstrip("/") + "/api/auth/google/callback"
        if e.get("PUBLIC_APP_URL")
        else ""
    ),
}


class InfisicalError(RuntimeError):
    pass


# ── dotenv ───────────────────────────────────────────────────────────


def load_env_file(path: Path, *, required: bool = True) -> dict[str, str]:
    if not path.is_file():
        if required:
            raise InfisicalError(f"file not found: {path}")
        return {}
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        # Strip trailing inline comments, but only when clearly separated, so
        # a value legitimately containing '#' survives.
        value = re.sub(r"\s+#.*$", "", value.strip())
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def merge_into(path: Path, values: dict[str, str]) -> None:
    """Persist generated values so a later run reuses them instead of rotating."""
    existing = load_env_file(path, required=False)
    existing.update(values)
    lines = ["# Generated by deploy-mvp. Do not commit."]
    lines += [f"{k}={v}" for k, v in sorted(existing.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def mask(key: str, value: str) -> str:
    if key not in NOT_SECRET and SECRETISH.search(key) and value:
        return f"<set:{len(value)}>"
    return value


def generate(kind: str) -> str:
    if kind == "hex32":
        return pysecrets.token_hex(32)
    raw = base64.b64encode(pysecrets.token_bytes(32)).decode()
    return raw.replace("+", "-").replace("/", "_").rstrip("=")


# ── client ───────────────────────────────────────────────────────────


class Infisical:
    def __init__(self, base_url: str, *, insecure: bool = False) -> None:
        if not base_url:
            raise InfisicalError(
                "no Infisical URL. Set INFISICAL_DOMAIN (preferred) or the "
                "legacy INFISICAL_API_URL in your env file."
            )
        # Every documented example passes the bare origin; /api is part of the
        # request path, so strip it if the operator pasted it in.
        self.base = base_url.rstrip("/")
        if self.base.endswith("/api"):
            self.base = self.base[: -len("/api")]
        self.token: str | None = None
        self.ctx: ssl.SSLContext | None = None
        if insecure:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def request(self, method: str, path: str, *, params=None, body=None, auth=True):
        url = f"{self.base}/api{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if auth:
            if not self.token:
                raise InfisicalError("not logged in")
            req.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=60) as resp:
                payload = resp.read()
                return json.loads(payload) if payload.strip() else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:600]
            raise InfisicalError(
                f"{method} /api{path} -> HTTP {exc.code} {exc.reason}\n{detail}"
            ) from None
        except urllib.error.URLError as exc:
            raise InfisicalError(f"cannot reach {self.base}: {exc.reason}") from None

    def login(self, client_id: str, client_secret: str) -> None:
        if not client_id or not client_secret:
            raise InfisicalError(
                "INFISICAL_MACHINE_CLIENT_ID / INFISICAL_MACHINE_CLIENT_SECRET are required"
            )
        result = self.request(
            "POST",
            "/v1/auth/universal-auth/login",
            body={"clientId": client_id, "clientSecret": client_secret},
            auth=False,
        )
        self.token = result["accessToken"]

    def projects(self) -> list[dict]:
        result = self.request("GET", "/v1/projects", params={"type": "secret-manager"})
        if isinstance(result, dict):
            return result.get("projects") or result.get("workspaces") or []
        return result or []

    def create_project(self, name: str, slug: str | None) -> dict:
        body: dict = {"projectName": name, "type": "secret-manager"}
        if slug:
            # The API enforces a 5-character minimum on an explicit slug.
            if len(slug) < 5:
                raise InfisicalError(f"slug {slug!r} is shorter than the 5-char minimum")
            body["slug"] = slug
        return (self.request("POST", "/v1/projects", body=body) or {}).get("project", {})

    def list_secrets(self, project_id: str, environment: str, path: str = "/") -> dict[str, str]:
        result = self.request(
            "GET",
            "/v4/secrets",
            params={
                "projectId": project_id,
                "environment": environment,
                "secretPath": path,
                "viewSecretValue": "true",
                # Compare what is literally stored, not the resolved form of
                # any ${SECRET_REF} indirection.
                "expandSecretReferences": "false",
                "recursive": "false",
            },
        ) or {}
        out: dict[str, str] = {}
        for item in result.get("secrets", []):
            key = item.get("secretKey") or item.get("key")
            if key:
                out[key] = item.get("secretValue", item.get("value", ""))
        return out

    def upsert(self, project_id: str, environment: str, values: dict[str, str], path: str = "/"):
        """Batch upsert. `mode: upsert` is the only idempotent seeding primitive.

        The single-secret PATCH has no upsert flag and 404s on a missing key,
        and the batch default mode is failOnNotFound.
        """
        return self.request(
            "PATCH",
            "/v4/secrets/batch",
            body={
                "projectId": project_id,
                "environment": environment,
                "secretPath": path,
                "mode": "upsert",
                "secrets": [
                    {"secretKey": k, "secretValue": v} for k, v in sorted(values.items())
                ],
            },
        )


# ── planning ─────────────────────────────────────────────────────────


def template_keys(path: Path) -> dict[str, str]:
    """Read KEY=default pairs from a .env.example, preserving order."""
    if not path.is_file():
        raise InfisicalError(f"template not found: {path}")
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
        if match:
            value = re.sub(r"\s+#.*$", "", match.group(2).strip())
            out[match.group(1)] = value
    return out


def build_plan(
    template: dict[str, str],
    operator: dict[str, str],
    overrides: dict[str, str],
    remote: dict[str, str],
    *,
    generate_missing: bool,
) -> tuple[dict[str, tuple[str, str, str]], dict[str, str]]:
    """Resolve every template key to (value, source, status).

    Precedence: overrides > operator env > derived > safe template default >
    generated > MISSING.
    """
    plan: dict[str, tuple[str, str, str]] = {}
    newly_generated: dict[str, str] = {}

    for key, default in template.items():
        if key in overrides and overrides[key]:
            value, source = overrides[key], "override"
        elif key in operator and operator[key]:
            value, source = operator[key], "operator"
        elif key in DERIVED and DERIVED[key](operator):
            value, source = DERIVED[key](operator), "derived"
        elif key in SAFE_TEMPLATE_DEFAULTS and default and not PLACEHOLDER.search(default):
            value, source = default, "template"
        elif key in GENERATABLE and generate_missing:
            value = generate(GENERATABLE[key])
            source = "generated"
            newly_generated[key] = value
        elif key in OPTIONAL_EMPTY:
            plan[key] = ("", "optional", "empty")
            continue
        else:
            plan[key] = ("", "MISSING", "blocked")
            continue

        if key not in remote:
            status = "create"
        elif remote[key] != value:
            status = "update"
        else:
            status = "same"
        plan[key] = (value, source, status)

    return plan, newly_generated


def print_plan(plan: dict[str, tuple[str, str, str]], remote: dict[str, str]) -> int:
    width = max((len(k) for k in plan), default=10)
    print(f"{'KEY':<{width}}  {'SOURCE':<10} {'STATUS':<8} VALUE")
    print("-" * (width + 32))
    for key in sorted(plan):
        value, source, status = plan[key]
        shown = "-" if status == "blocked" else mask(key, value)
        print(f"{key:<{width}}  {source:<10} {status:<8} {shown}")

    missing = [k for k, (_, s, _) in plan.items() if s == "MISSING"]
    empty = [k for k, (_, _, st) in plan.items() if st == "empty"]
    counts = {
        s: sum(1 for _, (_, _, st) in plan.items() if st == s)
        for s in ("create", "update", "same", "blocked", "empty")
    }
    print(
        f"\n{counts['create']} to create, {counts['update']} to update, "
        f"{counts['same']} unchanged, {counts['empty']} skipped (optional), "
        f"{counts['blocked']} blocked."
    )

    if empty:
        print(f"\nWARNING — {len(empty)} optional value(s) left unset:")
        for key in empty:
            print(f"    {key}")
        print("The app will run, but the feature behind each is off. Confirm")
        print("with the user that this is intended before finishing the deploy.")

    extra = sorted(set(remote) - set(plan))
    if extra:
        print(f"\n{len(extra)} secret(s) exist in Infisical but not in the template:")
        for key in extra:
            print(f"    {key}")
        print("These are left untouched. Remove them by hand if they are stale.")

    if missing:
        print(f"\nBLOCKED — {len(missing)} value(s) only a human can supply:")
        for key in missing:
            print(f"    {key}")
        print("\nAdd them to your overrides file, then re-run. Do not apply a")
        print("plan with blocked keys: the app will boot with empty settings.")
        return 1
    return 0


# ── commands ─────────────────────────────────────────────────────────


def connect(args: argparse.Namespace, env: dict[str, str]) -> Infisical:
    base = env.get("INFISICAL_DOMAIN") or env.get("INFISICAL_API_URL", "")
    api = Infisical(base, insecure=args.insecure)
    api.login(
        env.get("INFISICAL_MACHINE_CLIENT_ID", ""),
        env.get("INFISICAL_MACHINE_CLIENT_SECRET", ""),
    )
    return api


def cmd_projects(args: argparse.Namespace, env: dict[str, str]) -> int:
    api = connect(args, env)
    projects = api.projects()
    if not projects:
        print("No projects visible to this machine identity.")
        print("Grant it project access, or create one with `create-project`.")
        return 1
    for p in projects:
        envs = ",".join(e.get("slug", "") for e in p.get("environments", []))
        print(f"{p.get('id')}  {p.get('name')}  [{p.get('slug')}]  envs: {envs or '-'}")
    return 0


def cmd_create_project(args: argparse.Namespace, env: dict[str, str]) -> int:
    api = connect(args, env)
    for p in api.projects():
        if p.get("name") == args.name:
            print(f"Project {args.name!r} already exists: id={p.get('id')}")
            return 0
    project = api.create_project(args.name, args.slug)
    print(f"Created project {project.get('name')!r} id={project.get('id')}")
    print("\nRecord this id as BACKEND_PROJECT_ID or FRONTEND_PROJECT_ID in .env.deploy.")
    print("Then grant the machine identity access to it before seeding.")
    return 0


def resolve_plan(args: argparse.Namespace, env: dict[str, str]):
    api = connect(args, env)
    project_id = args.project_id or env.get("BACKEND_PROJECT_ID", "")
    if not project_id:
        raise InfisicalError("no --project-id and no BACKEND_PROJECT_ID in the env file")
    environment = args.environment or env.get("INFISICAL_SECRET_ENV", "prod")

    template = template_keys(Path(args.template))
    overrides = load_env_file(Path(args.overrides), required=False) if args.overrides else {}
    remote = api.list_secrets(project_id, environment, args.path)

    plan, generated = build_plan(
        template, env, overrides, remote, generate_missing=not args.no_generate
    )
    return api, project_id, environment, plan, generated, remote


def cmd_plan(args: argparse.Namespace, env: dict[str, str]) -> int:
    _, project_id, environment, plan, generated, remote = resolve_plan(args, env)
    print(f"Project {project_id} / environment {environment} / path {args.path}\n")
    rc = print_plan(plan, remote)
    if generated:
        print(f"\n{len(generated)} value(s) would be generated on apply:")
        for key in sorted(generated):
            print(f"    {key}")
        print("They are written to the overrides file so re-running is stable.")
    return rc


def cmd_apply(args: argparse.Namespace, env: dict[str, str]) -> int:
    api, project_id, environment, plan, generated, remote = resolve_plan(args, env)
    rc = print_plan(plan, remote)
    if rc:
        print("\nRefusing to apply while values are blocked.")
        return rc

    writable = {k: v for k, (v, _, st) in plan.items() if st in ("create", "update")}
    if not writable:
        print("\nNothing to do — Infisical already matches the plan.")
        return 0

    if generated and args.overrides:
        # Persist before writing remotely so a failed apply does not lose the
        # generated values (and a retry does not rotate them).
        merge_into(Path(args.overrides), generated)
        print(f"\nPersisted {len(generated)} generated value(s) to {args.overrides}")

    api.upsert(project_id, environment, writable, args.path)
    print(f"\nUpserted {len(writable)} secret(s) into {project_id}/{environment}.")
    return 0


def cmd_check(args: argparse.Namespace, env: dict[str, str]) -> int:
    """Verify invariants that span the two projects."""
    api = connect(args, env)
    environment = args.environment or env.get("INFISICAL_SECRET_ENV", "prod")
    backend_id = env.get("BACKEND_PROJECT_ID", "")
    frontend_id = env.get("FRONTEND_PROJECT_ID", "")
    if not backend_id or not frontend_id:
        raise InfisicalError("check needs both BACKEND_PROJECT_ID and FRONTEND_PROJECT_ID")

    backend = api.list_secrets(backend_id, environment, args.path)
    frontend = api.list_secrets(frontend_id, environment, args.path)
    failures: list[str] = []

    def require(condition: bool, message: str) -> None:
        print(f"  [{'ok' if condition else 'FAIL'}] {message}")
        if not condition:
            failures.append(message)

    print("Cross-service invariants:")
    require(
        bool(backend.get("ADMIN_API_KEY"))
        and backend.get("ADMIN_API_KEY") == frontend.get("BACKEND_API_KEY"),
        "backend ADMIN_API_KEY == frontend BACKEND_API_KEY (else every BFF call 401s)",
    )
    jwt = backend.get("JWT_SECRET_KEY", "")
    require(len(jwt) >= 32, "backend JWT_SECRET_KEY is at least 32 characters")
    app_url = env.get("PUBLIC_APP_URL", "").rstrip("/")
    require(
        bool(app_url) and app_url in backend.get("CORS_ORIGINS", ""),
        f"backend CORS_ORIGINS contains {app_url or '<PUBLIC_APP_URL unset>'}",
    )
    require(
        backend.get("GOOGLE_REDIRECT_URI", "").startswith(app_url) if app_url else False,
        "backend GOOGLE_REDIRECT_URI is under the public app URL "
        "(must also be registered in Google Cloud)",
    )
    require(
        backend.get("ENVIRONMENT") == "production",
        "backend ENVIRONMENT == production",
    )
    for key in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        require(bool(backend.get(key)), f"backend {key} is set")

    print(f"\n{len(failures)} failing invariant(s)." if failures else "\nAll invariants hold.")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env.deploy")
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("projects", help="list visible projects")

    p_new = sub.add_parser("create-project", help="create a project")
    p_new.add_argument("--name", required=True)
    p_new.add_argument("--slug", default=None, help="optional, min 5 chars")

    seed_args = argparse.ArgumentParser(add_help=False)
    seed_args.add_argument("--template", required=True, help="path to a .env.example")
    seed_args.add_argument("--overrides", default=".env.deploy.generated")
    seed_args.add_argument("--project-id", default=None)
    seed_args.add_argument("--environment", default=None, help="default: INFISICAL_SECRET_ENV")
    seed_args.add_argument("--path", default="/", help="Infisical secret path")
    seed_args.add_argument(
        "--no-generate",
        action="store_true",
        help="never invent a value; report every unset secret as MISSING",
    )

    sub.add_parser("plan", parents=[seed_args], help="show what would change")
    sub.add_parser("apply", parents=[seed_args], help="upsert the planned secrets")

    p_check = sub.add_parser("check", help="verify cross-service invariants")
    p_check.add_argument("--environment", default=None)
    p_check.add_argument("--path", default="/")

    args = parser.parse_args()
    handlers = {
        "projects": cmd_projects,
        "create-project": cmd_create_project,
        "plan": cmd_plan,
        "apply": cmd_apply,
        "check": cmd_check,
    }
    try:
        env = load_env_file(Path(args.env_file))
        return handlers[args.command](args, env)
    except InfisicalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
