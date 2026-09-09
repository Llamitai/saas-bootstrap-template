"""Shared non-mutating static gate, invoked by just and CI from backend/."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root)}
    for command in (
        ["ruff", "format", "--check", "."],
        ["ruff", "check", "."],
        ["ty", "check"],
        ["lint-imports"],
    ):
        result = subprocess.run(command, cwd=root, env=env, check=False)  # noqa: S603
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
