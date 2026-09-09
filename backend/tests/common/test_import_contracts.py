"""Negative fixtures verify cross-module and framework boundary enforcement."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from expects import be_empty, equal, expect


@pytest.mark.parametrize(
    ("file", "content", "allowed"),
    [
        ("auth/domain/model.py", "from src.common.domain.models import item", True),
        ("auth/domain/model.py", "from src.tenants.infrastructure import repository", False),
        ("users/application/creator.py", "import sqlalchemy", False),
        ("common/domain/models/item.py", "from src.auth.domain import model", False),
    ],
)
def test_import_contracts_reject_boundary_bypasses(tmp_path: Path, file: str, content: str, allowed: bool):
    config = Path("pyproject.toml").resolve()
    for module in ("admin", "assets", "auth", "common", "messaging", "profile", "tenants", "users"):
        for layer in ("domain", "application", "infrastructure", "presentation"):
            directory = tmp_path / "src" / module / layer
            directory.mkdir(parents=True)
            for parent in (directory, directory.parent, directory.parent.parent):
                (parent / "__init__.py").touch()
    for name, source in {
        "common/database/__init__.py": "",
        "common/domain/models/__init__.py": "",
        "common/domain/models/item.py": "",
        "common/application/helpers/__init__.py": "",
        "common/application/helpers/json_encoder.py": "import fastapi",
        "tenants/infrastructure/repository.py": "",
        "auth/domain/model.py": "",
        file: content,
    }.items():
        target = tmp_path / "src" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
    executable = shutil.which("lint-imports") or ""
    expect(executable).not_to(be_empty)
    result = subprocess.run(  # noqa: S603
        [executable, "--config", str(config)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    expect(result.returncode == 0).to(equal(allowed))
