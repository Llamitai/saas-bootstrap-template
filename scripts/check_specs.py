#!/usr/bin/env python3
"""Validate all local active changes and accepted specs; no semantic acceptance."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    count = 0
    for folder, kind in [('changes', 'change'), ('specs', 'spec')]:
        parent = ROOT / 'openspec' / folder
        for item in sorted(parent.iterdir()) if parent.exists() else []:
            if not item.is_dir() or item.name == 'archive':
                continue
            result = subprocess.run(['node', str(ROOT / 'scripts/openspec.mjs'), 'check', item.name, kind], cwd=ROOT, check=False)
            if result.returncode:
                return result.returncode
            count += 1
    print(f'OpenSpec: {count} local definitions structurally checked; product acceptance is separate')
    return 0


if __name__ == '__main__':
    sys.exit(main())
