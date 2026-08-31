#!/usr/bin/env python3
"""Create, redeploy and inspect a Portainer standalone Compose stack backed by Git.

Standard library only (urllib). No curl, no requests, no portainer SDK.

Targets Portainer CE 2.19+ using the canonical route
`POST /api/stacks/create/standalone/repository`. The legacy
`POST /api/stacks?type=2&method=repository` form was REMOVED in Portainer 2.27
and is never emitted here.

Commands:
    endpoints   list environments so you can pick --endpoint-id
    create      create the stack, or redeploy it if the name already exists
    redeploy    redeploy an existing git stack (env-preserving by default)
    status      stack record + container states + running image tags
    logs        tail a container's logs through Portainer's Docker proxy

Example:
    portainer_stack.py endpoints --env-file .env.deploy
    portainer_stack.py create --env-file .env.deploy --endpoint-id 1 \\
        --name acme-backend-prod --repo https://github.com/acme/app \\
        --ref refs/heads/main --compose backend/docker-compose.prod.yml \\
        --stack-env .env.deploy.stack --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Anything whose name matches this is masked in dry-run output and error text.
SECRETISH = re.compile(
    r"(PASSWORD|SECRET|TOKEN|KEY|CLIENT_ID|DSN|CREDENTIAL)", re.IGNORECASE
)

# Names that trip the pattern above but carry no secret. Masking these makes a
# dry run harder to review without making it any safer — an operator needs to
# see that the environment slug really says `prod`.
NOT_SECRET = {
    "INFISICAL_SECRET_ENV",
    "SENTRY_SEND_DEFAULT_PII",
    "JWT_ALGORITHM",
    "AWS_S3_PUBLIC_URL",
}


class PortainerError(RuntimeError):
    pass


# ── dotenv ───────────────────────────────────────────────────────────


def load_env_file(path: Path, *, required: bool = True) -> dict[str, str]:
    if not path.is_file():
        if required:
            raise PortainerError(f"env file not found: {path}")
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
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def mask(key: str, value: str) -> str:
    if key not in NOT_SECRET and SECRETISH.search(key) and value:
        return f"<set:{len(value)} chars>"
    return value


# ── client ───────────────────────────────────────────────────────────


class Portainer:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        insecure: bool = False,
        cf_client_id: str = "",
        cf_client_secret: str = "",
    ) -> None:
        if not base_url:
            raise PortainerError("PORTAINER_URL is empty")
        if not token:
            raise PortainerError("PORTAINER_TOKEN is empty")
        # The API lives under /api; accept a URL with or without it.
        self.base = base_url.rstrip("/")
        if self.base.endswith("/api"):
            self.base = self.base[: -len("/api")]
        self.token = token
        # Cloudflare Access service-token headers. When Portainer sits behind
        # Cloudflare Access, every request without these is answered by the
        # Access login page — an HTML 302, not a Portainer error — so a missing
        # pair looks like "Portainer is broken" rather than "you are not
        # authenticated". Sent on every request when configured.
        self.cf_headers: dict[str, str] = {}
        if cf_client_id and cf_client_secret:
            self.cf_headers = {
                "CF-Access-Client-Id": cf_client_id,
                "CF-Access-Client-Secret": cf_client_secret,
            }
        self.ctx: ssl.SSLContext | None = None
        if insecure:
            # Opt-in only. The popular community action disables verification
            # unconditionally; this tool makes it a visible choice.
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict | None = None,
        raw: bool = False,
    ):
        url = f"{self.base}/api{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-API-Key", self.token)
        for header, value in self.cf_headers.items():
            req.add_header(header, value)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=60) as resp:
                payload = resp.read()
                if raw:
                    return payload
                # GET /api/stacks answers 204 with no body when there are none.
                if resp.status == 204 or not payload.strip():
                    return None
                try:
                    return json.loads(payload)
                except json.JSONDecodeError:
                    # Cloudflare Access serves its login page with HTTP 200, so
                    # a non-JSON body here means the request never reached
                    # Portainer at all.
                    if b"<html" in payload[:200].lower():
                        raise PortainerError(
                            f"{method} {path} returned HTML, not JSON. Portainer is "
                            "likely behind an access proxy. Set CF_ACCESS_CLIENT_ID "
                            "and CF_ACCESS_CLIENT_SECRET in your env file."
                        ) from None
                    raise
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:600]
            hint = ""
            if exc.code in (401, 403) and not self.cf_headers:
                hint = (
                    "\nhint: if Portainer is behind Cloudflare Access, set "
                    "CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET."
                )
            raise PortainerError(
                f"{method} {path} -> HTTP {exc.code} {exc.reason}\n{detail}{hint}"
            ) from None
        except urllib.error.URLError as exc:
            raise PortainerError(f"cannot reach {self.base}: {exc.reason}") from None

    # -- specific calls --

    def version(self) -> dict:
        return self.request("GET", "/system/version") or {}

    def endpoints(self) -> list[dict]:
        return self.request("GET", "/endpoints", params={"excludeSnapshots": "true"}) or []

    def stacks(self, endpoint_id: int | None = None) -> list[dict]:
        params = {}
        if endpoint_id is not None:
            params["filters"] = json.dumps({"EndpointID": endpoint_id})
        return self.request("GET", "/stacks", params=params) or []

    def find_stack(self, name: str, endpoint_id: int) -> dict | None:
        """Resolve a stack by name. The API has no name filter, so match here.

        Names can repeat across environments, so endpoint must match too.
        """
        for stack in self.stacks(endpoint_id):
            if stack.get("Name") == name and stack.get("EndpointId") == endpoint_id:
                return stack
        return None

    def containers(self, endpoint_id: int, project: str) -> list[dict]:
        """List a stack's containers through Portainer's Docker API proxy."""
        filters = json.dumps({"label": [f"com.docker.compose.project={project}"]})
        return (
            self.request(
                "GET",
                f"/endpoints/{endpoint_id}/docker/containers/json",
                params={"all": "1", "filters": filters},
            )
            or []
        )

    def container_logs(self, endpoint_id: int, cid: str, tail: int) -> str:
        payload = self.request(
            "GET",
            f"/endpoints/{endpoint_id}/docker/containers/{cid}/logs",
            params={"stdout": "1", "stderr": "1", "tail": str(tail), "timestamps": "1"},
            raw=True,
        )
        return demux_docker_stream(payload or b"")


def demux_docker_stream(payload: bytes) -> str:
    """Strip Docker's 8-byte stream framing.

    Without a TTY the daemon multiplexes stdout/stderr as
    [stream(1) 0 0 0 size(4 big-endian)][payload]. With a TTY the bytes are
    raw, so fall back to decoding as-is when the framing does not parse.
    """
    out: list[str] = []
    i = 0
    while i + 8 <= len(payload):
        stream = payload[i]
        if stream not in (0, 1, 2):
            return payload.decode("utf-8", "replace")
        size = int.from_bytes(payload[i + 4 : i + 8], "big")
        chunk = payload[i + 8 : i + 8 + size]
        if len(chunk) < size:
            break
        out.append(chunk.decode("utf-8", "replace"))
        i += 8 + size
    if not out:
        return payload.decode("utf-8", "replace")
    return "".join(out)


# ── env pairs ────────────────────────────────────────────────────────


def to_pairs(values: dict[str, str]) -> list[dict[str, str]]:
    """Portainer's Pair struct uses lowercase json tags: {"name":..,"value":..}."""
    return [{"name": k, "value": v} for k, v in sorted(values.items())]


def from_pairs(pairs: list[dict] | None) -> dict[str, str]:
    return {p.get("name", ""): p.get("value", "") for p in (pairs or []) if p.get("name")}


def show_pairs(values: dict[str, str]) -> str:
    return "\n".join(f"    {k}={mask(k, v)}" for k, v in sorted(values.items())) or "    (none)"


# ── commands ─────────────────────────────────────────────────────────


def client_from(args: argparse.Namespace, env: dict[str, str]) -> Portainer:
    return Portainer(
        env.get("PORTAINER_URL", ""),
        env.get("PORTAINER_TOKEN", ""),
        insecure=args.insecure,
        cf_client_id=env.get("CF_ACCESS_CLIENT_ID", ""),
        cf_client_secret=env.get("CF_ACCESS_CLIENT_SECRET", ""),
    )


def endpoint_id_from(args: argparse.Namespace, env: dict[str, str]) -> int:
    raw = args.endpoint_id or env.get("PORTAINER_ENDPOINT_ID", "")
    if not raw:
        raise PortainerError(
            "no endpoint id — pass --endpoint-id or set PORTAINER_ENDPOINT_ID. "
            "Run the `endpoints` command to list them. Never let it default: on a "
            "multi-environment Portainer you would deploy to the wrong host."
        )
    return int(raw)


def cmd_endpoints(args: argparse.Namespace, env: dict[str, str]) -> int:
    api = client_from(args, env)
    version = api.version()
    print(
        f"Portainer {version.get('ServerVersion', '?')} "
        f"({version.get('ServerEdition', '?')})\n"
    )
    types = {1: "docker-local", 2: "docker-agent", 3: "azure", 4: "edge", 5: "k8s-local"}
    print(f"{'Id':>4}  {'Name':<28} {'Type':<14} Status")
    for ep in api.endpoints():
        status = "up" if ep.get("Status") == 1 else "down"
        print(
            f"{ep.get('Id'):>4}  {ep.get('Name', ''):<28} "
            f"{types.get(ep.get('Type'), str(ep.get('Type'))):<14} {status}"
        )
    return 0


def build_create_payload(args: argparse.Namespace, stack_env: dict[str, str], env: dict[str, str]) -> dict:
    private = args.private_repo or env.get("PORTAINER_REPO_PRIVATE", "0") == "1"
    payload: dict = {
        "name": args.name,
        "repositoryURL": args.repo.rstrip("/"),
        "repositoryReferenceName": args.ref,
        "composeFile": args.compose,
        "additionalFiles": [],
        "repositoryAuthentication": private,
        "tlsskipVerify": False,
        "fromAppTemplate": False,
        "env": to_pairs(stack_env),
    }
    if private:
        username = env.get("GITHUB_CLONE_USERNAME", "")
        password = env.get("GITHUB_CLONE_TOKEN", "")
        if not password:
            # The API rejects repositoryAuthentication=true without a password.
            raise PortainerError(
                "private repo requested but GITHUB_CLONE_TOKEN is empty. "
                "Portainer returns 400 when repositoryAuthentication is true "
                "and repositoryPassword is missing."
            )
        payload["repositoryUsername"] = username or "x-access-token"
        payload["repositoryPassword"] = password
    # autoUpdate is deliberately omitted: the API rejects an object with both
    # webhook and interval empty, and CI drives redeploys explicitly.
    return payload


def redact_payload(payload: dict) -> dict:
    shown = dict(payload)
    if "repositoryPassword" in shown:
        shown["repositoryPassword"] = f"<set:{len(shown['repositoryPassword'])} chars>"
    shown["env"] = [
        {"name": p["name"], "value": mask(p["name"], p["value"])} for p in shown.get("env", [])
    ]
    return shown


def cmd_create(args: argparse.Namespace, env: dict[str, str]) -> int:
    api = client_from(args, env)
    endpoint_id = endpoint_id_from(args, env)
    stack_env = load_env_file(Path(args.stack_env), required=False) if args.stack_env else {}

    try:
        existing = api.find_stack(args.name, endpoint_id)
    except PortainerError:
        # A dry run's job is to show the payload for review. Not being able to
        # reach Portainer is fatal for a real apply, but should not block a
        # preview written before the credentials are in place.
        if not args.dry_run:
            raise
        print("# NOTE: Portainer unreachable — could not check whether the stack")
        print("# already exists. Showing the CREATE payload; a real run would")
        print("# switch to redeploy if the name is taken.\n")
        existing = None

    if existing:
        print(
            f"Stack {args.name!r} already exists (id={existing['Id']}) on endpoint "
            f"{endpoint_id} — switching to redeploy."
        )
        return do_redeploy(api, args, env, existing, stack_env, endpoint_id)

    payload = build_create_payload(args, stack_env, env)

    if args.dry_run:
        print(f"# DRY RUN — POST /api/stacks/create/standalone/repository?endpointId={endpoint_id}")
        print(json.dumps(redact_payload(payload), indent=2))
        return 0

    try:
        stack = api.request(
            "POST",
            "/stacks/create/standalone/repository",
            params={"endpointId": str(endpoint_id)},
            body=payload,
        )
    except PortainerError as exc:
        if "HTTP 409" in str(exc):
            # Raced with another deploy, or the name normalized onto an
            # existing stack. Re-resolve and redeploy instead of failing.
            print("409 Conflict — stack name already taken; re-resolving.")
            existing = api.find_stack(args.name, endpoint_id)
            if existing:
                return do_redeploy(api, args, env, existing, stack_env, endpoint_id)
        raise

    print(f"Created stack {stack['Name']!r} id={stack['Id']} on endpoint {endpoint_id}.")
    print(f"Set {len(payload['env'])} stack variables (values not shown).")
    print("\nNote: these are compose *interpolation* variables written to stack.env")
    print("and passed as --env-file. They are not automatically container env.")
    return 0


def do_redeploy(
    api: Portainer,
    args: argparse.Namespace,
    env: dict[str, str],
    stack: dict,
    new_env: dict[str, str],
    endpoint_id: int,
) -> int:
    """Redeploy a git stack, preserving env unless explicitly told to replace.

    The redeploy handler assigns `stack.Env = payload.Env` unconditionally, so
    an omitted or partial `env` silently DELETES stored variables. Always send
    the full, merged set.
    """
    current = from_pairs(stack.get("Env"))
    if args.replace_env:
        merged = dict(new_env)
        dropped = sorted(set(current) - set(merged))
        if dropped:
            print(f"WARNING: --replace-env will drop {len(dropped)} existing vars:")
            for key in dropped:
                print(f"    {key}")
    else:
        merged = {**current, **new_env}

    ref = args.ref or (stack.get("GitConfig") or {}).get("ReferenceName") or "refs/heads/main"
    private = args.private_repo or env.get("PORTAINER_REPO_PRIVATE", "0") == "1"

    payload: dict = {
        "repositoryReferenceName": ref,
        "repositoryAuthentication": private,
        "env": to_pairs(merged),
        "pullImage": True,
        "prune": False,  # ignored for standalone compose; sent for clarity
    }
    if private:
        # An empty password with authentication on means "keep the stored one",
        # so only send it when we actually have a fresh value.
        token = env.get("GITHUB_CLONE_TOKEN", "")
        if token:
            payload["repositoryUsername"] = env.get("GITHUB_CLONE_USERNAME") or "x-access-token"
            payload["repositoryPassword"] = token

    if args.dry_run:
        print(f"# DRY RUN — PUT /api/stacks/{stack['Id']}/git/redeploy?endpointId={endpoint_id}")
        print(json.dumps(redact_payload(payload), indent=2))
        print(f"\n# env: {len(current)} existing + {len(new_env)} incoming -> {len(merged)} sent")
        return 0

    api.request(
        "PUT",
        f"/stacks/{stack['Id']}/git/redeploy",
        params={"endpointId": str(endpoint_id)},
        body=payload,
    )
    print(f"Redeployed stack {stack['Name']!r} (id={stack['Id']}) at {ref}.")
    print(f"Sent {len(merged)} stack variables (values not shown).")
    return 0


def cmd_redeploy(args: argparse.Namespace, env: dict[str, str]) -> int:
    api = client_from(args, env)
    endpoint_id = endpoint_id_from(args, env)
    stack = api.find_stack(args.name, endpoint_id)
    if not stack:
        raise PortainerError(
            f"no stack named {args.name!r} on endpoint {endpoint_id}. "
            "Use the `create` command for the first deploy."
        )
    if not stack.get("GitConfig"):
        raise PortainerError(
            f"stack {args.name!r} is not git-backed; /git/redeploy only works for "
            "stacks created from a repository."
        )
    new_env = load_env_file(Path(args.stack_env), required=False) if args.stack_env else {}
    if args.set:
        for item in args.set:
            key, _, value = item.partition("=")
            new_env[key.strip()] = value
    return do_redeploy(api, args, env, stack, new_env, endpoint_id)


def cmd_status(args: argparse.Namespace, env: dict[str, str]) -> int:
    api = client_from(args, env)
    endpoint_id = endpoint_id_from(args, env)
    stack = api.find_stack(args.name, endpoint_id)
    if not stack:
        print(f"No stack named {args.name!r} on endpoint {endpoint_id}.")
        return 1

    git = stack.get("GitConfig") or {}
    print(f"Stack     {stack['Name']} (id={stack['Id']})")
    print(f"Status    {'active' if stack.get('Status') == 1 else 'inactive'}")
    print(f"Compose   {stack.get('EntryPoint')}")
    print(f"Ref       {git.get('ReferenceName', '-')}")
    print(f"Commit    {git.get('ConfigHash', '-')}")
    print(f"Env vars  {len(stack.get('Env') or [])} stored")

    # Compose derives the project name from the stack name.
    containers = api.containers(endpoint_id, stack["Name"])
    if not containers:
        print(
            "\nNo containers. Common causes: the external network does not exist "
            "on the host, or the image could not be pulled (GHCR packages are "
            "private by default)."
        )
        return 1

    print(f"\n{'Service':<20} {'State':<12} {'Image'}")
    unhealthy = 0
    for c in containers:
        labels = c.get("Labels") or {}
        service = labels.get("com.docker.compose.service", (c.get("Names") or ["?"])[0])
        state = c.get("State", "?")
        if state != "running":
            unhealthy += 1
        print(f"{service:<20} {state:<12} {c.get('Image', '')}")
        if args.verbose:
            print(f"{'':<20} {c.get('Status', '')}")

    if unhealthy:
        print(f"\n{unhealthy} container(s) not running — inspect with the `logs` command.")
    return 1 if unhealthy else 0


def cmd_logs(args: argparse.Namespace, env: dict[str, str]) -> int:
    api = client_from(args, env)
    endpoint_id = endpoint_id_from(args, env)
    for c in api.containers(endpoint_id, args.name):
        labels = c.get("Labels") or {}
        service = labels.get("com.docker.compose.service", "")
        if args.service and service != args.service:
            continue
        print(f"\n===== {service or c.get('Id', '')[:12]} ({c.get('State')}) =====")
        print(api.container_logs(endpoint_id, c["Id"], args.tail))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env.deploy")
    parser.add_argument("--endpoint-id", type=int, default=None)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="skip TLS verification (self-signed Portainer certs)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("endpoints", help="list environments")

    common_stack = argparse.ArgumentParser(add_help=False)
    common_stack.add_argument("--name", required=True, help="stack name")

    p_create = sub.add_parser("create", parents=[common_stack], help="create or redeploy")
    p_create.add_argument("--repo", required=True, help="https://github.com/owner/repo")
    p_create.add_argument("--ref", default="refs/heads/main")
    p_create.add_argument("--compose", required=True, help="path to compose file in the repo")
    p_create.add_argument("--stack-env", default=None, help="dotenv of tier-2 stack variables")
    p_create.add_argument("--private-repo", action="store_true")
    p_create.add_argument("--replace-env", action="store_true")
    p_create.add_argument("--dry-run", action="store_true")

    p_redeploy = sub.add_parser("redeploy", parents=[common_stack], help="redeploy a git stack")
    p_redeploy.add_argument("--ref", default=None, help="default: keep the stack's current ref")
    p_redeploy.add_argument("--stack-env", default=None)
    p_redeploy.add_argument("--set", action="append", metavar="KEY=VALUE")
    p_redeploy.add_argument("--private-repo", action="store_true")
    p_redeploy.add_argument(
        "--replace-env",
        action="store_true",
        help="replace stored env instead of merging (DESTRUCTIVE: drops vars)",
    )
    p_redeploy.add_argument("--dry-run", action="store_true")

    p_status = sub.add_parser("status", parents=[common_stack], help="stack + container state")
    p_status.add_argument("--verbose", action="store_true")

    p_logs = sub.add_parser("logs", parents=[common_stack], help="container logs")
    p_logs.add_argument("--service", default=None, help="compose service name")
    p_logs.add_argument("--tail", type=int, default=200)

    args = parser.parse_args()
    handlers = {
        "endpoints": cmd_endpoints,
        "create": cmd_create,
        "redeploy": cmd_redeploy,
        "status": cmd_status,
        "logs": cmd_logs,
    }
    try:
        env = load_env_file(Path(args.env_file))
        return handlers[args.command](args, env)
    except PortainerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
