#!/usr/bin/env python3
"""Run backend/API/browser checks in an exclusive Compose project; clean only it."""
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent


def wait_ready(url: str, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise TimeoutError(f"API not ready within {timeout}s: {url}")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["unit", "single", "api", "all", "integration", "migrations"])
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if os.environ.get("DOCKER_HOST", "").startswith("tcp://"):
        os.environ["TEST_BIND_HOST"] = "0.0.0.0"
    project = f"check-{uuid4().hex[:12]}"
    compose = ["docker", "compose", "-p", project, "-f", str(ROOT / "backend/docker-compose.test.yml")]

    def run(*command: str, capture: bool = False):
        return subprocess.run([*compose, *command], cwd=ROOT, check=True, text=True, capture_output=capture)

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        run("up", "-d", "--wait", "--wait-timeout", "90", "postgres", "redis", "rabbitmq", "mailpit")
        run("build", "api")
        if args.mode == "migrations":
            run("run", "--rm", "api", "python", "scripts/check_migrations.py", *args.args)
        else:
            if args.mode in {"api", "all", "integration"}:
                run("run", "--rm", "api", "alembic", "upgrade", "head")
                run("up", "-d", "api")
                address = run("port", "api", "8200", capture=True).stdout.strip()
                # With Docker-in-Docker the published port belongs to its service host.
                docker_host = os.environ.get("DOCKER_HOST", "")
                if docker_host.startswith("tcp://"):
                    from urllib.parse import urlparse
                    host = urlparse(docker_host).hostname
                    address = f"{host}:{address.rsplit(':', 1)[1]}"
                backend_url = f"http://{address}"
                wait_ready(backend_url)
            if args.mode == "integration":
                env = {**os.environ, "BACKEND_API_HOST": backend_url,
                       "NEXT_PUBLIC_BACKEND_API_HOST": backend_url,
                       "BACKEND_API_KEY": "test-super-secret-key",
                       "E2E_API_URL": backend_url, "E2E_API_KEY": "test-super-secret-key",
                       "E2E_PORT": str(free_port()), "E2E_INTEGRATION": "1",
                       "E2E_RUN_ID": project}
                subprocess.run(["pnpm", "-C", "frontend", "test:e2e", *args.args], cwd=ROOT, env=env, check=True)
            else:
                selection = {"unit": ["-m", "not api"], "single": ["-m", "single"], "api": ["-m", "api"], "all": []}[args.mode]
                run("run", "--rm", "api", "pytest", *selection, *args.args)
        return 0
    except (subprocess.CalledProcessError, TimeoutError, KeyboardInterrupt) as error:
        print(f"Test stack {project} failed: {error}", file=sys.stderr)
        subprocess.run([*compose, "logs", "--tail", "80", "api"], cwd=ROOT, check=False)
        return 1
    finally:
        subprocess.run([*compose, "down", "--volumes", "--remove-orphans", "--timeout", "10"], cwd=ROOT, check=False)


if __name__ == "__main__":
    sys.exit(main())
