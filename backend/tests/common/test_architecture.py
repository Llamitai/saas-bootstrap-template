"""Structural rules the linters cannot express: contract coverage, routing, commits, ORM placement."""

import ast
import tomllib
from pathlib import Path

from expects import be_empty, equal, expect

import src.common.database.models  # noqa: F401  registers every ORM model on Base
from src.common.database.mixins.common import Base

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SRC = BACKEND_ROOT / "src"
TRANSACTION_HELPER = SRC / "common/infrastructure/helpers/database.py"
ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "head", "options", "api_route", "route"}


def _import_contracts() -> list[dict]:
    with (BACKEND_ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)["tool"]["importlinter"]["contracts"]


def _contract(name: str) -> dict:
    return next(contract for contract in _import_contracts() if contract["name"] == name)


def _feature_packages() -> set[str]:
    return {f"src.{path.parent.name}" for path in SRC.glob("*/__init__.py")}


def _source_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _relative(path: Path) -> str:
    return str(path.relative_to(BACKEND_ROOT))


def test_layers_contract__covers_every_backend_module():
    containers = set(_contract("Clean Architecture layers within each module")["containers"])

    missing = sorted(_feature_packages() - containers)
    stale = sorted(containers - _feature_packages())

    expect(missing).to(be_empty)  # add these modules to the layers contract `containers` in pyproject.toml
    expect(stale).to(be_empty)  # remove these deleted modules from the layers contract


def test_shared_domain_contract__forbids_every_feature_module():
    forbidden = set(_contract("Shared domain does not depend on features")["forbidden_modules"])

    missing = sorted(_feature_packages() - {"src.common"} - forbidden)

    expect(missing).to(be_empty)  # add these modules to "Shared domain does not depend on features"


def test_routes__are_registered_with_add_api_route():
    decorated = []
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                if isinstance(target, ast.Attribute) and target.attr in ROUTE_DECORATORS:
                    decorated.append(f"{_relative(path)}:{node.lineno} @{ast.unparse(target)}")

    expect(decorated).to(be_empty)  # register these routes with router.add_api_route(...)


def test_commits__only_happen_in_the_transaction_helper():
    commits = []
    for path in _source_files():
        if path == TRANSACTION_HELPER:
            continue
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "commit":
                commits.append(f"{_relative(path)}:{node.lineno}")

    expect(commits).to(be_empty)  # wrap the write in atomic_transaction(session) instead


def test_orm_models__live_in_the_shared_database_package():
    misplaced = sorted(
        f"{mapper.class_.__module__}.{mapper.class_.__name__}"
        for mapper in Base.registry.mappers
        if not mapper.class_.__module__.startswith("src.common.database.")
    )

    expect(misplaced).to(be_empty)  # move these ORM classes under src/common/database/models/
    expect(len(Base.registry.mappers) > 0).to(equal(True))
