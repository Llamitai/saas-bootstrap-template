#!/usr/bin/env python3
"""Verify every system answers before provisioning anything.

Standard library only. Read-only: this script never mutates any system.

Checks Postgres, Infisical, Portainer, GitHub and the repository layout, then
prints one pass/fail table. A half-provisioned deploy is worse than none, so
the intended use is: run this, fix everything red, and only then start phase 1.

Usage:
    preflight.py --env-file .env.deploy
    preflight.py --env-file .env.deploy --skip postgres
"""

from __future__ import annotations

import argparse
import json
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OK, FAIL, WARN, SKIP = "ok", "FAIL", "warn", "skip"


class Result:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str]] = []

    def add(self, system: str, check: str, status: str, detail: str = "") -> None:
        self.rows.append((system, check, status, detail))

    def render(self) -> int:
        w1 = max(len(r[0]) for r in self.rows)
        w2 = max(len(r[1]) for r in self.rows)
        current = None
        for system, check, status, detail in self.rows:
            if system != current:
                print()
                current = system
            marker = {OK: "  ok  ", FAIL: " FAIL ", WARN: " warn ", SKIP: " skip "}[status]
            print(f"[{marker}] {system:<{w1}}  {check:<{w2}}  {detail}")
        failures = sum(1 for r in self.rows if r[2] == FAIL)
        warnings = sum(1 for r in self.rows if r[2] == WARN)
        print()
        if failures:
            print(f"{failures} check(s) FAILED, {warnings} warning(s).")
            print("Fix every failure before starting phase 1. Do not provision")
            print("partially — an interrupted deploy leaves state in three systems.")
        else:
            print(f"All checks passed ({warnings} warning(s)). Safe to start phase 1.")
        return 1 if failures else 0


def load_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        print(f"error: env file not found: {path}", file=sys.stderr)
        print(f"hint: cp <skill-dir>/assets/env.deploy.template {path}", file=sys.stderr)
        raise SystemExit(1)
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


def http(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    insecure: bool = False,
):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        payload = resp.read()
        return resp.status, (json.loads(payload) if payload.strip() else None)


# ── checks ───────────────────────────────────────────────────────────


def check_postgres(env: dict[str, str], res: Result) -> None:
    sysname = "postgres"
    if not shutil.which("psql"):
        res.add(sysname, "psql on PATH", FAIL, "install postgresql-client")
        return
    missing = [k for k in ("PGHOST", "PGUSER", "PGPASSWORD") if not env.get(k)]
    if missing:
        res.add(sysname, "credentials present", FAIL, f"unset: {', '.join(missing)}")
        return

    import os

    penv = dict(os.environ)
    for key in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGSSLMODE"):
        if env.get(key):
            penv[key] = env[key]
    penv.setdefault("PGDATABASE", "postgres")
    penv["PGCONNECT_TIMEOUT"] = "10"

    def q(sql: str) -> tuple[bool, str]:
        proc = subprocess.run(
            ["psql", "-X", "-tA", "-q", "-v", "ON_ERROR_STOP=1", "-c", sql],
            capture_output=True,
            text=True,
            env=penv,
        )
        return proc.returncode == 0, (proc.stdout or proc.stderr).strip()

    ok, out = q("SELECT current_setting('server_version');")
    if not ok:
        res.add(sysname, "connect", FAIL, out.splitlines()[0][:90] if out else "failed")
        return
    res.add(sysname, "connect", OK, f"server {out}")

    ok, out = q("SELECT rolsuper OR rolcreatedb FROM pg_roles WHERE rolname = current_user;")
    res.add(
        sysname,
        "can create databases",
        OK if out == "t" else FAIL,
        "superuser or CREATEDB" if out == "t" else "current_user lacks CREATEDB",
    )

    slug = env.get("PROJECT_SLUG", "")
    if slug:
        ok, out = q(f"SELECT 1 FROM pg_roles WHERE rolname = '{slug}';")
        res.add(sysname, f"role {slug!r}", WARN if out == "1" else OK,
                "already exists — phase 1 will rotate its password" if out == "1" else "free")
        ok, out = q(f"SELECT 1 FROM pg_database WHERE datname = '{slug}';")
        res.add(sysname, f"database {slug!r}", WARN if out == "1" else OK,
                "already exists — phase 1 will leave it alone" if out == "1" else "free")


def check_infisical(env: dict[str, str], res: Result, insecure: bool) -> None:
    sysname = "infisical"
    base = (env.get("INFISICAL_DOMAIN") or env.get("INFISICAL_API_URL", "")).rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]
    if not base:
        res.add(sysname, "URL configured", FAIL, "set INFISICAL_API_URL or INFISICAL_DOMAIN")
        return
    cid = env.get("INFISICAL_MACHINE_CLIENT_ID", "")
    csec = env.get("INFISICAL_MACHINE_CLIENT_SECRET", "")
    if not cid or not csec:
        res.add(sysname, "machine identity", FAIL, "CLIENT_ID / CLIENT_SECRET unset")
        return
    try:
        _, data = http(
            "POST",
            f"{base}/api/v1/auth/universal-auth/login",
            body={"clientId": cid, "clientSecret": csec},
            insecure=insecure,
        )
        token = data["accessToken"]
        res.add(sysname, "authenticate", OK, f"token TTL {data.get('expiresIn', '?')}s")
    except urllib.error.HTTPError as exc:
        res.add(sysname, "authenticate", FAIL, f"HTTP {exc.code} — check client id/secret")
        return
    except Exception as exc:  # noqa: BLE001 — surface any transport failure verbatim
        res.add(sysname, "authenticate", FAIL, str(exc)[:90])
        return

    try:
        _, data = http(
            "GET",
            f"{base}/api/v1/projects?type=secret-manager",
            headers={"Authorization": f"Bearer {token}"},
            insecure=insecure,
        )
        projects = data.get("projects", data) if isinstance(data, dict) else data
        ids = {p.get("id") for p in (projects or [])}
        res.add(sysname, "visible projects", OK if ids else WARN, f"{len(ids)} project(s)")
        for label in ("BACKEND_PROJECT_ID", "FRONTEND_PROJECT_ID"):
            pid = env.get(label, "")
            if not pid:
                res.add(sysname, label, WARN, "unset — phase 2 can create the project")
            elif pid in ids:
                res.add(sysname, label, OK, "reachable")
            else:
                res.add(sysname, label, FAIL, "identity cannot see this project id")
    except Exception as exc:  # noqa: BLE001
        res.add(sysname, "list projects", FAIL, str(exc)[:90])


def check_portainer(env: dict[str, str], res: Result, insecure: bool) -> None:
    sysname = "portainer"
    base = env.get("PORTAINER_URL", "").rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]
    token = env.get("PORTAINER_TOKEN", "")
    if not base or not token:
        res.add(sysname, "URL + token", FAIL, "PORTAINER_URL / PORTAINER_TOKEN unset")
        return
    headers = {"X-API-Key": token}
    cf_id = env.get("CF_ACCESS_CLIENT_ID", "")
    cf_secret = env.get("CF_ACCESS_CLIENT_SECRET", "")
    if cf_id and cf_secret:
        headers["CF-Access-Client-Id"] = cf_id
        headers["CF-Access-Client-Secret"] = cf_secret
        res.add(sysname, "cloudflare access", OK, "service token headers set")

    try:
        _, data = http("GET", f"{base}/api/system/version", headers=headers, insecure=insecure)
        res.add(
            sysname,
            "authenticate",
            OK,
            f"{data.get('ServerVersion', '?')} ({data.get('ServerEdition', '?')})",
        )
    except urllib.error.HTTPError as exc:
        hint = "check token"
        if exc.code in (401, 403) and not cf_id:
            hint = "401/403 — behind Cloudflare Access? set CF_ACCESS_CLIENT_ID/SECRET"
        res.add(sysname, "authenticate", FAIL, f"HTTP {exc.code} — {hint}")
        return
    except json.JSONDecodeError:
        res.add(sysname, "authenticate", FAIL, "non-JSON response — access proxy login page?")
        return
    except Exception as exc:  # noqa: BLE001
        res.add(sysname, "authenticate", FAIL, str(exc)[:90])
        return

    try:
        _, endpoints = http(
            "GET", f"{base}/api/endpoints?excludeSnapshots=true", headers=headers, insecure=insecure
        )
        names = [f"{e.get('Id')}:{e.get('Name')}" for e in (endpoints or [])]
        res.add(sysname, "environments", OK if names else FAIL, " ".join(names) or "none")

        want = env.get("PORTAINER_ENDPOINT_ID", "")
        if want:
            ids = {str(e.get("Id")) for e in (endpoints or [])}
            res.add(
                sysname,
                "PORTAINER_ENDPOINT_ID",
                OK if want in ids else FAIL,
                f"{want} {'found' if want in ids else 'NOT among the ids above'}",
            )
        else:
            res.add(sysname, "PORTAINER_ENDPOINT_ID", WARN, "unset — pick one from the list")
    except Exception as exc:  # noqa: BLE001
        res.add(sysname, "environments", FAIL, str(exc)[:90])


def check_github(env: dict[str, str], res: Result) -> None:
    sysname = "github"
    if not shutil.which("gh"):
        res.add(sysname, "gh on PATH", FAIL, "install the GitHub CLI")
        return
    proc = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if proc.returncode != 0:
        res.add(sysname, "authenticated", FAIL, "run: gh auth login")
        return
    res.add(sysname, "authenticated", OK, "")

    repo = env.get("GITHUB_REPOSITORY", "")
    args = ["gh", "repo", "view", "--json", "nameWithOwner,visibility"]
    if repo:
        args.insert(3, repo)
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        res.add(sysname, "repository", FAIL, (proc.stderr or "not found").strip()[:80])
        return
    info = json.loads(proc.stdout)
    res.add(sysname, "repository", OK, f"{info['nameWithOwner']} ({info['visibility'].lower()})")

    if info["visibility"].lower() == "private" and env.get("PORTAINER_REPO_PRIVATE") != "1":
        res.add(
            sysname,
            "private-repo clone",
            WARN,
            "repo is private but PORTAINER_REPO_PRIVATE != 1 — Portainer cannot clone it",
        )

    proc = subprocess.run(
        ["gh", "api", f"repos/{info['nameWithOwner']}/environments", "--jq", ".environments[].name"],
        capture_output=True,
        text=True,
    )
    existing = proc.stdout.split() if proc.returncode == 0 else []
    for name in ("Production", "Development"):
        res.add(
            sysname,
            f"environment {name}",
            OK if name in existing else WARN,
            "exists" if name in existing else "missing — github_setup.sh creates it",
        )


def check_repo(res: Result) -> None:
    sysname = "repo"
    for path in (
        "backend/docker-compose.prod.yml",
        "frontend/docker-compose.prod.yml",
        "backend/.env.example",
        "frontend/.env.example",
        ".github/workflows/build_backend.yml",
        ".github/workflows/build_frontend.yml",
    ):
        exists = Path(path).is_file()
        res.add(sysname, path, OK if exists else FAIL, "" if exists else "not found")

    gitignored = subprocess.run(
        ["git", "check-ignore", "-q", ".env.deploy"], capture_output=True
    ).returncode == 0
    res.add(
        sysname,
        ".env.deploy gitignored",
        OK if gitignored else FAIL,
        "" if gitignored else "ADD IT TO .gitignore BEFORE FILLING IT IN",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env.deploy")
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        choices=["postgres", "infisical", "portainer", "github", "repo"],
    )
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    args = parser.parse_args()

    env = load_env_file(Path(args.env_file))
    res = Result()

    print(f"Preflight — reading {args.env_file}. Nothing is modified.")

    for name, fn in (
        ("repo", lambda: check_repo(res)),
        ("postgres", lambda: check_postgres(env, res)),
        ("infisical", lambda: check_infisical(env, res, args.insecure)),
        ("portainer", lambda: check_portainer(env, res, args.insecure)),
        ("github", lambda: check_github(env, res)),
    ):
        if name in args.skip:
            res.add(name, "(skipped)", SKIP, "--skip " + name)
            continue
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — one bad system must not hide the rest
            res.add(name, "unexpected error", FAIL, str(exc)[:90])

    return res.render()


if __name__ == "__main__":
    sys.exit(main())
