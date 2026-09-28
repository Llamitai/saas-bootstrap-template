# Related backend tools

Use this reference only when a concrete FastAPI API question also depends on a
related library or tool. Read `backend/pyproject.toml`, its lock and an installed
example before choosing a package or command.

This project uses SQLAlchemy for persistence, `asyncio.to_thread` for blocking
work inside async paths, and the `just backend` recipes for local execution and
checks. Do not substitute SQLModel, Asyncer or the generic `fastapi dev` command
because an upstream example uses them. Ruff, ty, uv and HTTPX are governed by
the project's manifests and existing usage, not by a blanket preference in a
framework guide.
