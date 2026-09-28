"""Export the FastAPI OpenAPI schema that the docs site renders.

Prints the schema to stdout, or with ``--check PATH`` compares it against the
committed snapshot and exits 1 when they differ. Invoked by just and CI from
backend/; no database or other service is contacted.
"""

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
# FastAPI declares no servers; the docs playground and code samples need a base URL.
DOCS_SERVERS = [{"url": "http://localhost:8200", "description": "Backend local (just backend dev)"}]


def build_schema() -> dict[str, Any]:
    # Importing the app configures logging that writes to stdout; keep stdout for JSON.
    sys.path.insert(0, str(BACKEND_ROOT))
    with contextlib.redirect_stdout(sys.stderr):
        from config.main import app

        schema = app.openapi()
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            # include_router(tags=...) plus APIRouter(tags=...) repeats each tag.
            if isinstance(operation, dict) and "tags" in operation:
                operation["tags"] = list(dict.fromkeys(operation["tags"]))
    schema.setdefault("servers", DOCS_SERVERS)
    return schema


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", type=Path, help="committed snapshot to compare against")
    args = parser.parse_args()

    output = render(build_schema())
    if args.check is None:
        sys.stdout.write(output)
        return 0
    if not args.check.is_file() or args.check.read_text(encoding="utf-8") != output:
        print(
            f"{args.check} is out of date with the FastAPI schema; run `just backend openapi`.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
